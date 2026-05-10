import hashlib
import secrets

from app.services.auth_middleware import _key_cache


async def generate_api_key(name: str, supabase, email: str = "") -> str:
    """Generate a new API key, store its hash in Supabase, and return the raw key.

    The raw key is returned exactly once — it is never recoverable after this call.
    """
    raw_key = "rp_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    row: dict = {"name": name, "key_hash": key_hash, "key_prefix": key_prefix}
    if email:
        row["email"] = email

    await supabase.table("api_keys").insert(row).execute()

    return raw_key


async def list_keys(supabase) -> list[dict]:
    """Return a list of all API key records (without the hash)."""
    result = (
        await supabase.table("api_keys")
        .select("id, name, key_prefix, is_active, created_at, last_used_at, request_count")
        .execute()
    )
    return result.data


async def revoke_key(key_id: str, supabase) -> None:
    """Deactivate an API key by ID and evict it from the in-process cache."""
    await supabase.table("api_keys").update({"is_active": False}).eq(
        "id", key_id
    ).execute()

    # Evict any cached entry for this key_id so auth fails immediately.
    stale_hashes = [
        key_hash
        for key_hash, (cached_id, _, _) in _key_cache.items()
        if cached_id == key_id
    ]
    for key_hash in stale_hashes:
        _key_cache.pop(key_hash, None)
