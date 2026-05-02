import base64
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.schemas import ParseResponse
from app.services.auth_middleware import get_current_user
from app.services.parser_service import parse_images
from app.services.gpt_parser_service import parse_images_gpt
from app.services.pdf_service import pdf_to_images, PDFConversionError
from app.core.config import settings
from app.services.compress_images import compress_image_for_claude
from app.services.img_enhancement import fix_orientation, binarization, deskew, sharpen,crop_to_content

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PDF_TYPE = "application/pdf"
MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024
_HARD_LIMIT_BYTES = 20 * 1024 * 1024  # absolute ceiling before any processing

_IMAGE_MAGIC = (b'\xff\xd8\xff', b'\x89PNG', b'%PDF', b'RIFF', b'GIF8')


def _decode_if_base64(data: bytes) -> bytes:
    if not any(data.startswith(m) for m in _IMAGE_MAGIC):
        try:
            return base64.b64decode(data)
        except Exception:
            pass
    return data


@router.post(
    "/parse",
    response_model=ParseResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Receipt or invoice file (JPEG, PNG, WEBP, or PDF)",
                            }
                        },
                        "required": ["file"],
                    }
                }
            }
        }
    },
)
async def parse_receipt(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Upload a receipt or invoice (JPEG, PNG, WEBP, or PDF).
    Returns structured JSON with merchant info, line items, and totals.
    """
    start_time = time.perf_counter()
    form = await request.form()
    file_field = form.get("file")

    if file_field is None:
        raise HTTPException(status_code=422, detail="Missing required field: file")

    # RapidAPI Studio sends file as a JSON string: {"value": "name.jpg", "data": "data:image/jpeg;base64,..."}
    if isinstance(file_field, str):
        try:
            file_info = json.loads(file_field)
            data_uri: str = file_info.get("data", "")
            header, b64_data = data_uri.split(",", 1)
            content_type = header.split(";")[0].split(":")[1]
            file_bytes = base64.b64decode(b64_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid file field format.")
    else:
        content_type = file_field.content_type or ""
        file_bytes = await file_field.read()
        file_bytes = _decode_if_base64(file_bytes)

    if content_type not in ALLOWED_IMAGE_TYPES and content_type != ALLOWED_PDF_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: JPEG, PNG, WEBP, PDF.",
        )

    if len(file_bytes) > _HARD_LIMIT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum upload size is 20MB.",
        )

    if content_type == ALLOWED_PDF_TYPE:
        if len(file_bytes) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
            )
    else:
        # file_bytes = fix_orientation(file_bytes)
        # file_bytes = crop_to_content(file_bytes)
        # file_bytes = deskew(file_bytes)
        # file_bytes = binarization(file_bytes)
        # file_bytes = sharpen(file_bytes)
        file_bytes, _ = compress_image_for_claude(file_bytes)
        if len(file_bytes) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
            )

    try:
        if content_type == ALLOWED_PDF_TYPE:
            image_bytes_list = pdf_to_images(file_bytes)
            compressed_list = [compress_image_for_claude(fix_orientation(p))[0] for p in image_bytes_list]
        else:
            compressed_list = [file_bytes]

        parsed, pages_processed = await parse_images(compressed_list)

        return ParseResponse(
            success=True,
            pages_processed=pages_processed,
            data=parsed,
            response_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    except PDFConversionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        return ParseResponse(
            success=False,
            pages_processed=0,
            error=f"Parsing failed: {str(e)}",
            response_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )
