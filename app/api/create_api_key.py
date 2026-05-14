import logging
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.models.schemas import Plan
from app.services.api_key_service import generate_api_key
from app.services.email_service import send_api_key_email
from app.services import stripe_service

logger = logging.getLogger(__name__)
router = APIRouter()

PAID_PLANS = {"starter", "pro", "business"}


class CreateKeyRequest(BaseModel):
    email: EmailStr
    plan: Plan = "free"


class CreateKeyResponse(BaseModel):
    message: Optional[str] = None
    checkout_url: Optional[str] = None


@router.post("/keys", response_model=CreateKeyResponse)
async def create_api_key(body: CreateKeyRequest, request: Request) -> CreateKeyResponse:
    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Database not configured.")

    # Paid plans: redirect to Stripe checkout — key is created after payment webhook
    if body.plan in PAID_PLANS:
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe not configured.")
        success_url = f"{settings.FRONTEND_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{settings.FRONTEND_URL}/pricing"
        try:
            checkout_url = stripe_service.create_checkout_session(
                email=body.email,
                plan=body.plan,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe checkout creation failed for %s", body.email)
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")
        return CreateKeyResponse(checkout_url=checkout_url)

    # Free plan: generate key immediately and email it
    try:
        raw_key = await generate_api_key(name=body.email, supabase=supabase, email=body.email, plan="free")
    except Exception as e:
        logger.exception("Failed to generate API key for %s", body.email)
        raise HTTPException(status_code=500, detail=f"Failed to generate API key: {e}")

    try:
        await send_api_key_email(to_email=body.email, api_key=raw_key)
    except Exception as e:
        logger.exception("Email delivery failed for %s", body.email)
        raise HTTPException(status_code=500, detail=f"Key created but email delivery failed: {e}")

    return CreateKeyResponse(message="API key sent to your email.")
