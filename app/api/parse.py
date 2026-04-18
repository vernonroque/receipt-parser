import base64
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.models.schemas import ParseResponse
from app.services.auth_middleware import get_current_user
from app.services.parser_service import parse_images
from app.services.pdf_service import pdf_to_images, PDFConversionError
from app.core.config import settings
from app.services.compress_images import compress_image_for_claude

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_PDF_TYPE = "application/pdf"
MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/parse", response_model=ParseResponse)
async def parse_receipt(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """
    Upload a receipt or invoice (JPEG, PNG, WEBP, or PDF).
    Returns structured JSON with merchant info, line items, and totals.
    """
    content_type = file.content_type or ""

    if content_type not in ALLOWED_IMAGE_TYPES and content_type != ALLOWED_PDF_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: JPEG, PNG, WEBP, PDF.",
        )

    file_bytes = await file.read()

    # RapidAPI Studio sends files as base64 strings; detect by absence of magic bytes
    _IMAGE_MAGIC = (b'\xff\xd8\xff', b'\x89PNG', b'%PDF', b'RIFF', b'GIF8')
    if not any(file_bytes.startswith(m) for m in _IMAGE_MAGIC):
        try:
            file_bytes = base64.b64decode(file_bytes)
        except Exception:
            pass

    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
        )

    try:
        if content_type == ALLOWED_PDF_TYPE:
            image_bytes_list = pdf_to_images(file_bytes)
        else:
            image_bytes_list = [file_bytes]

        # Compress each image individually before sending to Claude
        compressed_list = []
        for page_bytes in image_bytes_list:
            compressed, media_type = compress_image_for_claude(page_bytes)
            compressed_list.append(compressed)

        parsed, pages_processed = parse_images(compressed_list)

        return ParseResponse(
            success=True,
            pages_processed=pages_processed,
            data=parsed,
        )

    except PDFConversionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        return ParseResponse(
            success=False,
            pages_processed=0,
            error=f"Parsing failed: {str(e)}",
        )
