import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    # Path 1: RapidAPI proxy request
    rapidapi_secret = request.headers.get("X-RapidAPI-Proxy-Secret", "")
    if settings.RAPIDAPI_PROXY_SECRET and rapidapi_secret:
        if secrets.compare_digest(rapidapi_secret, settings.RAPIDAPI_PROXY_SECRET):
            return "rapidapi-user"
        raise HTTPException(status_code=401, detail="Invalid RapidAPI proxy secret")

    # Path 2: Direct Bearer token request (unchanged behavior)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not secrets.compare_digest(credentials.credentials, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return "static-user"
