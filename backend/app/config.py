"""Runtime configuration for the API."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings with portfolio-demo safe defaults."""

    app_name: str = "ResolveAI Support Platform API"
    app_version: str = "1.0.0"
    demo_mode: bool = True
    fallback_on_ai_error: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini/gemini-2.0-flash"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "https://resolveai-support-platform.vercel.app",
            "https://resolveai-support-prototype.amarasfaw7.chatgpt.site",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        """Accept either JSON arrays or comma-separated origin strings."""
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()

