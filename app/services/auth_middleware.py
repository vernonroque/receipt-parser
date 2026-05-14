import hashlib
import secrets
import time
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.schemas import PLAN_LIMITS

bearer_scheme = HTTPBearer(auto_error=False)

# Cache: key_hash -> (key_id, is_active, plan, monthly_count, monthly_reset_iso, expires_monotonic)
_key_cache: dict[str, tuple[str, bool, str, int, str, float]] = {}
_CACHE_TTL = 60.0

# In-process hourly rate limiter: key_id -> (count, window_start_monotonic)
_hourly_counters: dict[str, tuple[int, float]] = {}
_HOUR = 3600.0


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _check_quotas(key_id: str, plan: str, monthly_count: int, monthly_reset_iso: str) -> None:
    """Raise 429 if the key has exceeded its monthly quota or hourly rate limit."""
    limits = PLAN_LIMITS[plan]

    # Monthly quota: detect if reset_at is from a prior month
    now_utc = datetime.now(timezone.utc)
    try:
        reset_dt = datetime.fromisoformat(monthly_reset_iso)
        if reset_dt.tzinfo is None:
            reset_dt = reset_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        reset_dt = now_utc

    current_month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    effective_count = monthly_count if reset_dt >= current_month_start else 0

    if effective_count >= limits["monthly"]:
        raise HTTPException(status_code=429, detail="Monthly request quota exceeded")

    # Hourly rate limit (in-process)
    hourly_limit = limits["hourly"]
    if hourly_limit is not None:
        now_mono = time.monotonic()
        entry = _hourly_counters.get(key_id)
        if entry is None or (now_mono - entry[1]) >= _HOUR:
            _hourly_counters[key_id] = (1, now_mono)
        else:
            count, window_start = entry
            if count >= hourly_limit:
                raise HTTPException(status_code=429, detail="Hourly rate limit exceeded")
            _hourly_counters[key_id] = (count + 1, window_start)


async def _track_usage(supabase, key_id: str) -> None:
    """Best-effort usage tracking — all exceptions are swallowed."""
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
        key_id, is_active, plan, monthly_count, monthly_reset_iso, expires = cached
        if now < expires:
            if not is_active:
                raise HTTPException(status_code=401, detail="API key is inactive")
            _check_quotas(key_id, plan, monthly_count, monthly_reset_iso)
            background_tasks.add_task(_track_usage, supabase, key_id)
            return key_id

    # Cache miss or expired — query Supabase
    try:
        result = (
            await supabase.table("api_keys")
            .select("id, is_active, plan, monthly_request_count, monthly_reset_at")
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
    plan: str = row.get("plan", "free")
    monthly_count: int = row.get("monthly_request_count", 0)
    monthly_reset_iso: str = row.get("monthly_reset_at", "") or ""

    _key_cache[key_hash] = (key_id, is_active, plan, monthly_count, monthly_reset_iso, now + _CACHE_TTL)

    if not is_active:
        raise HTTPException(status_code=401, detail="API key is inactive")

    _check_quotas(key_id, plan, monthly_count, monthly_reset_iso)
    background_tasks.add_task(_track_usage, supabase, key_id)
    return key_id
