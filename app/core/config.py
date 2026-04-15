from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Anthropic
    ANTHROPIC_API_KEY: str

    # Auth
    API_KEY: str
    RAPIDAPI_PROXY_SECRET: str = ""

    # App
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    MAX_FILE_SIZE_MB: int = 10
    MAX_PDF_PAGES: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
