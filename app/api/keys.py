import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.supabase import get_supabase
from app.services.auth_middleware import get_current_user
from app.models.schemas import APIKey, NewAPIKeyResponse

router = APIRouter()


def _generate_key() -> str:
    """Generate a secure random API key with a recognizable prefix."""
    token = secrets.token_urlsafe(32)
    return f"rp_live_{token}"


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class CreateKeyRequest(BaseModel):
    name: str   # e.g. "Production", "My App", "Testing"


@router.post("/", response_model=NewAPIKeyResponse)
def create_api_key(
    body: CreateKeyRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Create a new API key for the authenticated user.
    The full key is returned ONCE — store it securely. It cannot be retrieved again.
    """
    supabase = get_supabase()

    # Limit keys per user
    existing = supabase.table("api_keys").select("id").eq("user_id", user_id).eq("revoked", False).execute()
    if len(existing.data) >= 10:
        raise HTTPException(status_code=400, detail="Maximum of 10 active API keys allowed.")

    raw_key = _generate_key()
    key_hash = _hash_key(raw_key)
    preview = raw_key[:12] + "..." + raw_key[-4:]

    result = supabase.table("api_keys").insert({
        "user_id": user_id,
        "name": body.name,
        "key_hash": key_hash,
        "key_preview": preview,
        "revoked": False,
        "request_count": 0,
    }).execute()

    row = result.data[0]
    return NewAPIKeyResponse(
        id=row["id"],
        name=row["name"],
        key=raw_key,        # Full key — only returned here, never again
        created_at=row["created_at"],
    )


@router.get("/", response_model=list[APIKey])
def list_api_keys(user_id: str = Depends(get_current_user)):
    """List all active API keys for the authenticated user (previews only)."""
    supabase = get_supabase()
    result = (
        supabase.table("api_keys")
        .select("id, name, key_preview, created_at, last_used_at, request_count")
        .eq("user_id", user_id)
        .eq("revoked", False)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user),
):
    """Revoke (soft-delete) an API key. This cannot be undone."""
    supabase = get_supabase()

    # Verify key belongs to this user before revoking
    existing = (
        supabase.table("api_keys")
        .select("id")
        .eq("id", key_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="API key not found.")

    supabase.table("api_keys").update({"revoked": True}).eq("id", key_id).execute()
    return {"message": "API key revoked successfully."}
