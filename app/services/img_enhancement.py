from PIL import Image, ImageOps
import cv2
import numpy as np
import io


def fix_orientation(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()
    
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
    small = cv2.resize(img, (int(w * 0.25), int(h * 0.25)))
    sh, sw = small.shape[:2]

    margin_x = int(sw * 0.20)
    margin_y = int(sh * 0.05)
    rect = (margin_x, margin_y, sw - 2 * margin_x, sh - 2 * margin_y)

    mask = np.zeros(small.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)

    fg_mask = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    fg_mask = cv2.resize(fg_mask, (w, h), interpolation=cv2.INTER_NEAREST)

    k = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 30))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k, iterations=3)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)

    for eps in (0.02, 0.03, 0.05, 0.08, 0.10):
        approx = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)

    box = cv2.boxPoints(cv2.minAreaRect(c))
    return box.astype(np.float32)


def _tight_crop_white(img: np.ndarray, padding: int = 10) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
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

    corners = _detect_receipt_corners(img)
    if corners is None:
        return image_bytes

    warped = _four_point_transform(img, corners)
    if warped.shape[0] < 100 or warped.shape[1] < 100:
        return image_bytes

    cropped = _tight_crop_white(warped)

    _, encoded = cv2.imencode('.jpg', cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()

def deskew(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img_color = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0))
    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = img_color.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(img_color, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    _, encoded = cv2.imencode('.jpg', deskewed, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()

def binarization():
    pass

def sharpen():
    pass