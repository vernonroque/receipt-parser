from PIL import Image, ImageOps
import io


def fix_orientation(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()

def binarization():

def straighten():

def sharpen():

def upscale_image():