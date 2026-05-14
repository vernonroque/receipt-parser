import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# Maps plan name -> Stripe price ID (set via env vars)
PLAN_PRICE_MAP: dict[str, str] = {
    "starter":  settings.STRIPE_PRICE_STARTER,
    "pro":      settings.STRIPE_PRICE_PRO,
    "business": settings.STRIPE_PRICE_BUSINESS,
}

# Reverse map: price ID -> plan name (built at import time)
PRICE_PLAN_MAP: dict[str, str] = {v: k for k, v in PLAN_PRICE_MAP.items() if v}


def create_checkout_session(email: str, plan: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session for a subscription and return the session URL."""
    session = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=["card"],
        line_items=[{"price": PLAN_PRICE_MAP[plan], "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"email": email, "plan": plan},
    )
    return session.url


def get_checkout_session(session_id: str) -> stripe.checkout.Session:
    return stripe.checkout.Session.retrieve(session_id)


def verify_webhook(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify Stripe webhook signature and return the parsed event."""
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )


async def handle_checkout_completed(session: dict, supabase) -> None:
    """Generate and email an API key after a successful Stripe checkout."""
    from app.services.api_key_service import generate_api_key
    from app.services.email_service import send_api_key_email

    email: str = session["metadata"]["email"]
    plan: str = session["metadata"]["plan"]
    customer_id: str = getattr(session, "customer", "") or ""
    subscription_id: str = getattr(session, "subscription", "") or ""

    raw_key = await generate_api_key(
        name=email,
        supabase=supabase,
        email=email,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    await send_api_key_email(to_email=email, api_key=raw_key)


async def handle_subscription_deleted(subscription: dict, supabase) -> None:
    """Downgrade an API key to free when its subscription is cancelled."""
    subscription_id: str = subscription["id"]
    await (
        supabase.table("api_keys")
        .update({"plan": "free", "stripe_subscription_id": None})
        .eq("stripe_subscription_id", subscription_id)
        .execute()
    )


async def handle_subscription_updated(subscription: dict, supabase) -> None:
    """Sync the plan on an API key when a subscription changes tier."""
    subscription_id: str = subscription["id"]
    items_obj = getattr(subscription, "items", None)
    items = items_obj.data if items_obj else []
    if not items:
        return

    price_id: str = items[0]["price"]["id"]
    new_plan = PRICE_PLAN_MAP.get(price_id)
    if new_plan is None:
        return

    await (
        supabase.table("api_keys")
        .update({"plan": new_plan})
        .eq("stripe_subscription_id", subscription_id)
        .execute()
    )
