import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.services.api_key_service import generate_api_key
from app.services.email_service import send_api_key_email

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateKeyRequest(BaseModel):
    email: EmailStr


class CreateKeyResponse(BaseModel):
    message: str


@router.post("/keys", response_model=CreateKeyResponse)
async def create_api_key(body: CreateKeyRequest, request: Request) -> CreateKeyResponse:
    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Database not configured.")

    try:
        raw_key = await generate_api_key(name=body.email, supabase=supabase, email=body.email)
    except Exception as e:
        logger.exception("Failed to generate API key for %s", body.email)
        raise HTTPException(status_code=500, detail=f"Failed to generate API key: {e}")

    try:
        await send_api_key_email(to_email=body.email, api_key=raw_key)
    except Exception as e:
        logger.exception("Email delivery failed for %s", body.email)
        raise HTTPException(status_code=500, detail=f"Key created but email delivery failed: {e}")

    return CreateKeyResponse(message="API key sent to your email.")
