from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.supabase import get_supabase
import hashlib

bearer_scheme = HTTPBearer(auto_error=False)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key — this is what gets stored in the DB."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Accepts either:
      - A Supabase JWT:  Authorization: Bearer <supabase_jwt>
      - An API key:      Authorization: Bearer rp_live_<key>
    Returns the user_id string on success, raises 401 on failure.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    supabase = get_supabase()

    # --- API Key path ---
    if token.startswith("rp_live_") or token.startswith("rp_test_"):
        key_hash = _hash_key(token)
        result = (
            supabase.table("api_keys")
            .select("id, user_id, revoked")
            .eq("key_hash", key_hash)
            .single()
            .execute()
        )
        if not result.data or result.data.get("revoked"):
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        # Update usage stats (fire and forget — don't block on it)
        supabase.table("api_keys").update(
            {"last_used_at": "now()", "request_count": result.data.get("request_count", 0) + 1}
        ).eq("id", result.data["id"]).execute()

        return result.data["user_id"]

    # --- Supabase JWT path ---
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
