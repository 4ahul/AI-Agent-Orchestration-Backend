"""
Centralized application configuration using pydantic-settings.
All env vars are type-safe, validated at startup.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "AI Agent Orchestrator"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # ── Database ───────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/agent_db"
    SYNC_DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/agent_db"

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── LLM Providers ─────────────────────────────────────────────
    # ── Groq (for free Llama3 access) ─────────────────────────────
    GROQ_API_KEY: str | None = None

    # ── Gemini (Free Tier fallback) ──────────────────────────────
    GOOGLE_API_KEY: str | None = None

    # ── Email ─────────────────────────────────────────────────────
    EMAIL_PROVIDER: Literal["smtp", "sendgrid"] = "smtp"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "AI Agent Orchestrator"
    SMTP_FROM_EMAIL: str = ""
    SENDGRID_API_KEY: str = ""

    # ── File Upload ───────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf"

    # ── Worker / Agents ───────────────────────────────────────────
    CELERY_CONCURRENCY: int = 4
    AGENT_TIMEOUT_SECONDS: int = 600

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
