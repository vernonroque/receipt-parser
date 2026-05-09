import hashlib
import secrets
import time
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

# Cache: key_hash -> (key_id, is_active, expires_monotonic)
_key_cache: dict[str, tuple[str, bool, float]] = {}
_CACHE_TTL = 60.0


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _track_usage(supabase, key_id: str) -> None:
    """Best-effort usage tracking — all exceptions are swallowed."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        await supabase.table("api_keys").update({"last_used_at": now_iso}).eq(
            "id", key_id
        ).execute()
    except Exception:
        pass

    try:
        await supabase.rpc("increment_key_usage", {"key_id": key_id}).execute()
    except Exception:
        pass


async def get_current_user(
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    # Path 1: RapidAPI proxy request
    rapidapi_secret = request.headers.get("X-RapidAPI-Proxy-Secret", "")
    if settings.RAPIDAPI_PROXY_SECRET and rapidapi_secret:
        if secrets.compare_digest(rapidapi_secret, settings.RAPIDAPI_PROXY_SECRET):
            return "rapidapi-user"
        raise HTTPException(status_code=401, detail="Invalid RapidAPI proxy secret")

    # Path 2: Bearer token
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    raw_key = credentials.credentials
    supabase = getattr(request.app.state, "supabase", None)

    # Path 2a: No Supabase configured — fall back to static API_KEY
    if supabase is None:
        if not secrets.compare_digest(raw_key, settings.API_KEY):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return "static-user"

    # Path 2b: Supabase-backed key validation
    key_hash = _hash_key(raw_key)
    now = time.monotonic()

    cached = _key_cache.get(key_hash)
    if cached is not None:
        key_id, is_active, expires = cached
        if now < expires:
            if not is_active:
                raise HTTPException(status_code=401, detail="API key is inactive")
            background_tasks.add_task(_track_usage, supabase, key_id)
            return key_id

    # Cache miss or expired — query Supabase
    try:
        result = (
            await supabase.table("api_keys")
            .select("id, is_active")
            .eq("key_hash", key_hash)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid API key")

    row = result.data
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_id: str = row["id"]
    is_active: bool = row["is_active"]

    _key_cache[key_hash] = (key_id, is_active, now + _CACHE_TTL)

    if not is_active:
        raise HTTPException(status_code=401, detail="API key is inactive")

    background_tasks.add_task(_track_usage, supabase, key_id)
    return key_id
