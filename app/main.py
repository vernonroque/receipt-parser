from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import parse, auth, keys
from app.core.config import settings

app = FastAPI(
    title="Receipt / Invoice Parser API",
    description="Upload an image or PDF receipt/invoice and get structured JSON back.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(keys.router, prefix="/keys", tags=["API Keys"])
app.include_router(parse.router, prefix="/api", tags=["Parser"])


@app.get("/health")
def health():
    return {"status": "ok"}
