"""Startup configuration validation using Pydantic BaseSettings.

Validates critical configuration values at startup to provide fail-fast behavior.
This is an ADDITIONAL validation layer — it does NOT replace PersistentConfig.
"""

import os

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Validate database configuration."""

    DATABASE_URL: str = "sqlite:///./data/bcgpt.db"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        valid_schemes = ("sqlite://", "postgresql://", "postgres://")
        if not any(v.startswith(s) for s in valid_schemes):
            raise ValueError(f"DATABASE_URL must start with one of {valid_schemes}")
        return v

    model_config = {"extra": "ignore"}


class ServerSettings(BaseSettings):
    """Validate server configuration."""

    PORT: int = int(os.environ.get("PORT", "8090"))
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    WORKERS: int = int(os.environ.get("WORKERS", "1"))

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be between 1 and 65535, got {v}")
        return v

    model_config = {"extra": "ignore"}


class RAGSettings(BaseSettings):
    """Validate RAG configuration."""

    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100

    @field_validator("CHUNK_SIZE")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        if v < 50:
            raise ValueError(f"CHUNK_SIZE must be >= 50, got {v}")
        if v > 10000:
            raise ValueError(f"CHUNK_SIZE must be <= 10000, got {v}")
        return v

    @field_validator("CHUNK_OVERLAP")
    @classmethod
    def validate_chunk_overlap(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"CHUNK_OVERLAP must be >= 0, got {v}")
        return v

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.CHUNK_OVERLAP}) must be less than CHUNK_SIZE ({self.CHUNK_SIZE})"
            )
        return self

    model_config = {"extra": "ignore"}


class SecuritySettings(BaseSettings):
    """Validate security configuration."""

    BCGPT_SECRET_KEY: str = ""

    @field_validator("BCGPT_SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v:
            # Warning only — don't fail startup for dev
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "BCGPT_SECRET_KEY is not set. Using insecure default. "
                "Set this for production deployments."
            )
        elif len(v) < 16:
            raise ValueError("BCGPT_SECRET_KEY must be at least 16 characters")
        return v

    model_config = {"extra": "ignore"}


def validate_settings() -> list[str]:
    """Validate all settings groups. Returns list of warnings.
    Raises ValueError on critical validation failures."""
    warnings = []

    try:
        DatabaseSettings()
    except Exception as e:
        raise ValueError(f"Database configuration error: {e}") from e

    try:
        ServerSettings()
    except Exception as e:
        raise ValueError(f"Server configuration error: {e}") from e

    try:
        RAGSettings()
    except Exception as e:
        raise ValueError(f"RAG configuration error: {e}") from e

    try:
        SecuritySettings()
    except Exception as e:
        warnings.append(str(e))

    return warnings
