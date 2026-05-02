from PIL import Image, ImageOps
import anthropic
import base64
import cv2
import json
import logging
import numpy as np
import io

_claude_client = anthropic.Anthropic()

_CORNER_PROMPT = """Look at this image and find the receipt or document in it.
Return ONLY a JSON array with exactly 4 corner points of the receipt, ordered:
top-left, top-right, bottom-right, bottom-left.
Each point is [x, y] as a fraction of image width/height (0.0 to 1.0).
Example: [[0.1, 0.05], [0.9, 0.05], [0.92, 0.95], [0.08, 0.95]]
If no clear receipt is visible, return null.
Return ONLY the JSON, no explanation."""


def fix_orientation(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    if img.width > img.height:
        img = img.rotate(90, expand=True)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()
    
def _normalize_exposure(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _detect_corners_via_rembg(image_bytes: bytes, w: int, h: int) -> np.ndarray | None:
    try:
        from rembg import remove
        rgba_bytes = remove(image_bytes)
        buf = np.frombuffer(rgba_bytes, dtype=np.uint8)
        rgba = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.ndim < 3 or rgba.shape[2] < 4:
            return None
        rh, rw = rgba.shape[:2]
        alpha = rgba[:, :, 3]
        if rh != h or rw != w:
            alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_NEAREST)

        k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, k_close, iterations=1)
        _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 0.10 * h * w:
            return None

        for eps in (0.02, 0.03, 0.05, 0.08, 0.10):
            approx = cv2.approxPolyDP(largest, eps * cv2.arcLength(largest, True), True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
                pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
                return pts

        box = cv2.boxPoints(cv2.minAreaRect(largest))
        pts = box.astype(np.float32)
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
        return pts
    except Exception as e:
        logging.warning("rembg corner detection failed: %s", e)
        return None


def _detect_corners_via_claude(image_bytes: bytes, w: int, h: int) -> np.ndarray | None:
    try:
        b64 = base64.standard_b64encode(image_bytes).decode()
        response = _claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": _CORNER_PROMPT},
                ],
            }],
        )
        import re
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        if text.lower() == "null":
            return None
        pts = np.array(json.loads(text), dtype=np.float32)
        pts[:, 0] *= w
        pts[:, 1] *= h
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
        return pts
    except Exception as e:
        logging.warning("Claude corner detection failed: %s", e)
        return None


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    dst_w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    dst_h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst_pts = np.array([
        [0,       0      ],
        [dst_w-1, 0      ],
        [dst_w-1, dst_h-1],
        [0,       dst_h-1],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(rect, dst_pts)
    return cv2.warpPerspective(img, M, (dst_w, dst_h))


def _detect_receipt_corners(img: np.ndarray) -> np.ndarray | None:
    h, w = img.shape[:2]
    scale = 0.4
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    sh, sw = small.shape[:2]

    def _scale_pts(pts):
        pts = pts.astype(np.float32) / scale
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
        return pts

    def _best_quad(contours, min_area):
        for c in contours:
            if cv2.contourArea(c) < min_area:
                break
            for eps in (0.02, 0.03, 0.05, 0.08, 0.10):
                approx = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
                if len(approx) == 4:
                    return _scale_pts(approx.reshape(4, 2))
        return None

    min_area = 0.10 * sh * sw

    # Method 1: HSV white-region — reliable when receipt is white on colorful background
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 150), (180, 60, 255))
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    k_open  = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close, iterations=4)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k_open,  iterations=1)
    contours_hsv, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours_hsv = sorted(contours_hsv, key=cv2.contourArea, reverse=True)
    result = _best_quad(contours_hsv, min_area)
    if result is not None:
        return result

    # Method 2: Canny edges — fallback for non-white or low-contrast receipts
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 75, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=2)
    contours_canny, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours_canny = sorted(contours_canny, key=cv2.contourArea, reverse=True)
    result = _best_quad(contours_canny, min_area)
    if result is not None:
        return result

    # Last resort: minimum-area bounding box of largest HSV region
    if contours_hsv and cv2.contourArea(contours_hsv[0]) >= min_area:
        box = cv2.boxPoints(cv2.minAreaRect(contours_hsv[0]))
        return _scale_pts(box)
    return None


def _tight_crop_white(img: np.ndarray, padding: int = 10) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 140), (180, 50, 255))
    coords = cv2.findNonZero(mask)
    if coords is None:
        return img
    x, y, cw, ch = cv2.boundingRect(coords)
    x  = max(0, x - padding)
    y  = max(0, y - padding)
    cw = min(img.shape[1] - x, cw + 2 * padding)
    ch = min(img.shape[0] - y, ch + 2 * padding)
    return img[y:y + ch, x:x + cw]


def crop_to_content(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    img = _normalize_exposure(img)
    h, w = img.shape[:2]

    corners = _detect_corners_via_rembg(image_bytes, w, h)
    if corners is None:
        corners = _detect_corners_via_claude(image_bytes, w, h)
    if corners is None:
        corners = _detect_receipt_corners(img)
    if corners is None:
        return image_bytes

    warped = _four_point_transform(img, corners)
    if warped.shape[0] < 100 or warped.shape[1] < 100:
        return image_bytes

    # Receipts are always portrait; if the warp mis-ordered corners and produced
    # a landscape image, rotate 90° CCW to restore portrait orientation.
    if warped.shape[1] > warped.shape[0]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE)

    cropped = _tight_crop_white(warped)

    _, encoded = cv2.imencode('.jpg', cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()

def deskew(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img_color = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0)[::-1])  # (x, y) ordering for minAreaRect
    if coords.size == 0:
        return image_bytes

    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return image_bytes

    (h, w) = img_color.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(img_color, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    _, encoded = cv2.imencode('.jpg', deskewed, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()

def binarization(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=25,
        C=12,
    )

    _, encoded = cv2.imencode('.jpg', binary, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()

def sharpen(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=2)
    sharpened = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

    _, encoded = cv2.imencode('.jpg', sharpened, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()