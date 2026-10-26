"""
EdStemBot — Centralised configuration.

All settings are loaded from environment variables (or a .env file).
Access settings via the module-level `settings` singleton:

    from config.settings import settings
    print(settings.ed_course_id)
"""

from __future__ import annotations

import logging
from typing import Literal

import os
from pydantic import Field, field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel

    class BaseSettings(BaseModel):  # type: ignore[no-redef]
        def __init__(self, **values):
            env_vals = {}
            for field_name, field in self.model_fields.items():
                val = os.getenv(field_name.upper()) or os.getenv(field_name)
                if val is not None:
                    if field.annotation == int:
                        try:
                            env_vals[field_name] = int(val)
                        except ValueError:
                            pass
                    else:
                        env_vals[field_name] = val
            env_vals.update(values)
            super().__init__(**env_vals)

    def SettingsConfigDict(**kwargs):  # type: ignore
        return kwargs


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── EdStem ──────────────────────────────────────────────────────────────
    ed_api_token: str = Field(default="", description="EdStem personal API token")
    ed_course_id: int = Field(default=0, description="EdStem course ID (from URL)")
    ed_base_url: str = Field(
        default="https://us.edstem.org",
        description="EdStem regional base URL",
    )

    # ── LLM ─────────────────────────────────────────────────────────────────
    llm_provider: Literal["openai", "gemini", "claude"] = Field(
        default="openai",
        description="Active LLM provider",
    )
    openai_api_key: str = Field(default="", description="OpenAI API key")
    google_api_key: str = Field(default="", description="Google Gemini API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./edstembot.db",
        description="SQLAlchemy async database URL",
    )

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field(
        default="./chroma_db",
        description="Directory for ChromaDB persistent storage",
    )
    chroma_collection: str = Field(
        default="course_materials",
        description="Name of the ChromaDB collection",
    )

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformers model name",
    )

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: int = Field(default=8000)

    # ── Chrome extension ──────────────────────────────────────────────────────
    extension_secret: str = Field(
        default="",
        description="Shared secret the Chrome extension sends as X-EdStemBot-Key",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")

    @field_validator("llm_provider")
    @classmethod
    def validate_provider_key(cls, v: str, info) -> str:  # noqa: ANN001
        """Warn if the selected provider has no API key."""
        # Validation at import time is tricky because other fields may not
        # be populated yet — we do a runtime check in get_llm_provider().
        return v

    @property
    def log_level_int(self) -> int:
        return getattr(logging, self.log_level.upper(), logging.INFO)


# Module-level singleton — import this everywhere
settings = Settings()
