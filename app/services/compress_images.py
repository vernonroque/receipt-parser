import base64
from PIL import Image
import io

_BASE64_OVERHEAD = 4 / 3  # base64 expands raw bytes by ~33%
_CLAUDE_MAX_BASE64_BYTES = 5 * 1024 * 1024  # Claude's 5MB base64 limit
_SAFE_RAW_MAX = int(_CLAUDE_MAX_BASE64_BYTES / _BASE64_OVERHEAD)  # ~3.75MB raw

def compress_image_for_claude(image_bytes: bytes, max_size_bytes: int = _SAFE_RAW_MAX) -> tuple[bytes, str]:
    """Compress image so its base64 encoding stays within Claude's 5MB limit."""
    img = Image.open(io.BytesIO(image_bytes))
    media_type = "image/png"

    # Palette mode needs conversion before PNG re-save
    if img.mode == "P":
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    compressed = buffer.getvalue()

    if len(compressed) <= max_size_bytes:
        return compressed, media_type

    # PNG is lossless, so downscale until it fits
    while len(compressed) > max_size_bytes:
        scale = (max_size_bytes / len(compressed)) ** 0.5
        new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        img = img.resize(new_size, Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        compressed = buffer.getvalue()

    return compressed, media_type
