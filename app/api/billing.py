import logging

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.models.schemas import Plan
from app.services import stripe_service

logger = logging.getLogger(__name__)
router = APIRouter()

PAID_PLANS = {"starter", "pro", "business"}


class CheckoutRequest(BaseModel):
    email: EmailStr
    plan: Plan


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalRequest(BaseModel):
    stripe_customer_id: str


class PortalResponse(BaseModel):
    portal_url: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    payment_status: str
    email: str
    plan: str
    api_key_created: bool


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest, request: Request) -> CheckoutResponse:
    if body.plan not in PAID_PLANS:
        raise HTTPException(status_code=400, detail="Use /api/keys for the free plan.")
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured.")

    success_url = f"{settings.FRONTEND_URL}/api/billing/session/{{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.FRONTEND_URL}/pricing"

    try:
        checkout_url = stripe_service.create_checkout_session(
            email=body.email,
            plan=body.plan,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.StripeError as exc:
        logger.exception("Stripe checkout creation failed for %s", body.email)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.verify_webhook(payload, sig_header)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Database not configured.")

    event_type: str = event["type"]
    event_data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await stripe_service.handle_checkout_completed(event_data, supabase)
        elif event_type == "customer.subscription.deleted":
            await stripe_service.handle_subscription_deleted(event_data, supabase)
        elif event_type == "customer.subscription.updated":
            await stripe_service.handle_subscription_updated(event_data, supabase)
    except Exception:
        logger.exception("Webhook handler failed for event %s", event_type)
        raise HTTPException(status_code=500, detail="Webhook processing error")

    return {"received": True}


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str, request: Request) -> SessionStatusResponse:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured.")

    try:
        session = stripe_service.get_checkout_session(session_id)
    except stripe.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except stripe.StripeError as exc:
        logger.exception("Stripe error retrieving session %s", session_id)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    email = getattr(session.metadata, "email", "") if session.metadata else ""
    plan = getattr(session.metadata, "plan", "unknown") if session.metadata else "unknown"

    supabase = getattr(request.app.state, "supabase", None)
    api_key_created = False
    if supabase and email:
        result = await supabase.table("api_keys").select("id").eq("email", email).execute()
        api_key_created = len(result.data) > 0

    return SessionStatusResponse(
        session_id=session_id,
        status=session.status,
        payment_status=session.payment_status,
        email=email,
        plan=plan,
        api_key_created=api_key_created,
    )


@router.post("/portal", response_model=PortalResponse)
async def billing_portal(body: PortalRequest) -> PortalResponse:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured.")

    try:
        session = stripe.billing_portal.Session.create(
            customer=body.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard",
        )
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return PortalResponse(portal_url=session.url)
