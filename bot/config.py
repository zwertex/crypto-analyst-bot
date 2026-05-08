"""Application configuration loaded from environment variables."""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot settings loaded from .env / environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")
    allowed_user_ids: list[int] = Field(default_factory=list, alias="ALLOWED_USER_IDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> list[int]:
        if v is None or v == "":
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        raise ValueError(f"Cannot parse allowed_user_ids from {v!r}")


def load_settings() -> Settings:
    """Load settings from environment. Separated for easier testing."""
    return Settings()  # type: ignore[call-arg]
