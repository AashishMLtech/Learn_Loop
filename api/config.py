"""API Configuration and Environment Settings Module.

Purpose:
    Loads, validates, and manages environment configuration settings for the FastAPI
    service and background workers, including API keys, database URLs, CORS origins,
    and rate limit parameters.

Inputs/Outputs:
    Inputs: Operating system environment variables.
    Outputs: Immutable or typed settings dataclass/attributes.

What it must NOT do:
    - Must NOT hardcode secrets or production API keys.
    - Must NOT execute generation or database mutations.
"""
import os
from typing import List


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.api_key: str = os.getenv("API_KEY", "default-insecure-api-key")
        self.admin_api_key: str = os.getenv("ADMIN_API_KEY", "default-admin-secret-xyz")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./lesson_generator.db")
        self.rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
        self.api_host: str = os.getenv("API_HOST", "0.0.0.0")
        self.api_port: int = int(os.getenv("API_PORT", "8000"))
        self.ui_port: int = int(os.getenv("UI_PORT", "8080"))

        raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
        self.cors_origins: List[str] = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]


settings = Settings()
