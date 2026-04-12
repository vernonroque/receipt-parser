from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.supabase import get_supabase

router = APIRouter()


class TokenRequest(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    id: str
    email: str


@router.post("/verify", response_model=UserResponse)
def verify_token(body: TokenRequest):
    """
    Verify a Supabase JWT and return basic user info.
    Your frontend calls this after Google OAuth to confirm the session is valid.
    """
    supabase = get_supabase()
    try:
        user_response = supabase.auth.get_user(body.access_token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return UserResponse(
            id=user_response.user.id,
            email=user_response.user.email,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
