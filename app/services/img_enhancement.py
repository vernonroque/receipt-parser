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


def crop_to_content(image_bytes: bytes) -> bytes:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    scale = 800.0 / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    sh, sw = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 75, 200)

    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    doc_contour = None
    min_area = sh * sw * 0.10
    for c in contours:
        if cv2.contourArea(c) < min_area:
            break
        hull = cv2.convexHull(c)
        for eps in (0.02, 0.03, 0.04, 0.05):
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                doc_contour = approx
                break
        if doc_contour is not None:
            break

    if doc_contour is None:
        return image_bytes

    pts = (doc_contour.reshape(4, 2) / scale).astype(np.float32)
    result = _four_point_transform(img, pts)

    if result.shape[0] < 100 or result.shape[1] < 100:
        return image_bytes

    _, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 95])
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