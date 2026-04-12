from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.models.schemas import ParseResponse
from app.services.auth_middleware import get_current_user
from app.services.parser_service import parse_images
from app.services.pdf_service import pdf_to_images, PDFConversionError
from app.core.config import settings

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

    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
        )

    try:
        # --- PDF path ---
        if content_type == ALLOWED_PDF_TYPE:
            image_bytes_list = pdf_to_images(file_bytes)
        # --- Image path ---
        else:
            image_bytes_list = [file_bytes]

        parsed, pages_processed = parse_images(image_bytes_list)

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
