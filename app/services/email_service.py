import asyncio

import resend

from app.core.config import settings


async def send_api_key_email(to_email: str, api_key: str) -> None:
    """Send the generated API key to the user via Resend. Raises on failure."""
    resend.api_key = settings.RESEND_API_KEY

    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Your Receipt Parser API Key</h2>
      <p>Here is your API key. <strong>Save it now — it will not be shown again.</strong></p>
      <pre style="background:#f4f4f4;padding:12px;border-radius:4px;font-size:14px;">{api_key}</pre>
      <p>To authenticate, include it as a Bearer token in your requests:</p>
      <pre style="background:#f4f4f4;padding:12px;border-radius:4px;font-size:13px;">Authorization: Bearer {api_key}</pre>
      <p style="color:#888;font-size:12px;">If you did not request this key, you can ignore this email.</p>
    </div>
    """

    text = (
        f"Your Receipt Parser API key:\n\n{api_key}\n\n"
        "Save this now — it will not be shown again.\n\n"
        "Use it as a Bearer token: Authorization: Bearer <key>"
    )

    params: resend.Emails.SendParams = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": "Your Receipt Parser API Key",
        "html": html,
        "text": text,
    }

    await asyncio.to_thread(resend.Emails.send, params)
