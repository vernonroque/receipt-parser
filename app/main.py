from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import acreate_client

from app.api import parse
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SUPABASE_URL:
        app.state.supabase = await acreate_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )
    else:
        app.state.supabase = None
    yield


app = FastAPI(
    title="Receipt / Invoice Parser API",
    description="Upload an image or PDF receipt/invoice and get structured JSON back.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/api", tags=["Parser"])


@app.get("/health")
def health():
    return {"status": "ok"}
