import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not secrets.compare_digest(credentials.credentials, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return "static-user"
