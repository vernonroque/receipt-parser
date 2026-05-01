import io
from PIL import Image

_BASE64_OVERHEAD = 4 / 3  # base64 expands raw bytes by ~33%
_CLAUDE_MAX_BASE64_BYTES = 5 * 1024 * 1024  # Claude's 5MB base64 limit
_SAFE_RAW_MAX = int(_CLAUDE_MAX_BASE64_BYTES / _BASE64_OVERHEAD)  # ~3.75MB raw


def compress_image_for_claude(img: Image.Image, max_size_bytes: int = _SAFE_RAW_MAX) -> bytes:
    """Compress a PIL Image to JPEG bytes within Claude's 5MB base64 limit."""
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Probe at quality=85
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    probe = buf.getvalue()
    if len(probe) <= max_size_bytes:
        return probe

    # Estimate target quality from ratio (1-2 encodes total for most images)
    estimated_quality = max(10, min(int(85 / (len(probe) / max_size_bytes)), 75))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=estimated_quality)
    result = buf.getvalue()
    if len(result) <= max_size_bytes:
        return result

    # Fallback: downscale then encode (only for extreme edge cases)
    scale = (max_size_bytes / len(result)) ** 0.5
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()
