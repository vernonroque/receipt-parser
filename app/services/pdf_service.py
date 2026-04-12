import io
from typing import List
from PIL import Image

try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from app.core.config import settings


class PDFConversionError(Exception):
    pass


def pdf_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Convert a PDF to a list of JPEG image bytes, one per page.
    Raises PDFConversionError if conversion fails or page limit is exceeded.
    """
    if not PDF_SUPPORT:
        raise PDFConversionError(
            "pdf2image is not installed. Run: pip install pdf2image "
            "and install poppler (see README)."
        )

    try:
        pages = convert_from_bytes(
            pdf_bytes,
            dpi=200,           # High enough for Claude to read text clearly
            fmt="jpeg",
            thread_count=2,
        )
    except Exception as e:
        raise PDFConversionError(f"Failed to convert PDF: {str(e)}")

    if len(pages) > settings.MAX_PDF_PAGES:
        raise PDFConversionError(
            f"PDF has {len(pages)} pages. Maximum allowed is {settings.MAX_PDF_PAGES}."
        )

    image_bytes_list = []
    for page in pages:
        buffer = io.BytesIO()
        # Convert to RGB first (handles PDFs with transparency/CMYK)
        page.convert("RGB").save(buffer, format="JPEG", quality=90)
        image_bytes_list.append(buffer.getvalue())

    return image_bytes_list
