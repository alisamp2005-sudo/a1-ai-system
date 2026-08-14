"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://a1admin:password@postgres:5432/a1_system"
    DB_USER: str = "a1admin"
    DB_PASS: str = "password"
    DB_NAME: str = "a1_system"
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Ollama
    OLLAMA_URL: str = "http://host.docker.internal:11434"

    # Telegram
    TELEGRAM_TOKEN: str = ""
    ADMIN_TELEGRAM_ID: str = "5867249984"

    # ChromaDB
    CHROMA_URL: str = "http://chromadb:8000"

    # App
    APP_ENV: str = "production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    LOG_LEVEL: str = "info"

    # SLA
    SLA_CHECK_INTERVAL_SECONDS: int = 60
    TIMEZONE: str = "Europe/Moscow"
    WORK_HOURS_START: str = "09:00"
    WORK_HOURS_END: str = "18:00"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
