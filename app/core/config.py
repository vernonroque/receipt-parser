from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Anthropic
    ANTHROPIC_API_KEY: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str  # Server-side only — never expose to client

    # App
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    MAX_FILE_SIZE_MB: int = 10
    MAX_PDF_PAGES: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
