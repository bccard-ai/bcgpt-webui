"""
bcgpt.config — Central configuration for the BCGPT platform.

This module provides:
  - :class:`PersistentConfig` — Generic config value backed by the DB.
  - :class:`AppConfig`        — Redis-backed config proxy with transparent attr access.
  - Module-level config variables consumed throughout the application.

Import-time side effects (Alembic + config.json migration + DB read) run by
default for backward compatibility.  Set ``BCGPT_SKIP_IMPORT_TIME_MIGRATIONS``
to suppress them — ``CONFIG_DATA`` then falls back to ``DEFAULT_CONFIG``.
See ``BACKEND_ARCHITECTURE_TESTABILITY_PLAN_2026-06-23.md`` §5 Phase 1.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import redis
from datetime import datetime
from pathlib import Path
from typing import Generic, Optional, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, Integer, func
from sqlalchemy.exc import OperationalError

from bcgpt.env import (
    DATA_DIR,
    DATABASE_URL,
    ENV,
    REDIS_URL,
    REDIS_SENTINEL_HOSTS,
    REDIS_SENTINEL_PORT,
    FRONTEND_BUILD_DIR,
    OFFLINE_MODE,
    BCGPT_DIR,
    BCGPT_AUTH,
    BCGPT_FAVICON_URL,
    BCGPT_APP_NAME,
    log,
)
from bcgpt.internal import Base, get_db
from bcgpt.utils import get_redis_connection

# ---------------------------------------------------------------------------
# Logging filter — suppress /health access lines
# ---------------------------------------------------------------------------


class EndpointFilter(logging.Filter):
    """Suppress uvicorn access logs for ``/health``."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------


class Config(Base):  # type: ignore[misc]
    """SQLAlchemy model for the ``config`` table."""

    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _load_json_config() -> dict:
    """Load the legacy ``config.json`` from the data directory."""
    with open(f"{DATA_DIR}/config.json", "r") as fh:
        return json.load(fh)


def save_to_db(data: dict) -> None:
    """Persist *data* into the ``config`` table (upsert)."""
    with get_db() as db:
        existing = db.query(Config).first()
        if not existing:
            db.add(Config(data=data, version=0))
        else:
            existing.data = data
            existing.updated_at = datetime.now()
            db.add(existing)
        db.commit()


def reset_config() -> None:
    """Delete all rows from the ``config`` table."""
    with get_db() as db:
        db.query(Config).delete()
        db.commit()


def run_migrations() -> None:
    """Execute Alembic migrations to bring the DB schema to ``head``."""
    log.info("Running migrations")
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig(BCGPT_DIR / "alembic.ini")
        alembic_cfg.set_main_option("script_location", str(BCGPT_DIR / "migrations"))
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        log.exception(f"Error running migrations: {exc}")


def migrate_json_config() -> None:
    """One-time migration of ``config.json`` → database.

    If ``{DATA_DIR}/config.json`` exists it is loaded, written to the DB,
    and renamed to ``old_config.json``.
    """
    config_path = f"{DATA_DIR}/config.json"
    if os.path.exists(config_path):
        data = _load_json_config()
        save_to_db(data)
        os.rename(config_path, f"{DATA_DIR}/old_config.json")


# ---------------------------------------------------------------------------
# Default config (used when the DB has no rows)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "version": 0,
    "mcp": {
        "enabled": False,
        "servers": [],
        "allowed_hosts": [],
        "builtins_enabled": ["time"],
    },
    "ui": {
        "default_locale": "",
        "prompt_suggestions": [
            {
                "title": ["Study Helper", "Vocabulary Building for College Prep"],
                "content": "Help me study vocabulary: Create fill-in-the-blank sentences and I'll choose the right words.",
            },
            {
                "title": ["Idea Suggestions", "Creative Ways to Use Kids' Artwork"],
                "content": "Suggest 5 creative ways to repurpose children's artwork. It's a shame to throw them away, but there are too many taking up space.",
            },
            {
                "title": ["Fun Story", "About the Roman Empire"],
                "content": "Tell me a fascinating story about the Roman Empire.",
            },
            {
                "title": ["Code Sample", "Website Sticky Header"],
                "content": "Show me the CSS and JavaScript code for creating a sticky header on a website.",
            },
            {
                "title": [
                    "Stock Options Explained",
                    "For Those Already Familiar with Trading",
                ],
                "content": "Explain options trading in simple terms for someone already familiar with stock trading.",
            },
            {
                "title": ["Overcoming Procrastination", "Effective Tips"],
                "content": "Ask me when I tend to procrastinate the most, and suggest ways to overcome it.",
            },
            {
                "title": [
                    "Grammar Check",
                    "Sentence Refinement for Better Readability",
                ],
                "content": 'Check the grammar and clarity of the following sentence: "[sentence]". Rewrite it to improve readability while keeping the original meaning.',
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# CONFIG_DATA — the live in-memory config tree
# ---------------------------------------------------------------------------


def get_config() -> dict:
    """Return the latest config dict from the database (or the default).

    The DB read is tolerant of a not-yet-provisioned ``config`` table: during
    an in-memory test import (or a mid-migration startup window) the table may
    not exist yet, in which case we fall back to ``DEFAULT_CONFIG`` instead of
    crashing the whole import. Other DB errors (connection failures, etc.) still
    propagate. In normal startup ``run_migrations()`` has already created the
    table, so this branch is not taken.
    """
    try:
        with get_db() as db:
            entry = db.query(Config).order_by(Config.id.desc()).first()
            return entry.data if entry else DEFAULT_CONFIG
    except OperationalError as e:
        msg = str(e).lower()
        if "no such table" in msg or "does not exist" in msg:
            log.warning("config table not provisioned; using DEFAULT_CONFIG: %s", e)
            return DEFAULT_CONFIG
        raise


def get_config_value(config_path: str):
    """Dotted-path lookup into :data:`CONFIG_DATA`.

    Example: ``get_config_value("ui.name")`` → ``CONFIG_DATA["ui"]["name"]``.
    """
    parts = config_path.split(".")
    cur = CONFIG_DATA
    for key in parts:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


# Import-time side effects — guarded by BCGPT_SKIP_IMPORT_TIME_MIGRATIONS.
# When unset (default): migrations run as before (backward compat).
# When set: skip migrations, use DEFAULT_CONFIG (import-safe contract).
if not os.environ.get("BCGPT_SKIP_IMPORT_TIME_MIGRATIONS"):
    run_migrations()
    migrate_json_config()
    CONFIG_DATA: dict = get_config()
else:
    CONFIG_DATA: dict = DEFAULT_CONFIG


def save_config(config: dict) -> bool:
    """Persist *config* to DB and refresh all registered PersistentConfig objects."""
    global CONFIG_DATA
    try:
        save_to_db(config)
        CONFIG_DATA = config
        for item in PERSISTENT_CONFIG_REGISTRY:
            item.update()
    except Exception as exc:
        log.exception(exc)
        return False
    return True


# ---------------------------------------------------------------------------
# PersistentConfig
# ---------------------------------------------------------------------------

T = TypeVar("T")

PERSISTENT_CONFIG_REGISTRY: list[PersistentConfig] = []  # type: ignore[name-defined]


class PersistentConfig(Generic[T]):
    """A typed config value that auto-persists to the database.

    Resolution order:
      1. Value stored in the DB under ``config_path`` (if present)
      2. Fallback to ``env_value`` (typically from an env var)
    """

    def __init__(self, env_name: str, config_path: str, env_value: T) -> None:
        self.env_name = env_name
        self.config_path = config_path
        self.env_value: T = env_value
        self.config_value = get_config_value(config_path)

        if self.config_value is not None:
            log.info(f"'{env_name}' loaded from the latest database entry")
            self.value: T = self.config_value
        else:
            self.value = env_value

        PERSISTENT_CONFIG_REGISTRY.append(self)

    def __str__(self) -> str:
        return str(self.value)

    @property
    def __dict__(self):  # type: ignore[override]
        raise TypeError(
            "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
        )

    def __getattribute__(self, item: str):
        if item == "__dict__":
            raise TypeError(
                "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
            )
        return super().__getattribute__(item)

    def update(self) -> None:
        """Refresh from DB if a value exists for our path."""
        new_value = get_config_value(self.config_path)
        if new_value is not None:
            self.value = new_value
            log.info(f"Updated {self.env_name} to new value {self.value}")

    def save(self) -> None:
        """Write the current ``.value`` back to the DB config tree."""
        log.info(f"Saving '{self.env_name}' to the database")
        parts = self.config_path.split(".")
        sub = CONFIG_DATA
        for key in parts[:-1]:
            if key not in sub:
                sub[key] = {}
            sub = sub[key]
        sub[parts[-1]] = self.value
        save_to_db(CONFIG_DATA)
        self.config_value = self.value


# ---------------------------------------------------------------------------
# AppConfig — Redis-backed transparent config proxy
# ---------------------------------------------------------------------------


class AppConfig:
    """Attribute-proxy that syncs config changes through Redis.

    Usage::

        app_config = AppConfig(redis_url="redis://…")
        app_config.feature_x = PersistentConfig("FEATURE_X", "feature.x", False)
        app_config.feature_x = True   # saves to DB + publishes to Redis
    """

    _state: dict[str, PersistentConfig]
    _redis: Optional[redis.Redis]

    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_sentinels: Optional[list] = None,
    ) -> None:
        if redis_sentinels is None:
            redis_sentinels = []
        super().__setattr__("_state", {})
        if redis_url:
            super().__setattr__(
                "_redis",
                get_redis_connection(redis_url, redis_sentinels, decode_responses=True),
            )
        else:
            super().__setattr__("_redis", None)

    def __setattr__(self, key: str, value) -> None:
        if isinstance(value, PersistentConfig):
            self._state[key] = value
        elif key in self._state:
            self._state[key].value = value
            self._state[key].save()
            if self._redis:
                redis_key = f"bcgpt:config:{key}"
                self._redis.set(redis_key, json.dumps(self._state[key].value))
        else:
            raise AttributeError(
                f"Config key '{key}' not registered. "
                f"Assign a PersistentConfig object first to register it. "
                f"Got type={type(value).__name__!r}, value={value!r}"
            )

    def __getattr__(self, key: str):
        if key not in self._state:
            raise AttributeError(f"Config key '{key}' not found")

        if self._redis:
            redis_key = f"bcgpt:config:{key}"
            redis_value = self._redis.get(redis_key)
            if redis_value is not None:
                try:
                    decoded = json.loads(redis_value)
                    if self._state[key].value != decoded:
                        self._state[key].value = decoded
                        log.info(f"Updated {key} from Redis: {decoded}")
                except json.JSONDecodeError:
                    log.error(f"Invalid JSON format in Redis for {key}: {redis_value}")

        return self._state[key].value


# ---------------------------------------------------------------------------
# Helper: parse boolean env vars
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: str = "False") -> bool:
    return os.environ.get(name, default).lower() == "true"


def _env_int(name: str, default: str = "0") -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: str = "0.0") -> float:
    return float(os.environ.get(name, default))


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_str_or_none(name: str) -> Optional[str]:
    return os.environ.get(name, None)


# ===========================================================================
# SECTION: Auth Configuration
# ===========================================================================

ENABLE_API_KEY = PersistentConfig(
    "ENABLE_API_KEY",
    "auth.api_key.enable",
    _env_bool("ENABLE_API_KEY", "True"),
)

ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = PersistentConfig(
    "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS",
    "auth.api_key.endpoint_restrictions",
    _env_bool("ENABLE_API_KEY_ENDPOINT_RESTRICTIONS", "False"),
)

API_KEY_ALLOWED_ENDPOINTS = PersistentConfig(
    "API_KEY_ALLOWED_ENDPOINTS",
    "auth.api_key.allowed_endpoints",
    _env_str("API_KEY_ALLOWED_ENDPOINTS", ""),
)

JWT_EXPIRES_IN = PersistentConfig(
    "JWT_EXPIRES_IN",
    "auth.jwt_expiry",
    _env_str("JWT_EXPIRES_IN", "7d"),
)


# ===========================================================================
# SECTION: OAuth Configuration
# ===========================================================================

ENABLE_OAUTH_SIGNUP = PersistentConfig(
    "ENABLE_OAUTH_SIGNUP",
    "oauth.enable_signup",
    _env_bool("ENABLE_OAUTH_SIGNUP", "False"),
)

OAUTH_MERGE_ACCOUNTS_BY_EMAIL = PersistentConfig(
    "OAUTH_MERGE_ACCOUNTS_BY_EMAIL",
    "oauth.merge_accounts_by_email",
    _env_bool("OAUTH_MERGE_ACCOUNTS_BY_EMAIL", "False"),
)

OAUTH_PROVIDERS: dict = {}

# --- Google OAuth ---

GOOGLE_CLIENT_ID = PersistentConfig(
    "GOOGLE_CLIENT_ID",
    "oauth.google.client_id",
    _env_str("GOOGLE_CLIENT_ID"),
)

GOOGLE_CLIENT_SECRET = PersistentConfig(
    "GOOGLE_CLIENT_SECRET",
    "oauth.google.client_secret",
    _env_str("GOOGLE_CLIENT_SECRET"),
)

GOOGLE_OAUTH_SCOPE = PersistentConfig(
    "GOOGLE_OAUTH_SCOPE",
    "oauth.google.scope",
    _env_str("GOOGLE_OAUTH_SCOPE", "openid email profile"),
)

GOOGLE_REDIRECT_URI = PersistentConfig(
    "GOOGLE_REDIRECT_URI",
    "oauth.google.redirect_uri",
    _env_str("GOOGLE_REDIRECT_URI"),
)

# --- Microsoft OAuth ---

MICROSOFT_CLIENT_ID = PersistentConfig(
    "MICROSOFT_CLIENT_ID",
    "oauth.microsoft.client_id",
    _env_str("MICROSOFT_CLIENT_ID"),
)

MICROSOFT_CLIENT_SECRET = PersistentConfig(
    "MICROSOFT_CLIENT_SECRET",
    "oauth.microsoft.client_secret",
    _env_str("MICROSOFT_CLIENT_SECRET"),
)

MICROSOFT_CLIENT_TENANT_ID = PersistentConfig(
    "MICROSOFT_CLIENT_TENANT_ID",
    "oauth.microsoft.tenant_id",
    _env_str("MICROSOFT_CLIENT_TENANT_ID"),
)

MICROSOFT_OAUTH_SCOPE = PersistentConfig(
    "MICROSOFT_OAUTH_SCOPE",
    "oauth.microsoft.scope",
    _env_str("MICROSOFT_OAUTH_SCOPE", "openid email profile"),
)

MICROSOFT_REDIRECT_URI = PersistentConfig(
    "MICROSOFT_REDIRECT_URI",
    "oauth.microsoft.redirect_uri",
    _env_str("MICROSOFT_REDIRECT_URI"),
)

# --- GitHub OAuth ---

GITHUB_CLIENT_ID = PersistentConfig(
    "GITHUB_CLIENT_ID",
    "oauth.github.client_id",
    _env_str("GITHUB_CLIENT_ID"),
)

GITHUB_CLIENT_SECRET = PersistentConfig(
    "GITHUB_CLIENT_SECRET",
    "oauth.github.client_secret",
    _env_str("GITHUB_CLIENT_SECRET"),
)

GITHUB_CLIENT_SCOPE = PersistentConfig(
    "GITHUB_CLIENT_SCOPE",
    "oauth.github.scope",
    _env_str("GITHUB_CLIENT_SCOPE", "user:email"),
)

GITHUB_CLIENT_REDIRECT_URI = PersistentConfig(
    "GITHUB_CLIENT_REDIRECT_URI",
    "oauth.github.redirect_uri",
    _env_str("GITHUB_CLIENT_REDIRECT_URI"),
)

# --- OIDC ---

OAUTH_CLIENT_ID = PersistentConfig(
    "OAUTH_CLIENT_ID",
    "oauth.oidc.client_id",
    _env_str("OAUTH_CLIENT_ID"),
)

OAUTH_CLIENT_SECRET = PersistentConfig(
    "OAUTH_CLIENT_SECRET",
    "oauth.oidc.client_secret",
    _env_str("OAUTH_CLIENT_SECRET"),
)

OPENID_PROVIDER_URL = PersistentConfig(
    "OPENID_PROVIDER_URL",
    "oauth.oidc.provider_url",
    _env_str("OPENID_PROVIDER_URL"),
)

OPENID_REDIRECT_URI = PersistentConfig(
    "OPENID_REDIRECT_URI",
    "oauth.oidc.redirect_uri",
    _env_str("OPENID_REDIRECT_URI"),
)

OAUTH_SCOPES = PersistentConfig(
    "OAUTH_SCOPES",
    "oauth.oidc.scopes",
    _env_str("OAUTH_SCOPES", "openid email profile"),
)

OAUTH_PROVIDER_NAME = PersistentConfig(
    "OAUTH_PROVIDER_NAME",
    "oauth.oidc.provider_name",
    _env_str("OAUTH_PROVIDER_NAME", "SSO"),
)

OAUTH_USERNAME_CLAIM = PersistentConfig(
    "OAUTH_USERNAME_CLAIM",
    "oauth.oidc.username_claim",
    _env_str("OAUTH_USERNAME_CLAIM", "name"),
)

OAUTH_PICTURE_CLAIM = PersistentConfig(
    "OAUTH_PICTURE_CLAIM",
    "oauth.oidc.avatar_claim",
    _env_str("OAUTH_PICTURE_CLAIM", "picture"),
)

OAUTH_EMAIL_CLAIM = PersistentConfig(
    "OAUTH_EMAIL_CLAIM",
    "oauth.oidc.email_claim",
    _env_str("OAUTH_EMAIL_CLAIM", "email"),
)

OAUTH_GROUPS_CLAIM = PersistentConfig(
    "OAUTH_GROUPS_CLAIM",
    "oauth.oidc.group_claim",
    _env_str("OAUTH_GROUP_CLAIM", "groups"),
)

ENABLE_OAUTH_ROLE_MANAGEMENT = PersistentConfig(
    "ENABLE_OAUTH_ROLE_MANAGEMENT",
    "oauth.enable_role_mapping",
    _env_bool("ENABLE_OAUTH_ROLE_MANAGEMENT", "False"),
)

ENABLE_OAUTH_GROUP_MANAGEMENT = PersistentConfig(
    "ENABLE_OAUTH_GROUP_MANAGEMENT",
    "oauth.enable_group_mapping",
    _env_bool("ENABLE_OAUTH_GROUP_MANAGEMENT", "False"),
)

OAUTH_ROLES_CLAIM = PersistentConfig(
    "OAUTH_ROLES_CLAIM",
    "oauth.roles_claim",
    _env_str("OAUTH_ROLES_CLAIM", "roles"),
)

OAUTH_ALLOWED_ROLES = PersistentConfig(
    "OAUTH_ALLOWED_ROLES",
    "oauth.allowed_roles",
    [r.strip() for r in _env_str("OAUTH_ALLOWED_ROLES", "user,admin").split(",")],
)

OAUTH_ADMIN_ROLES = PersistentConfig(
    "OAUTH_ADMIN_ROLES",
    "oauth.admin_roles",
    [r.strip() for r in _env_str("OAUTH_ADMIN_ROLES", "admin").split(",")],
)

OAUTH_ALLOWED_DOMAINS = PersistentConfig(
    "OAUTH_ALLOWED_DOMAINS",
    "oauth.allowed_domains",
    [d.strip() for d in _env_str("OAUTH_ALLOWED_DOMAINS", "*").split(",")],
)


def load_oauth_providers() -> None:
    """Populate :data:`OAUTH_PROVIDERS` from the configured OAuth credentials."""
    OAUTH_PROVIDERS.clear()

    if GOOGLE_CLIENT_ID.value and GOOGLE_CLIENT_SECRET.value:

        def google_oauth_register(client):
            client.register(
                name="google",
                client_id=GOOGLE_CLIENT_ID.value,
                client_secret=GOOGLE_CLIENT_SECRET.value,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": GOOGLE_OAUTH_SCOPE.value},
                redirect_uri=GOOGLE_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["google"] = {
            "redirect_uri": GOOGLE_REDIRECT_URI.value,
            "register": google_oauth_register,
        }

    if (
        MICROSOFT_CLIENT_ID.value
        and MICROSOFT_CLIENT_SECRET.value
        and MICROSOFT_CLIENT_TENANT_ID.value
    ):

        def microsoft_oauth_register(client):
            client.register(
                name="microsoft",
                client_id=MICROSOFT_CLIENT_ID.value,
                client_secret=MICROSOFT_CLIENT_SECRET.value,
                server_metadata_url=f"https://login.microsoftonline.com/{MICROSOFT_CLIENT_TENANT_ID.value}/v2.0/.well-known/openid-configuration",
                client_kwargs={"scope": MICROSOFT_OAUTH_SCOPE.value},
                redirect_uri=MICROSOFT_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["microsoft"] = {
            "redirect_uri": MICROSOFT_REDIRECT_URI.value,
            "picture_url": "https://graph.microsoft.com/v1.0/me/photo/$value",
            "register": microsoft_oauth_register,
        }

    if GITHUB_CLIENT_ID.value and GITHUB_CLIENT_SECRET.value:

        def github_oauth_register(client):
            client.register(
                name="github",
                client_id=GITHUB_CLIENT_ID.value,
                client_secret=GITHUB_CLIENT_SECRET.value,
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com",
                userinfo_endpoint="https://api.github.com/user",
                client_kwargs={"scope": GITHUB_CLIENT_SCOPE.value},
                redirect_uri=GITHUB_CLIENT_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["github"] = {
            "redirect_uri": GITHUB_CLIENT_REDIRECT_URI.value,
            "register": github_oauth_register,
            "sub_claim": "id",
        }

    if (
        OAUTH_CLIENT_ID.value
        and OAUTH_CLIENT_SECRET.value
        and OPENID_PROVIDER_URL.value
    ):

        def oidc_oauth_register(client):
            client.register(
                name="oidc",
                client_id=OAUTH_CLIENT_ID.value,
                client_secret=OAUTH_CLIENT_SECRET.value,
                server_metadata_url=OPENID_PROVIDER_URL.value,
                client_kwargs={"scope": OAUTH_SCOPES.value},
                redirect_uri=OPENID_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["oidc"] = {
            "name": OAUTH_PROVIDER_NAME.value,
            "redirect_uri": OPENID_REDIRECT_URI.value,
            "register": oidc_oauth_register,
        }


load_oauth_providers()


# ===========================================================================
# SECTION: Static Files & Branding
# ===========================================================================

STATIC_DIR = Path(os.getenv("STATIC_DIR", BCGPT_DIR / "static")).resolve()


def copy_static_files() -> None:
    """Copy frontend static assets into :data:`STATIC_DIR`.

    Separated from module level so callers can choose when this happens.
    """
    src_dir = FRONTEND_BUILD_DIR / "static"
    if not src_dir.exists():
        return

    for file_path in src_dir.glob("**/*"):
        if not file_path.is_file():
            continue
        target = STATIC_DIR / file_path.relative_to(src_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(file_path, target)
        except Exception as exc:
            logging.error(f"An error occurred: {exc}")

    # Copy specific well-known assets
    for asset_name in ("favicon.png", "splash.png", "loader.js"):
        asset_src = src_dir / asset_name
        if asset_src.exists():
            try:
                shutil.copyfile(asset_src, STATIC_DIR / asset_name)
            except Exception as exc:
                logging.error(f"An error occurred: {exc}")


# Execute at import time to preserve original behaviour.
copy_static_files()

# CUSTOM_NAME remote branding fetch — deliberately REMOVED (security risk).
# If you need custom branding, set assets directly in STATIC_DIR.
CUSTOM_NAME = os.environ.get("CUSTOM_NAME", "")


# ===========================================================================
# SECTION: License Key
# ===========================================================================

LICENSE_KEY = os.environ.get("LICENSE_KEY", "")


# ===========================================================================
# SECTION: Storage Provider
# ===========================================================================

STORAGE_PROVIDER = os.environ.get("STORAGE_PROVIDER", "local")

S3_ACCESS_KEY_ID = _env_str_or_none("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = _env_str_or_none("S3_SECRET_ACCESS_KEY")
S3_REGION_NAME = _env_str_or_none("S3_REGION_NAME")
S3_BUCKET_NAME = _env_str_or_none("S3_BUCKET_NAME")
S3_KEY_PREFIX = _env_str_or_none("S3_KEY_PREFIX")
S3_ENDPOINT_URL = _env_str_or_none("S3_ENDPOINT_URL")
S3_USE_ACCELERATE_ENDPOINT = _env_bool("S3_USE_ACCELERATE_ENDPOINT", "False")
S3_ADDRESSING_STYLE = _env_str_or_none("S3_ADDRESSING_STYLE")

GCS_BUCKET_NAME = _env_str_or_none("GCS_BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS_JSON = _env_str_or_none(
    "GOOGLE_APPLICATION_CREDENTIALS_JSON"
)

AZURE_STORAGE_ENDPOINT = _env_str_or_none("AZURE_STORAGE_ENDPOINT")
AZURE_STORAGE_CONTAINER_NAME = _env_str_or_none("AZURE_STORAGE_CONTAINER_NAME")
AZURE_STORAGE_KEY = _env_str_or_none("AZURE_STORAGE_KEY")


# ===========================================================================
# SECTION: File Upload & Cache Directories
# ===========================================================================

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# SECTION: Direct Connections
# ===========================================================================

ENABLE_DIRECT_CONNECTIONS = PersistentConfig(
    "ENABLE_DIRECT_CONNECTIONS",
    "direct.enable",
    _env_bool("ENABLE_DIRECT_CONNECTIONS", "True"),
)

# ===========================================================================
# SECTION: MCP (Model Context Protocol) servers
# ===========================================================================

ENABLE_MCP_SERVERS = PersistentConfig(
    "ENABLE_MCP_SERVERS",
    "mcp.enabled",
    _env_bool("ENABLE_MCP_SERVERS", "False"),
)
MCP_SERVERS = PersistentConfig("MCP_SERVERS", "mcp.servers", [])
MCP_ALLOWED_HOSTS = PersistentConfig("MCP_ALLOWED_HOSTS", "mcp.allowed_hosts", [])
MCP_BUILTINS_ENABLED = PersistentConfig(
    "MCP_BUILTINS_ENABLED", "mcp.builtins_enabled", ["time"]
)


# ===========================================================================
# SECTION: Audit Configuration
# ===========================================================================

AUDIT_LOG_LEVEL = PersistentConfig(
    "AUDIT_LOG_LEVEL",
    "audit.log_level",
    os.getenv("AUDIT_LOG_LEVEL", "NONE").upper(),
)

AUDIT_EXCLUDED_PATHS = PersistentConfig(
    "AUDIT_EXCLUDED_PATHS",
    "audit.excluded_paths",
    os.getenv("AUDIT_EXCLUDED_PATHS", "/chats,/folders"),
)

MAX_BODY_LOG_SIZE = PersistentConfig(
    "MAX_BODY_LOG_SIZE",
    "audit.max_body_log_size",
    _env_int("MAX_BODY_LOG_SIZE", "2048"),
)

AUDIT_LOG_FILE_ROTATION_SIZE = PersistentConfig(
    "AUDIT_LOG_FILE_ROTATION_SIZE",
    "audit.log_file_rotation_size",
    os.getenv("AUDIT_LOG_FILE_ROTATION_SIZE", "10 MB"),
)

AUDIT_RETENTION_DAYS = PersistentConfig(
    "AUDIT_RETENTION_DAYS",
    "audit.retention_days",
    _env_int("AUDIT_RETENTION_DAYS", "90"),
)


# ===========================================================================
# SECTION: Ollama
# ===========================================================================

ENABLE_OLLAMA_API = PersistentConfig(
    "ENABLE_OLLAMA_API",
    "ollama.enable",
    _env_bool("ENABLE_OLLAMA_API", "True"),
)

OLLAMA_API_BASE_URL = os.environ.get(
    "OLLAMA_API_BASE_URL", "http://localhost:11434/api"
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
if OLLAMA_BASE_URL:
    OLLAMA_BASE_URL = OLLAMA_BASE_URL.rstrip("/")

K8S_FLAG = os.environ.get("K8S_FLAG", "")
USE_OLLAMA_DOCKER = os.environ.get("USE_OLLAMA_DOCKER", "false")

if OLLAMA_BASE_URL == "" and OLLAMA_API_BASE_URL != "":
    OLLAMA_BASE_URL = (
        OLLAMA_API_BASE_URL[:-4]
        if OLLAMA_API_BASE_URL.endswith("/api")
        else OLLAMA_API_BASE_URL
    )

if ENV == "prod":
    if OLLAMA_BASE_URL == "/ollama" and not K8S_FLAG:
        if USE_OLLAMA_DOCKER.lower() == "true":
            OLLAMA_BASE_URL = "http://localhost:11434"
        else:
            OLLAMA_BASE_URL = "http://host.docker.internal:11434"
    elif K8S_FLAG:
        OLLAMA_BASE_URL = "http://ollama-service.bcgpt.svc.cluster.local:11434"

OLLAMA_BASE_URLS = os.environ.get("OLLAMA_BASE_URLS", "")
OLLAMA_BASE_URLS = OLLAMA_BASE_URLS if OLLAMA_BASE_URLS != "" else OLLAMA_BASE_URL

OLLAMA_BASE_URLS = PersistentConfig(
    "OLLAMA_BASE_URLS",
    "ollama.base_urls",
    [url.strip() for url in OLLAMA_BASE_URLS.split(";")],
)

OLLAMA_API_CONFIGS = PersistentConfig(
    "OLLAMA_API_CONFIGS",
    "ollama.api_configs",
    {},
)


# ===========================================================================
# SECTION: OpenAI API
# ===========================================================================

ENABLE_OPENAI_API = PersistentConfig(
    "ENABLE_OPENAI_API",
    "openai.enable",
    _env_bool("ENABLE_OPENAI_API", "True"),
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL", "")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_BASE_URL = os.environ.get("GEMINI_API_BASE_URL", "")

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_API_BASE_URL = os.environ.get("CLAUDE_API_BASE_URL", "")

if OPENAI_API_BASE_URL == "":
    OPENAI_API_BASE_URL = "https://api.openai.com/v1"

OPENAI_API_KEYS = os.environ.get("OPENAI_API_KEYS", "")
OPENAI_API_KEYS = OPENAI_API_KEYS if OPENAI_API_KEYS != "" else OPENAI_API_KEY

OPENAI_API_KEYS = PersistentConfig(
    "OPENAI_API_KEYS",
    "openai.api_keys",
    [k.strip() for k in OPENAI_API_KEYS.split(";")],
)

OPENAI_API_BASE_URLS = os.environ.get("OPENAI_API_BASE_URLS", "")
OPENAI_API_BASE_URLS = (
    OPENAI_API_BASE_URLS if OPENAI_API_BASE_URLS != "" else OPENAI_API_BASE_URL
)

OPENAI_API_BASE_URLS = PersistentConfig(
    "OPENAI_API_BASE_URLS",
    "openai.api_base_urls",
    [
        url.strip() if url != "" else "https://api.openai.com/v1"
        for url in OPENAI_API_BASE_URLS.split(";")
    ],
)

OPENAI_API_CONFIGS = PersistentConfig(
    "OPENAI_API_CONFIGS",
    "openai.api_configs",
    {},
)

# Resolve the actual OpenAI API key from the keys list
OPENAI_API_KEY = ""
try:
    OPENAI_API_KEY = OPENAI_API_KEYS.value[
        OPENAI_API_BASE_URLS.value.index("https://api.openai.com/v1")
    ]
except Exception:
    pass
OPENAI_API_BASE_URL = "https://api.openai.com/v1"


# ===========================================================================
# SECTION: LiteLLM Gateway
# ===========================================================================

LITELLM_GATEWAY_ENABLED = PersistentConfig(
    "LITELLM_GATEWAY_ENABLED",
    "llm.litellm_gateway_enabled",
    _env_bool("LITELLM_GATEWAY_ENABLED", "False"),
)

LITELLM_FALLBACK_MODEL = PersistentConfig(
    "LITELLM_FALLBACK_MODEL",
    "llm.litellm_fallback_model",
    _env_str("LITELLM_FALLBACK_MODEL"),
)

LITELLM_NUM_RETRIES = PersistentConfig(
    "LITELLM_NUM_RETRIES",
    "llm.litellm_num_retries",
    _env_int("LITELLM_NUM_RETRIES", "3"),
)

LITELLM_TIMEOUT = PersistentConfig(
    "LITELLM_TIMEOUT",
    "llm.litellm_timeout",
    _env_int("LITELLM_TIMEOUT", "60"),
)


# ===========================================================================
# SECTION: Gemini API
# ===========================================================================

ENABLE_GEMINI_API = PersistentConfig(
    "ENABLE_GEMINI_API",
    "gemini.enable",
    _env_bool("ENABLE_GEMINI_API", "False"),
)

GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", "")
GEMINI_API_KEYS = GEMINI_API_KEYS if GEMINI_API_KEYS != "" else GEMINI_API_KEY
GEMINI_API_KEYS = PersistentConfig(
    "GEMINI_API_KEYS",
    "gemini.api_keys",
    [k.strip() for k in GEMINI_API_KEYS.split(";") if k.strip()],
)

if not GEMINI_API_BASE_URL:
    GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_API_BASE_URL = PersistentConfig(
    "GEMINI_API_BASE_URL", "gemini.api_base_url", GEMINI_API_BASE_URL
)

GEMINI_API_CONFIGS = PersistentConfig(
    "GEMINI_API_CONFIGS",
    "gemini.api_configs",
    {},
)


# ===========================================================================
# SECTION: Claude API
# ===========================================================================

ENABLE_CLAUDE_API = PersistentConfig(
    "ENABLE_CLAUDE_API",
    "claude.enable",
    _env_bool("ENABLE_CLAUDE_API", "False"),
)

CLAUDE_API_KEYS = os.environ.get("CLAUDE_API_KEYS", "")
CLAUDE_API_KEYS = CLAUDE_API_KEYS if CLAUDE_API_KEYS != "" else CLAUDE_API_KEY
CLAUDE_API_KEYS = PersistentConfig(
    "CLAUDE_API_KEYS",
    "claude.api_keys",
    [k.strip() for k in CLAUDE_API_KEYS.split(";") if k.strip()],
)

if not CLAUDE_API_BASE_URL:
    CLAUDE_API_BASE_URL = "https://api.anthropic.com"
CLAUDE_API_BASE_URL = PersistentConfig(
    "CLAUDE_API_BASE_URL", "claude.api_base_url", CLAUDE_API_BASE_URL
)

CLAUDE_API_CONFIGS = PersistentConfig(
    "CLAUDE_API_CONFIGS",
    "claude.api_configs",
    {},
)


# ===========================================================================
# SECTION: WebUI / UI Configuration
# ===========================================================================

BCGPT_URL = PersistentConfig(
    "BCGPT_URL", "bcgpt.url", _env_str("BCGPT_URL", "http://localhost:3000")
)

ENABLE_SIGNUP = PersistentConfig(
    "ENABLE_SIGNUP",
    "ui.enable_signup",
    (False if not BCGPT_AUTH else _env_bool("ENABLE_SIGNUP", "True")),
)

ENABLE_LOGIN_FORM = PersistentConfig(
    "ENABLE_LOGIN_FORM",
    "ui.ENABLE_LOGIN_FORM",
    _env_bool("ENABLE_LOGIN_FORM", "True"),
)

DEFAULT_LOCALE = PersistentConfig(
    "DEFAULT_LOCALE",
    "ui.default_locale",
    _env_str("DEFAULT_LOCALE"),
)

DEFAULT_MODELS = PersistentConfig(
    "DEFAULT_MODELS", "ui.default_models", _env_str_or_none("DEFAULT_MODELS")
)

DEFAULT_PROMPT_SUGGESTIONS = PersistentConfig(
    "DEFAULT_PROMPT_SUGGESTIONS",
    "ui.prompt_suggestions",
    DEFAULT_CONFIG["ui"]["prompt_suggestions"],
)

MODEL_ORDER_LIST = PersistentConfig(
    "MODEL_ORDER_LIST",
    "ui.model_order_list",
    [],
)

DEFAULT_USER_ROLE = PersistentConfig(
    "DEFAULT_USER_ROLE",
    "ui.default_user_role",
    os.getenv("DEFAULT_USER_ROLE", "pending"),
)


# ===========================================================================
# SECTION: User Permissions
# ===========================================================================

USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS", "False"
)
USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS", "False"
)
USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS", "False"
)
USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS", "False"
)

USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING", "False"
)
USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ALLOW_PUBLIC_SHARING = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ALLOW_PUBLIC_SHARING", "False"
)
USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING", "False"
)
USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING = _env_bool(
    "USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING", "False"
)

USER_PERMISSIONS_CHAT_CONTROLS = _env_bool("USER_PERMISSIONS_CHAT_CONTROLS", "True")
USER_PERMISSIONS_CHAT_FILE_UPLOAD = _env_bool(
    "USER_PERMISSIONS_CHAT_FILE_UPLOAD", "True"
)
USER_PERMISSIONS_CHAT_DELETE = _env_bool("USER_PERMISSIONS_CHAT_DELETE", "True")
USER_PERMISSIONS_CHAT_EDIT = _env_bool("USER_PERMISSIONS_CHAT_EDIT", "True")
USER_PERMISSIONS_CHAT_TEMPORARY = _env_bool("USER_PERMISSIONS_CHAT_TEMPORARY", "True")
USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED = _env_bool(
    "USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED", "False"
)

USER_PERMISSIONS_FEATURES_WEB_SEARCH = _env_bool(
    "USER_PERMISSIONS_FEATURES_WEB_SEARCH", "True"
)
USER_PERMISSIONS_FEATURES_IMAGE_GENERATION = _env_bool(
    "USER_PERMISSIONS_FEATURES_IMAGE_GENERATION", "True"
)

DEFAULT_USER_PERMISSIONS: dict = {
    "workspace": {
        "models": USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS,
        "knowledge": USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS,
        "prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS,
        "tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS,
    },
    "sharing": {
        "public_models": USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING,
        "public_knowledge": USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ALLOW_PUBLIC_SHARING,
        "public_prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING,
        "public_tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING,
    },
    "chat": {
        "controls": USER_PERMISSIONS_CHAT_CONTROLS,
        "file_upload": USER_PERMISSIONS_CHAT_FILE_UPLOAD,
        "delete": USER_PERMISSIONS_CHAT_DELETE,
        "edit": USER_PERMISSIONS_CHAT_EDIT,
        "temporary": USER_PERMISSIONS_CHAT_TEMPORARY,
        "temporary_enforced": USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED,
    },
    "features": {
        "web_search": USER_PERMISSIONS_FEATURES_WEB_SEARCH,
        "image_generation": USER_PERMISSIONS_FEATURES_IMAGE_GENERATION,
    },
}

USER_PERMISSIONS = PersistentConfig(
    "USER_PERMISSIONS",
    "user.permissions",
    DEFAULT_USER_PERMISSIONS,
)

ENABLE_CHANNELS = PersistentConfig(
    "ENABLE_CHANNELS",
    "channels.enable",
    _env_bool("ENABLE_CHANNELS", "False"),
)

ENABLE_EVALUATION_ARENA_MODELS = PersistentConfig(
    "ENABLE_EVALUATION_ARENA_MODELS",
    "evaluation.arena.enable",
    _env_bool("ENABLE_EVALUATION_ARENA_MODELS", "True"),
)

EVALUATION_ARENA_MODELS = PersistentConfig(
    "EVALUATION_ARENA_MODELS",
    "evaluation.arena.models",
    [],
)

DEFAULT_ARENA_MODEL: dict = {
    "id": "arena-model",
    "name": "Arena Model",
    "meta": {
        "profile_image_url": "/favicon.png",
        "description": "Submit your questions to anonymous AI chatbots and vote on the best response.",
        "model_ids": None,
    },
}

WEBHOOK_URL = PersistentConfig("WEBHOOK_URL", "webhook_url", _env_str("WEBHOOK_URL"))

ENABLE_ADMIN_EXPORT = _env_bool("ENABLE_ADMIN_EXPORT", "True")
ENABLE_ADMIN_CHAT_ACCESS = _env_bool("ENABLE_ADMIN_CHAT_ACCESS", "True")

ENABLE_COMMUNITY_SHARING = PersistentConfig(
    "ENABLE_COMMUNITY_SHARING",
    "ui.enable_community_sharing",
    _env_bool("ENABLE_COMMUNITY_SHARING", "True"),
)

ENABLE_MESSAGE_RATING = PersistentConfig(
    "ENABLE_MESSAGE_RATING",
    "ui.enable_message_rating",
    _env_bool("ENABLE_MESSAGE_RATING", "True"),
)

ENABLE_USER_WEBHOOKS = PersistentConfig(
    "ENABLE_USER_WEBHOOKS",
    "ui.enable_user_webhooks",
    _env_bool("ENABLE_USER_WEBHOOKS", "True"),
)

BCGPT_LOGO_URL = PersistentConfig(
    "BCGPT_LOGO_URL",
    "ui.logo_url",
    "",
)

BCGPT_APP_NAME_PERSISTENT = PersistentConfig(
    "BCGPT_APP_NAME",
    "ui.name",
    os.environ.get("BCGPT_APP_NAME", "BCGPT"),
)


# ===========================================================================
# SECTION: CORS Configuration
# ===========================================================================


def validate_cors_origin(origin: str) -> None:
    """Raise :class:`ValueError` if *origin* is not a valid http(s) URL."""
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. "
            "Only 'http' and 'https' are allowed."
        )
    if not parsed.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


def validate_cors_origins(origins: list[str]) -> None:
    for origin in origins:
        if origin != "*":
            validate_cors_origin(origin)


CORS_ALLOW_ORIGIN: list[str] = os.environ.get("CORS_ALLOW_ORIGIN", "").split(";")

if CORS_ALLOW_ORIGIN and CORS_ALLOW_ORIGIN != [""]:
    validate_cors_origins(CORS_ALLOW_ORIGIN)
    if "*" in CORS_ALLOW_ORIGIN:
        log.warning(
            "CORS_ALLOW_ORIGIN contains '*'. "
            "Using wildcard origins with allow_credentials=True is insecure and not recommended for production."
        )


# ===========================================================================
# SECTION: Banners
# ===========================================================================


class BannerModel(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    content: str
    dismissible: bool
    timestamp: int


try:
    _banners = json.loads(os.environ.get("BCGPT_BANNERS", "[]"))
    _banners = [BannerModel(**b) for b in _banners]
except Exception as exc:
    log.exception(f"Error loading BCGPT_BANNERS: {exc}")
    _banners = []

BCGPT_BANNERS = PersistentConfig("BCGPT_BANNERS", "ui.banners", _banners)

SHOW_ADMIN_DETAILS = PersistentConfig(
    "SHOW_ADMIN_DETAILS",
    "auth.admin.show",
    _env_bool("SHOW_ADMIN_DETAILS", "true"),
)

ADMIN_EMAIL = PersistentConfig(
    "ADMIN_EMAIL",
    "auth.admin.email",
    _env_str_or_none("ADMIN_EMAIL"),
)


# ===========================================================================
# SECTION: Task Prompts
# ===========================================================================

TASK_MODEL = PersistentConfig(
    "TASK_MODEL",
    "task.model.default",
    _env_str("TASK_MODEL"),
)

TASK_MODEL_EXTERNAL = PersistentConfig(
    "TASK_MODEL_EXTERNAL",
    "task.model.external",
    _env_str("TASK_MODEL_EXTERNAL"),
)

TITLE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "task.title.prompt_template",
    _env_str("TITLE_GENERATION_PROMPT_TEMPLATE"),
)

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a concise title summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Do not include emojis, quotation marks, or special formatting.
- IMPORTANT: You MUST write the title in the SAME language as the user's messages. Detect the language of the chat history and respond in that exact language. Never translate to a different language.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "Stock Market Trends" },
- { "title": "주식 시장 동향 분석" },
- { "title": "완벽한 초코칩 쿠키 레시피" },
- { "title": "Evolution of Music Streaming" },
- { "title": "AI 의료 분야 활용 사례" },
- { "title": "Remote Work Productivity Tips" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

TAGS_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TAGS_GENERATION_PROMPT_TEMPLATE",
    "task.tags.prompt_template",
    _env_str("TAGS_GENERATION_PROMPT_TEMPLATE"),
)

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE",
    "task.image.prompt_template",
    _env_str("IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE"),
)

DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a detailed prompt for am image generation task based on the given language and context. Describe the image as if you were explaining it to someone who cannot see it. Include relevant details, colors, shapes, and any other important elements.

### Guidelines:
- Be descriptive and detailed, focusing on the most important aspects of the image.
- Avoid making assumptions or adding information not present in the image.
- Use the chat's primary language; default to English if multilingual.
- If the image is too complex, focus on the most prominent elements.

### Output:
Strictly return in JSON format:
{
    "prompt": "Your detailed description here."
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

IMAGE_PROMPT_TRANSLATION_TEMPLATE = PersistentConfig(
    "IMAGE_PROMPT_TRANSLATION_TEMPLATE",
    "task.image.translation_template",
    _env_str("IMAGE_PROMPT_TRANSLATION_TEMPLATE"),
)

DEFAULT_IMAGE_PROMPT_TRANSLATION_TEMPLATE = """### Task:
Detect the language of the given image generation prompt. If the prompt is not in English, translate it to English while preserving all visual details, style references, and artistic intent. If the prompt is already in English, return it unchanged.

### Guidelines:
- Preserve all specific details: colors, compositions, styles, artists, techniques.
- Keep technical terms (e.g., "bokeh", "chromatic aberration", "tilt-shift") as-is.
- Maintain any quality modifiers (e.g., "4K", "highly detailed", "masterpiece").
- Translate descriptive words accurately to their English equivalents.
- Do NOT add new details or modify the original intent.

### Output:
Strictly return in JSON format:
{
    "prompt": "Translated English prompt here."
}

### Prompt:
{{PROMPT}}"""

IMAGE_PROMPT_EXPANSION_TEMPLATE = PersistentConfig(
    "IMAGE_PROMPT_EXPANSION_TEMPLATE",
    "task.image.expansion_template",
    _env_str("IMAGE_PROMPT_EXPANSION_TEMPLATE"),
)

DEFAULT_IMAGE_PROMPT_EXPANSION_TEMPLATE = """### Task:
Enhance the given image generation prompt by adding relevant quality modifiers, lighting details, composition guidance, and artistic style references to produce a higher-quality result. Do not change the core subject or intent of the prompt.

### Guidelines:
- Add quality modifiers: masterpiece, best quality, highly detailed, sharp focus, professional.
- Add lighting details when appropriate: cinematic lighting, volumetric lighting, golden hour, soft ambient light.
- Add composition hints when appropriate: rule of thirds, centered composition, dynamic angle.
- Add relevant technical terms: 8K, ultra HD, HDR, high resolution.
- Do NOT change the core subject, add new characters, or alter the original intent.
- Keep the prompt concise but enriched (aim for 2-3x the original length at most).
- If the prompt is already detailed and high-quality, only add minimal enhancements.

### Output:
Strictly return in JSON format:
{
    "prompt": "Enhanced prompt here."
}

### Prompt:
{{PROMPT}}"""

ENABLE_TAGS_GENERATION = PersistentConfig(
    "ENABLE_TAGS_GENERATION",
    "task.tags.enable",
    _env_bool("ENABLE_TAGS_GENERATION", "True"),
)

ENABLE_TITLE_GENERATION = PersistentConfig(
    "ENABLE_TITLE_GENERATION",
    "task.title.enable",
    _env_bool("ENABLE_TITLE_GENERATION", "True"),
)

ENABLE_MEMORY_INJECTION = PersistentConfig(
    "ENABLE_MEMORY_INJECTION",
    "task.memory.injection_enable",
    _env_bool("ENABLE_MEMORY_INJECTION", "True"),
)

ENABLE_MEMORY_EXTRACTION = PersistentConfig(
    "ENABLE_MEMORY_EXTRACTION",
    "task.memory.extraction_enable",
    _env_bool("ENABLE_MEMORY_EXTRACTION", "True"),
)

ENABLE_SEARCH_QUERY_GENERATION = PersistentConfig(
    "ENABLE_SEARCH_QUERY_GENERATION",
    "task.query.search.enable",
    _env_bool("ENABLE_SEARCH_QUERY_GENERATION", "True"),
)

ENABLE_RETRIEVAL_QUERY_GENERATION = PersistentConfig(
    "ENABLE_RETRIEVAL_QUERY_GENERATION",
    "task.query.retrieval.enable",
    _env_bool("ENABLE_RETRIEVAL_QUERY_GENERATION", "True"),
)

QUERY_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "QUERY_GENERATION_PROMPT_TEMPLATE",
    "task.query.prompt_template",
    _env_str("QUERY_GENERATION_PROMPT_TEMPLATE"),
)

DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Analyze the chat history to determine the necessity of generating search queries, in the given language. By default, **prioritize generating 1-3 broad and relevant search queries** unless it is absolutely certain that no additional information is required. The aim is to retrieve comprehensive, updated, and valuable information even with minimal uncertainty. If no search is unequivocally needed, return an empty list.

### Guidelines:
- Respond **EXCLUSIVELY** with a JSON object. Any form of extra commentary, explanation, or additional text is strictly prohibited.
- When generating search queries, respond in the format: { "queries": ["query1", "query2"] }, ensuring each query is distinct, concise, and relevant to the topic.
- If and only if it is entirely certain that no useful results can be retrieved by a search, return: { "queries": [] }.
- Err on the side of suggesting search queries if there is **any chance** they might provide useful or updated information.
- Be concise and focused on composing high-quality search queries, avoiding unnecessary elaboration, commentary, or assumptions.
- Today's date is: {{CURRENT_DATE}}.
- Always prioritize providing actionable and broad queries that maximize informational coverage.

### Output:
Strictly return in JSON format: 
{
  "queries": ["query1", "query2"]
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

ENABLE_AUTOCOMPLETE_GENERATION = PersistentConfig(
    "ENABLE_AUTOCOMPLETE_GENERATION",
    "task.autocomplete.enable",
    _env_bool("ENABLE_AUTOCOMPLETE_GENERATION", "False"),
)

AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = PersistentConfig(
    "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH",
    "task.autocomplete.input_max_length",
    _env_int("AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH", "-1"),
)

AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE",
    "task.autocomplete.prompt_template",
    _env_str("AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE"),
)

DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = """### Task:
You are an autocompletion system. Continue the text in `<text>` based on the **completion type** in `<type>` and the given language.  

### **Instructions**:
1. Analyze `<text>` for context and meaning.  
2. Use `<type>` to guide your output:  
   - **General**: Provide a natural, concise continuation.  
   - **Search Query**: Complete as if generating a realistic search query.  
3. Start as if you are directly continuing `<text>`. Do **not** repeat, paraphrase, or respond as a model. Simply complete the text.  
4. Ensure the continuation:
   - Flows naturally from `<text>`.  
   - Avoids repetition, overexplaining, or unrelated ideas.  
5. If unsure, return: `{ "text": "" }`. 

### **Output Rules**:
- Respond only in JSON format: `{ "text": "<your_completion>" }`.

### **Examples**:
#### Example 1:  
Input:  
<type>General</type>  
<text>The sun was setting over the horizon, painting the sky</text>  
Output:  
{ "text": "with vibrant shades of orange and pink." }

#### Example 2:  
Input:  
<type>Search Query</type>  
<text>Top-rated restaurants in</text>  
Output:  
{ "text": "New York City for Italian cuisine." }  

---
### Context:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
<type>{{TYPE}}</type>  
<text>{{PROMPT}}</text>  
#### Output:
"""

TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = PersistentConfig(
    "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE",
    "task.tools.prompt_template",
    _env_str("TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE"),
)

DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}

Your task is to choose and return the correct tool(s) from the list of available tools based on the query. Follow these guidelines:

- Return only the JSON object, without any additional text or explanation.

- If no tools match the query, return an empty array: 
   {
     "tool_calls": []
   }

- If one or more tools match the query, construct a JSON response containing a "tool_calls" array with objects that include:
   - "name": The tool's name.
   - "parameters": A dictionary of required parameters and their corresponding values.

The format for the JSON response is strictly:
{
  "tool_calls": [
    {"name": "toolName1", "parameters": {"key1": "value1"}},
    {"name": "toolName2", "parameters": {"key2": "value2"}}
  ]
}"""

DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE = """Your task is to reflect the speaker's likely facial expression through a fitting emoji. Interpret emotions from the message and reflect their facial expression using fitting, diverse emojis (e.g., 😊, 😢, 😡, 😱).

Message: ```{{prompt}}```"""

DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE = """You have been provided with a set of responses from various models to the latest user query: "{{prompt}}"

Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models: {{responses}}"""


# ===========================================================================
# SECTION: Vector Database
# ===========================================================================

VECTOR_DB = os.environ.get("VECTOR_DB", "qdrant")

# Milvus
MILVUS_URI = os.environ.get("MILVUS_URI", f"{DATA_DIR}/vector_db/milvus.db")
MILVUS_DB = os.environ.get("MILVUS_DB", "default")
MILVUS_TOKEN = _env_str_or_none("MILVUS_TOKEN")

# OpenSearch
OPENSEARCH_URI = os.environ.get("OPENSEARCH_URI", "https://localhost:9200")
OPENSEARCH_SSL = _env_bool("OPENSEARCH_SSL", "true")
OPENSEARCH_CERT_VERIFY = _env_bool("OPENSEARCH_CERT_VERIFY", "false")
OPENSEARCH_USERNAME = _env_str_or_none("OPENSEARCH_USERNAME")
OPENSEARCH_PASSWORD = _env_str_or_none("OPENSEARCH_PASSWORD")

# ElasticSearch
ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "https://localhost:9200")
ELASTICSEARCH_CA_CERTS = _env_str_or_none("ELASTICSEARCH_CA_CERTS")
ELASTICSEARCH_API_KEY = _env_str_or_none("ELASTICSEARCH_API_KEY")
ELASTICSEARCH_USERNAME = _env_str_or_none("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = _env_str_or_none("ELASTICSEARCH_PASSWORD")
ELASTICSEARCH_CLOUD_ID = _env_str_or_none("ELASTICSEARCH_CLOUD_ID")
SSL_ASSERT_FINGERPRINT = _env_str_or_none("SSL_ASSERT_FINGERPRINT")
ELASTICSEARCH_INDEX_PREFIX = os.environ.get(
    "ELASTICSEARCH_INDEX_PREFIX", "bcgpt_collections"
)

# Pgvector
PGVECTOR_DB_URL = os.environ.get("PGVECTOR_DB_URL", DATABASE_URL)
if VECTOR_DB == "pgvector" and not PGVECTOR_DB_URL.startswith("postgres"):
    raise ValueError(
        "Pgvector requires setting PGVECTOR_DB_URL or using Postgres with vector extension as the primary database."
    )
PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH = _env_int(
    "PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH", "1536"
)


# ===========================================================================
# SECTION: RAG — Information Retrieval
# ===========================================================================

# Google Drive integration
ENABLE_GOOGLE_DRIVE_INTEGRATION = PersistentConfig(
    "ENABLE_GOOGLE_DRIVE_INTEGRATION",
    "google_drive.enable",
    _env_bool("ENABLE_GOOGLE_DRIVE_INTEGRATION", "False"),
)

GOOGLE_DRIVE_CLIENT_ID = PersistentConfig(
    "GOOGLE_DRIVE_CLIENT_ID",
    "google_drive.client_id",
    _env_str("GOOGLE_DRIVE_CLIENT_ID"),
)

GOOGLE_DRIVE_API_KEY = PersistentConfig(
    "GOOGLE_DRIVE_API_KEY",
    "google_drive.api_key",
    _env_str("GOOGLE_DRIVE_API_KEY"),
)

# OneDrive integration
ENABLE_ONEDRIVE_INTEGRATION = PersistentConfig(
    "ENABLE_ONEDRIVE_INTEGRATION",
    "onedrive.enable",
    _env_bool("ENABLE_ONEDRIVE_INTEGRATION", "False"),
)

ONEDRIVE_CLIENT_ID = PersistentConfig(
    "ONEDRIVE_CLIENT_ID",
    "onedrive.client_id",
    _env_str("ONEDRIVE_CLIENT_ID"),
)

# Content extraction
CONTENT_EXTRACTION_ENGINE = PersistentConfig(
    "CONTENT_EXTRACTION_ENGINE",
    "rag.CONTENT_EXTRACTION_ENGINE",
    os.environ.get("CONTENT_EXTRACTION_ENGINE", "").lower(),
)

TIKA_SERVER_URL = PersistentConfig(
    "TIKA_SERVER_URL",
    "rag.tika_server_url",
    os.getenv("TIKA_SERVER_URL", "http://tika:9998"),
)

DOCLING_SERVER_URL = PersistentConfig(
    "DOCLING_SERVER_URL",
    "rag.docling_server_url",
    os.getenv("DOCLING_SERVER_URL", "http://docling:5001"),
)

DOCUMENT_INTELLIGENCE_ENDPOINT = PersistentConfig(
    "DOCUMENT_INTELLIGENCE_ENDPOINT",
    "rag.document_intelligence_endpoint",
    os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", ""),
)

DOCUMENT_INTELLIGENCE_KEY = PersistentConfig(
    "DOCUMENT_INTELLIGENCE_KEY",
    "rag.document_intelligence_key",
    os.getenv("DOCUMENT_INTELLIGENCE_KEY", ""),
)

BYPASS_EMBEDDING_AND_RETRIEVAL = PersistentConfig(
    "BYPASS_EMBEDDING_AND_RETRIEVAL",
    "rag.bypass_embedding_and_retrieval",
    _env_bool("BYPASS_EMBEDDING_AND_RETRIEVAL", "False"),
)

RAG_TOP_K = PersistentConfig("RAG_TOP_K", "rag.top_k", _env_int("RAG_TOP_K", "6"))
RAG_TOP_K_RERANKER = PersistentConfig(
    "RAG_TOP_K_RERANKER",
    "rag.top_k_reranker",
    _env_int("RAG_TOP_K_RERANKER", "10"),
)
RAG_RELEVANCE_THRESHOLD = PersistentConfig(
    "RAG_RELEVANCE_THRESHOLD",
    "rag.relevance_threshold",
    _env_float("RAG_RELEVANCE_THRESHOLD", "0.2"),
)

ENABLE_RAG_HYBRID_SEARCH = PersistentConfig(
    "ENABLE_RAG_HYBRID_SEARCH",
    "rag.enable_hybrid_search",
    _env_bool("ENABLE_RAG_HYBRID_SEARCH", ""),
)

RAG_FULL_CONTEXT = PersistentConfig(
    "RAG_FULL_CONTEXT",
    "rag.full_context",
    _env_bool("RAG_FULL_CONTEXT", "False"),
)

RAG_FILE_MAX_COUNT = PersistentConfig(
    "RAG_FILE_MAX_COUNT",
    "rag.file.max_count",
    _env_int("RAG_FILE_MAX_COUNT") if os.environ.get("RAG_FILE_MAX_COUNT") else None,
)

RAG_FILE_MAX_SIZE = PersistentConfig(
    "RAG_FILE_MAX_SIZE",
    "rag.file.max_size",
    _env_int("RAG_FILE_MAX_SIZE") if os.environ.get("RAG_FILE_MAX_SIZE") else 100,
)

ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = PersistentConfig(
    "ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION",
    "rag.enable_web_loader_ssl_verification",
    _env_bool("ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION", "True"),
)

RAG_EMBEDDING_ENGINE = PersistentConfig(
    "RAG_EMBEDDING_ENGINE",
    "rag.embedding_engine",
    _env_str("RAG_EMBEDDING_ENGINE"),
)

PDF_EXTRACT_IMAGES = PersistentConfig(
    "PDF_EXTRACT_IMAGES",
    "rag.pdf_extract_images",
    _env_bool("PDF_EXTRACT_IMAGES", "False"),
)

RAG_EMBEDDING_MODEL = PersistentConfig(
    "RAG_EMBEDDING_MODEL",
    "rag.embedding_model",
    os.environ.get("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)
log.info(f"Embedding model set: {RAG_EMBEDDING_MODEL.value}")

RAG_EMBEDDING_MODEL_AUTO_UPDATE = not OFFLINE_MODE and _env_bool(
    "RAG_EMBEDDING_MODEL_AUTO_UPDATE", "True"
)

RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE = _env_bool(
    "RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE", "False"
)

RAG_EMBEDDING_BATCH_SIZE = PersistentConfig(
    "RAG_EMBEDDING_BATCH_SIZE",
    "rag.embedding_batch_size",
    int(
        os.environ.get("RAG_EMBEDDING_BATCH_SIZE")
        or os.environ.get("RAG_EMBEDDING_OPENAI_BATCH_SIZE", "1")
    ),
)

RAG_EMBEDDING_QUERY_PREFIX = _env_str_or_none("RAG_EMBEDDING_QUERY_PREFIX")
RAG_EMBEDDING_CONTENT_PREFIX = _env_str_or_none("RAG_EMBEDDING_CONTENT_PREFIX")
RAG_EMBEDDING_PREFIX_FIELD_NAME = _env_str_or_none("RAG_EMBEDDING_PREFIX_FIELD_NAME")

RAG_EMBEDDING_MODEL_URI = PersistentConfig(
    "RAG_EMBEDDING_MODEL_URI",
    "rag.embedding_model_uri",
    _env_str("RAG_EMBEDDING_MODEL_URI"),
)

RAG_EMBEDDING_MODEL_API_KEY = PersistentConfig(
    "RAG_EMBEDDING_MODEL_API_KEY",
    "rag.embedding_model_api_key",
    _env_str("RAG_EMBEDDING_MODEL_API_KEY"),
)

# ---------------------------------------------------------------------------
# RAG corpus consolidation (P1)
# ---------------------------------------------------------------------------
# When true, new vectors are written into a single shared corpus collection per
# embedding-model configuration (see retrieval.vector.corpus) and retrieval
# uses payload-filtered ANN instead of one collection per file / per KB.
# Default false — opt-in after the consolidate_corpus migration has folded
# legacy collections into the corpus. Until flipped, the per-file/KB model and
# the corpus code-path coexist (the flag gates only P1.3/P1.4).
RAG_USE_CORPUS = PersistentConfig(
    "RAG_USE_CORPUS",
    "rag.use_corpus",
    _env_bool("RAG_USE_CORPUS", "False"),
)

RAG_RERANKING_MODEL = PersistentConfig(
    "RAG_RERANKING_MODEL",
    "rag.reranking_model",
    _env_str("RAG_RERANKING_MODEL"),
)
if RAG_RERANKING_MODEL.value != "":
    log.info(f"Reranking model set: {RAG_RERANKING_MODEL.value}")

RAG_RERANKING_MODEL_AUTO_UPDATE = not OFFLINE_MODE and _env_bool(
    "RAG_RERANKING_MODEL_AUTO_UPDATE", "True"
)

RAG_RERANKING_MODEL_TRUST_REMOTE_CODE = _env_bool(
    "RAG_RERANKING_MODEL_TRUST_REMOTE_CODE", "False"
)

RAG_RERANKING_MODEL_URI = PersistentConfig(
    "RAG_RERANKING_MODEL_URI",
    "rag.reranking_model_uri",
    _env_str("RAG_RERANKING_MODEL_URI"),
)

RAG_RERANKING_MODEL_API_KEY = PersistentConfig(
    "RAG_RERANKING_MODEL_API_KEY",
    "rag.reranking_model_api_key",
    _env_str("RAG_RERANKING_MODEL_API_KEY"),
)

RAG_TEXT_SPLITTER = PersistentConfig(
    "RAG_TEXT_SPLITTER",
    "rag.text_splitter",
    _env_str("RAG_TEXT_SPLITTER"),
)

TIKTOKEN_CACHE_DIR = os.environ.get("TIKTOKEN_CACHE_DIR", f"{CACHE_DIR}/tiktoken")
TIKTOKEN_ENCODING_NAME = PersistentConfig(
    "TIKTOKEN_ENCODING_NAME",
    "rag.tiktoken_encoding_name",
    _env_str("TIKTOKEN_ENCODING_NAME", "cl100k_base"),
)

CHUNK_SIZE = PersistentConfig(
    "CHUNK_SIZE", "rag.chunk_size", _env_int("CHUNK_SIZE", "1000")
)
CHUNK_OVERLAP = PersistentConfig(
    "CHUNK_OVERLAP", "rag.chunk_overlap", _env_int("CHUNK_OVERLAP", "100")
)
RAG_LATE_CHUNKING_ENABLED = PersistentConfig(
    "RAG_LATE_CHUNKING_ENABLED",
    "rag.late_chunking_enabled",
    _env_bool("RAG_LATE_CHUNKING_ENABLED", "False"),
)

# Qdrant
QDRANT_URL = PersistentConfig(
    "QDRANT_URL",
    "rag.qdrant_url",
    os.environ.get("QDRANT_URL", os.environ.get("QDRANT_URI", "")),
)
QDRANT_API_KEY = PersistentConfig(
    "QDRANT_API_KEY",
    "rag.qdrant_api_key",
    _env_str("QDRANT_API_KEY"),
)

# RAG post-processing
CLEANSING_ENABLED = PersistentConfig(
    "CLEANSING_ENABLED",
    "rag.cleansing_enabled",
    _env_bool("CLEANSING_ENABLED", "False"),
)
CLEANSING_MODEL = PersistentConfig(
    "CLEANSING_MODEL", "rag.cleansing_model", _env_str("CLEANSING_MODEL")
)
SUMMARY_ENABLED = PersistentConfig(
    "SUMMARY_ENABLED",
    "rag.summary_enabled",
    _env_bool("SUMMARY_ENABLED", "False"),
)
SUMMARY_MODEL = PersistentConfig(
    "SUMMARY_MODEL", "rag.summary_model", _env_str("SUMMARY_MODEL")
)

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [source_id] (e.g., [1], [2]) when a `<source_id>` tag is explicitly provided in the context.**
- Do not cite if the <source_id> tag is not provided in the context.  
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in "whitepaper.pdf" with a provided <source_id>, the response should include the citation like so:  
* "According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf]."
If no <source_id> is present, the response should omit the citation.

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.

<context>
{{CONTEXT}}
</context>

<user_query>
{{QUERY}}
</user_query>
"""

RAG_TEMPLATE = PersistentConfig(
    "RAG_TEMPLATE",
    "rag.template",
    os.environ.get("RAG_TEMPLATE", DEFAULT_RAG_TEMPLATE),
)

RAG_OPENAI_API_BASE_URL = PersistentConfig(
    "RAG_OPENAI_API_BASE_URL",
    "rag.openai_api_base_url",
    os.getenv("RAG_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
RAG_OPENAI_API_KEY = PersistentConfig(
    "RAG_OPENAI_API_KEY",
    "rag.openai_api_key",
    os.getenv("RAG_OPENAI_API_KEY", OPENAI_API_KEY),
)

RAG_OLLAMA_BASE_URL = PersistentConfig(
    "RAG_OLLAMA_BASE_URL",
    "rag.ollama.url",
    os.getenv("RAG_OLLAMA_BASE_URL", OLLAMA_BASE_URL),
)
RAG_OLLAMA_API_KEY = PersistentConfig(
    "RAG_OLLAMA_API_KEY",
    "rag.ollama.key",
    os.getenv("RAG_OLLAMA_API_KEY", ""),
)

ENABLE_RAG_LOCAL_WEB_FETCH = _env_bool("ENABLE_RAG_LOCAL_WEB_FETCH", "False")

YOUTUBE_LOADER_LANGUAGE = PersistentConfig(
    "YOUTUBE_LOADER_LANGUAGE",
    "rag.youtube_loader_language",
    os.getenv("YOUTUBE_LOADER_LANGUAGE", "en").split(","),
)

YOUTUBE_LOADER_PROXY_URL = PersistentConfig(
    "YOUTUBE_LOADER_PROXY_URL",
    "rag.youtube_loader_proxy_url",
    os.getenv("YOUTUBE_LOADER_PROXY_URL", ""),
)


# ===========================================================================
# SECTION: RAG — Web Search
# ===========================================================================

ENABLE_RAG_WEB_SEARCH = PersistentConfig(
    "ENABLE_RAG_WEB_SEARCH",
    "rag.web.search.enable",
    _env_bool("ENABLE_RAG_WEB_SEARCH", "False"),
)

RAG_WEB_SEARCH_ENGINE = PersistentConfig(
    "RAG_WEB_SEARCH_ENGINE",
    "rag.web.search.engine",
    _env_str("RAG_WEB_SEARCH_ENGINE"),
)

BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL = PersistentConfig(
    "BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL",
    "rag.web.search.bypass_embedding_and_retrieval",
    _env_bool("BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL", "False"),
)


# ===========================================================================
# SECTION: Advanced RAG Features
# ===========================================================================

# HyDE
RAG_HYDE_ENABLED = PersistentConfig(
    "RAG_HYDE_ENABLED",
    "rag.hyde.enabled",
    _env_bool("RAG_HYDE_ENABLED", "False"),
)
RAG_HYDE_MODEL = PersistentConfig(
    "RAG_HYDE_MODEL",
    "rag.hyde.model",
    _env_str("RAG_HYDE_MODEL"),
)

# Query Expansion
RAG_QUERY_EXPANSION_ENABLED = PersistentConfig(
    "RAG_QUERY_EXPANSION_ENABLED",
    "rag.query_expansion.enabled",
    _env_bool("RAG_QUERY_EXPANSION_ENABLED", "False"),
)
RAG_QUERY_EXPANSION_MAX = PersistentConfig(
    "RAG_QUERY_EXPANSION_MAX",
    "rag.query_expansion.max",
    _env_int("RAG_QUERY_EXPANSION_MAX", "3"),
)

# Step-Back Prompting
RAG_STEP_BACK_ENABLED = PersistentConfig(
    "RAG_STEP_BACK_ENABLED",
    "rag.step_back.enabled",
    _env_bool("RAG_STEP_BACK_ENABLED", "False"),
)

# RRF Fusion
RAG_RRF_K = PersistentConfig("RAG_RRF_K", "rag.rrf.k", _env_int("RAG_RRF_K", "20"))
RAG_RRF_VECTOR_WEIGHT = PersistentConfig(
    "RAG_RRF_VECTOR_WEIGHT",
    "rag.rrf.vector_weight",
    _env_float("RAG_RRF_VECTOR_WEIGHT", "0.7"),
)
RAG_RRF_KEYWORD_WEIGHT = PersistentConfig(
    "RAG_RRF_KEYWORD_WEIGHT",
    "rag.rrf.keyword_weight",
    _env_float("RAG_RRF_KEYWORD_WEIGHT", "0.3"),
)

# Rule-Based Reranking
RAG_RULE_BASED_RERANKING_ENABLED = PersistentConfig(
    "RAG_RULE_BASED_RERANKING_ENABLED",
    "rag.reranking.rule_based.enabled",
    _env_bool("RAG_RULE_BASED_RERANKING_ENABLED", "False"),
)

# LLM Reranking
RAG_LLM_RERANKING_ENABLED = PersistentConfig(
    "RAG_LLM_RERANKING_ENABLED",
    "rag.reranking.llm.enabled",
    _env_bool("RAG_LLM_RERANKING_ENABLED", "False"),
)
RAG_LLM_RERANKING_MODEL = PersistentConfig(
    "RAG_LLM_RERANKING_MODEL",
    "rag.reranking.llm.model",
    _env_str("RAG_LLM_RERANKING_MODEL"),
)

# CRAG
RAG_CRAG_ENABLED = PersistentConfig(
    "RAG_CRAG_ENABLED",
    "rag.crag.enabled",
    _env_bool("RAG_CRAG_ENABLED", "False"),
)
RAG_CRAG_THRESHOLD_SUFFICIENT = PersistentConfig(
    "RAG_CRAG_THRESHOLD_SUFFICIENT",
    "rag.crag.threshold_sufficient",
    _env_float("RAG_CRAG_THRESHOLD_SUFFICIENT", "65"),
)
RAG_CRAG_THRESHOLD_INSUFFICIENT = PersistentConfig(
    "RAG_CRAG_THRESHOLD_INSUFFICIENT",
    "rag.crag.threshold_insufficient",
    _env_float("RAG_CRAG_THRESHOLD_INSUFFICIENT", "40"),
)
RAG_CRAG_WEB_FALLBACK_ENABLED = PersistentConfig(
    "RAG_CRAG_WEB_FALLBACK_ENABLED",
    "rag.crag.web_fallback_enabled",
    _env_bool("RAG_CRAG_WEB_FALLBACK_ENABLED", "False"),
)

# Document Grading
RAG_DOC_GRADING_ENABLED = PersistentConfig(
    "RAG_DOC_GRADING_ENABLED",
    "rag.doc_grading.enabled",
    _env_bool("RAG_DOC_GRADING_ENABLED", "False"),
)

# Evidence Reconciliation
RAG_EVIDENCE_RECONCILIATION_ENABLED = PersistentConfig(
    "RAG_EVIDENCE_RECONCILIATION_ENABLED",
    "rag.evidence_reconciliation.enabled",
    _env_bool("RAG_EVIDENCE_RECONCILIATION_ENABLED", "False"),
)

# ──────────────────────────────────────────────────────────────────────────
# open-moai adoption — Phase 1 (risk-free backend algorithm / security wins)
# Opt-in (default OFF) per the RAG_*_ENABLED convention, EXCEPT the two pure
# safety-hardening flags (entity guard, file magic validation) which default ON.
# Algorithms re-implemented from open-moai (Apache-2.0); see module docstrings.
# ──────────────────────────────────────────────────────────────────────────

# 1.1 Content isolation / spotlighting (indirect prompt-injection defense)
CONTENT_ISOLATION_ENABLED = PersistentConfig(
    "CONTENT_ISOLATION_ENABLED",
    "rag.content_isolation.enabled",
    _env_bool("CONTENT_ISOLATION_ENABLED", "False"),
)
CONTENT_ISOLATION_METHOD = PersistentConfig(
    "CONTENT_ISOLATION_METHOD",
    "rag.content_isolation.method",
    _env_str("CONTENT_ISOLATION_METHOD", "datamarking"),
)

# 1.2 MMR diversity reranking
RAG_MMR_ENABLED = PersistentConfig(
    "RAG_MMR_ENABLED",
    "rag.mmr.enabled",
    _env_bool("RAG_MMR_ENABLED", "False"),
)
RAG_MMR_LAMBDA = PersistentConfig(
    "RAG_MMR_LAMBDA",
    "rag.mmr.lambda",
    _env_float("RAG_MMR_LAMBDA", "0.7"),
)

# 1.3 Deterministic citation-grounding audit (no-LLM) lives in bcgpt/agent/config.py
# (QUALITY_CITATION_AUDIT_ENABLED) alongside the other agent quality-stage flags.

# 1.4 Named-entity preservation in query rewriting (safety hardening — default ON)
QUERY_REWRITE_ENTITY_GUARD_ENABLED = PersistentConfig(
    "QUERY_REWRITE_ENTITY_GUARD_ENABLED",
    "rag.query_rewrite.entity_guard.enabled",
    _env_bool("QUERY_REWRITE_ENTITY_GUARD_ENABLED", "True"),
)

# 1.5 EU AI Act structured AI-interaction audit logging
AI_INTERACTION_AUDIT_ENABLED = PersistentConfig(
    "AI_INTERACTION_AUDIT_ENABLED",
    "audit.ai_interaction.enabled",
    _env_bool("AI_INTERACTION_AUDIT_ENABLED", "False"),
)

# 1.6 Magic-byte file signature validation (safety hardening — default ON)
FILE_MAGIC_VALIDATION_ENABLED = PersistentConfig(
    "FILE_MAGIC_VALIDATION_ENABLED",
    "rag.file_magic_validation.enabled",
    _env_bool("FILE_MAGIC_VALIDATION_ENABLED", "True"),
)

# ──────────────────────────────────────────────────────────────────────────
# open-moai adoption — Phase 2 (governance / FinOps / ingest-quality backbone)
# ──────────────────────────────────────────────────────────────────────────

# 2.1 Token/cost usage persistence (FinOps backbone) — opt-in
TOKEN_USAGE_PERSIST_ENABLED = PersistentConfig(
    "TOKEN_USAGE_PERSIST_ENABLED",
    "cost.token_usage_persist.enabled",
    _env_bool("TOKEN_USAGE_PERSIST_ENABLED", "False"),
)

# 2.2 Token/cost budget (OWASP LLM10 denial-of-wallet) — opt-in.
# Per-user caps; 0 = unlimited. Group-level overrides via groups.permissions.
TOKEN_BUDGET_ENABLED = PersistentConfig(
    "TOKEN_BUDGET_ENABLED",
    "cost.token_budget.enabled",
    _env_bool("TOKEN_BUDGET_ENABLED", "False"),
)
TOKEN_BUDGET_DAILY = PersistentConfig(
    "TOKEN_BUDGET_DAILY",
    "cost.token_budget.daily",
    _env_int("TOKEN_BUDGET_DAILY", "0"),
)
TOKEN_BUDGET_PER_MIN = PersistentConfig(
    "TOKEN_BUDGET_PER_MIN",
    "cost.token_budget.per_min",
    _env_int("TOKEN_BUDGET_PER_MIN", "0"),
)

# 2.6 Ingestion-time chunk-quality scorer + CSV column-type profiler — opt-in
RAG_CHUNK_QUALITY_ENABLED = PersistentConfig(
    "RAG_CHUNK_QUALITY_ENABLED",
    "rag.chunk_quality.enabled",
    _env_bool("RAG_CHUNK_QUALITY_ENABLED", "False"),
)
RAG_COLUMN_PROFILER_ENABLED = PersistentConfig(
    "RAG_COLUMN_PROFILER_ENABLED",
    "rag.column_profiler.enabled",
    _env_bool("RAG_COLUMN_PROFILER_ENABLED", "False"),
)

# 2.4 Chat data retention + pre-purge anonymization (GDPR/PIPA).
# CHAT_RETENTION_DAYS = 0 disables retention. When ANONYMIZE is true the daily
# job PII-masks chats past the threshold (keeps the row); otherwise it deletes.
CHAT_RETENTION_DAYS = PersistentConfig(
    "CHAT_RETENTION_DAYS",
    "security.chat_retention.days",
    _env_int("CHAT_RETENTION_DAYS", "0"),
)
CHAT_RETENTION_ANONYMIZE = PersistentConfig(
    "CHAT_RETENTION_ANONYMIZE",
    "security.chat_retention.anonymize",
    _env_bool("CHAT_RETENTION_ANONYMIZE", "False"),
)

# 2.5 MFA (TOTP). MFA_ENABLED turns the feature on; sign-in then requires a TOTP
# code for users who have enrolled. MFA_REQUIRED_FOR_ADMIN flags un-enrolled
# admins so the UI can prompt enrollment (does not lock them out).
MFA_ENABLED = PersistentConfig(
    "MFA_ENABLED",
    "auth.mfa.enabled",
    _env_bool("MFA_ENABLED", "False"),
)
MFA_REQUIRED_FOR_ADMIN = PersistentConfig(
    "MFA_REQUIRED_FOR_ADMIN",
    "auth.mfa.required_for_admin",
    _env_bool("MFA_REQUIRED_FOR_ADMIN", "False"),
)

# 3.4 SCIM 2.0 provisioning (Okta/Entra auto-provisioning). The IdP authenticates
# to /api/v1/scim/v2/* with SCIM_TOKEN as a bearer token.
SCIM_ENABLED = PersistentConfig(
    "SCIM_ENABLED",
    "auth.scim.enabled",
    _env_bool("SCIM_ENABLED", "False"),
)
SCIM_TOKEN = PersistentConfig(
    "SCIM_TOKEN",
    "auth.scim.token",
    _env_str("SCIM_TOKEN"),
)

# Multi-Hop Retrieval
RAG_MULTI_HOP_ENABLED = PersistentConfig(
    "RAG_MULTI_HOP_ENABLED",
    "rag.multi_hop.enabled",
    _env_bool("RAG_MULTI_HOP_ENABLED", "False"),
)
RAG_MULTI_HOP_MAX_HOPS = PersistentConfig(
    "RAG_MULTI_HOP_MAX_HOPS",
    "rag.multi_hop.max_hops",
    _env_int("RAG_MULTI_HOP_MAX_HOPS", "3"),
)

# Multi-Query Weights
RAG_MULTI_QUERY_WEIGHT_ORIGINAL = PersistentConfig(
    "RAG_MULTI_QUERY_WEIGHT_ORIGINAL",
    "rag.multi_query.weight_original",
    _env_float("RAG_MULTI_QUERY_WEIGHT_ORIGINAL", "1.0"),
)
RAG_MULTI_QUERY_WEIGHT_EXPANDED = PersistentConfig(
    "RAG_MULTI_QUERY_WEIGHT_EXPANDED",
    "rag.multi_query.weight_expanded",
    _env_float("RAG_MULTI_QUERY_WEIGHT_EXPANDED", "0.5"),
)

# Parent-Child Chunking
RAG_PARENT_CHILD_ENABLED = PersistentConfig(
    "RAG_PARENT_CHILD_ENABLED",
    "rag.parent_child_enabled",
    _env_bool("RAG_PARENT_CHILD_ENABLED", "False"),
)
RAG_PARENT_CHILD_PARENT_SIZE = PersistentConfig(
    "RAG_PARENT_CHILD_PARENT_SIZE",
    "rag.parent_child_parent_size",
    _env_int("RAG_PARENT_CHILD_PARENT_SIZE", "2000"),
)
RAG_PARENT_CHILD_CHILD_SIZE = PersistentConfig(
    "RAG_PARENT_CHILD_CHILD_SIZE",
    "rag.parent_child_child_size",
    _env_int("RAG_PARENT_CHILD_CHILD_SIZE", "200"),
)

# Semantic Cache
RAG_SEMANTIC_CACHE_ENABLED = PersistentConfig(
    "RAG_SEMANTIC_CACHE_ENABLED",
    "rag.semantic_cache_enabled",
    _env_bool("RAG_SEMANTIC_CACHE_ENABLED", "False"),
)
RAG_SEMANTIC_CACHE_THRESHOLD = PersistentConfig(
    "RAG_SEMANTIC_CACHE_THRESHOLD",
    "rag.semantic_cache_threshold",
    _env_float("RAG_SEMANTIC_CACHE_THRESHOLD", "0.95"),
)
RAG_SEMANTIC_CACHE_TTL = PersistentConfig(
    "RAG_SEMANTIC_CACHE_TTL",
    "rag.semantic_cache_ttl",
    _env_int("RAG_SEMANTIC_CACHE_TTL", "3600"),
)

# Contextual Retrieval
RAG_CONTEXTUAL_RETRIEVAL_ENABLED = PersistentConfig(
    "RAG_CONTEXTUAL_RETRIEVAL_ENABLED",
    "rag.contextual_retrieval.enabled",
    _env_bool("RAG_CONTEXTUAL_RETRIEVAL_ENABLED", "False"),
)
RAG_CONTEXTUAL_RETRIEVAL_MODEL = PersistentConfig(
    "RAG_CONTEXTUAL_RETRIEVAL_MODEL",
    "rag.contextual_retrieval.model",
    _env_str("RAG_CONTEXTUAL_RETRIEVAL_MODEL"),
)
RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS = PersistentConfig(
    "RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS",
    "rag.contextual_retrieval.max_context_tokens",
    _env_int("RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS", "200"),
)
RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE = PersistentConfig(
    "RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE",
    "rag.contextual_retrieval.batch_size",
    _env_int("RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE", "10"),
)

# Cross-Encoder Reranking
RAG_CROSS_ENCODER_RERANKING_ENABLED = PersistentConfig(
    "RAG_CROSS_ENCODER_RERANKING_ENABLED",
    "rag.reranking.cross_encoder.enabled",
    _env_bool("RAG_CROSS_ENCODER_RERANKING_ENABLED", "False"),
)
RAG_CROSS_ENCODER_MODEL = PersistentConfig(
    "RAG_CROSS_ENCODER_MODEL",
    "rag.reranking.cross_encoder.model",
    os.environ.get("RAG_CROSS_ENCODER_MODEL", "BAAI/bge-reranker-v2-m3"),
)
RAG_CROSS_ENCODER_MAX_LENGTH = PersistentConfig(
    "RAG_CROSS_ENCODER_MAX_LENGTH",
    "rag.reranking.cross_encoder.max_length",
    _env_int("RAG_CROSS_ENCODER_MAX_LENGTH", "512"),
)
RAG_CROSS_ENCODER_TOP_K = PersistentConfig(
    "RAG_CROSS_ENCODER_TOP_K",
    "rag.reranking.cross_encoder.top_k",
    _env_int("RAG_CROSS_ENCODER_TOP_K", "10"),
)

# GraphRAG
RAG_GRAPH_ENABLED = PersistentConfig(
    "RAG_GRAPH_ENABLED",
    "rag.graph.enabled",
    _env_bool("RAG_GRAPH_ENABLED", "False"),
)
RAG_GRAPH_ENTITY_EXTRACTION_MODEL = PersistentConfig(
    "RAG_GRAPH_ENTITY_EXTRACTION_MODEL",
    "rag.graph.entity_extraction_model",
    _env_str("RAG_GRAPH_ENTITY_EXTRACTION_MODEL"),
)
RAG_GRAPH_MAX_ENTITIES = PersistentConfig(
    "RAG_GRAPH_MAX_ENTITIES",
    "rag.graph.max_entities",
    _env_int("RAG_GRAPH_MAX_ENTITIES", "100"),
)
RAG_GRAPH_MAX_RELATIONS = PersistentConfig(
    "RAG_GRAPH_MAX_RELATIONS",
    "rag.graph.max_relations",
    _env_int("RAG_GRAPH_MAX_RELATIONS", "100"),
)
RAG_GRAPH_COMMUNITY_DETECTION_ENABLED = PersistentConfig(
    "RAG_GRAPH_COMMUNITY_DETECTION_ENABLED",
    "rag.graph.community_detection.enabled",
    _env_bool("RAG_GRAPH_COMMUNITY_DETECTION_ENABLED", "True"),
)
RAG_GRAPH_MAX_HOPS = PersistentConfig(
    "RAG_GRAPH_MAX_HOPS",
    "rag.graph.max_hops",
    _env_int("RAG_GRAPH_MAX_HOPS", "2"),
)
# 3.2 Personalized PageRank ranking (HippoRAG) over the knowledge graph.
RAG_GRAPH_PPR_ENABLED = PersistentConfig(
    "RAG_GRAPH_PPR_ENABLED",
    "rag.graph.ppr.enabled",
    _env_bool("RAG_GRAPH_PPR_ENABLED", "True"),
)
# 3.2 Deterministic fact-worthiness gate: prune graph entities appearing in
# fewer than this many documents (0 disables pruning).
RAG_GRAPH_MIN_ENTITY_DOCS = PersistentConfig(
    "RAG_GRAPH_MIN_ENTITY_DOCS",
    "rag.graph.min_entity_docs",
    _env_int("RAG_GRAPH_MIN_ENTITY_DOCS", "1"),
)

# RAG Evaluation
RAG_EVALUATION_ENABLED = PersistentConfig(
    "RAG_EVALUATION_ENABLED",
    "rag.evaluation.enabled",
    _env_bool("RAG_EVALUATION_ENABLED", "False"),
)
RAG_EVALUATION_MODEL = PersistentConfig(
    "RAG_EVALUATION_MODEL",
    "rag.evaluation.model",
    _env_str("RAG_EVALUATION_MODEL"),
)
RAG_EVALUATION_METRICS = PersistentConfig(
    "RAG_EVALUATION_METRICS",
    "rag.evaluation.metrics",
    os.environ.get(
        "RAG_EVALUATION_METRICS", "faithfulness,relevance,context_precision"
    ),
)
RAG_EVALUATION_LOG_RESULTS = PersistentConfig(
    "RAG_EVALUATION_LOG_RESULTS",
    "rag.evaluation.log_results",
    _env_bool("RAG_EVALUATION_LOG_RESULTS", "True"),
)


# ===========================================================================
# SECTION: Security Guardrail (Model-Based)
# ===========================================================================

SECURITY_GUARDRAIL_ENABLED = PersistentConfig(
    "SECURITY_GUARDRAIL_ENABLED",
    "security.guardrail.enabled",
    _env_bool("SECURITY_GUARDRAIL_ENABLED", "False"),
)
SECURITY_GUARDRAIL_MODEL = PersistentConfig(
    "SECURITY_GUARDRAIL_MODEL",
    "security.guardrail.model",
    _env_str("SECURITY_GUARDRAIL_MODEL"),
)
SECURITY_GUARDRAIL_ACTION = PersistentConfig(
    "SECURITY_GUARDRAIL_ACTION",
    "security.guardrail.action",
    os.environ.get("SECURITY_GUARDRAIL_ACTION", "block"),
)
SECURITY_CANARY_TOKENS_ENABLED = PersistentConfig(
    "SECURITY_CANARY_TOKENS_ENABLED",
    "security.canary_tokens.enabled",
    _env_bool("SECURITY_CANARY_TOKENS_ENABLED", "False"),
)
SECURITY_CANARY_TOKEN_POSITION = PersistentConfig(
    "SECURITY_CANARY_TOKEN_POSITION",
    "security.canary_tokens.position",
    os.environ.get("SECURITY_CANARY_TOKEN_POSITION", "system_prompt_end"),
)
SECURITY_SIEM_WEBHOOK_ENABLED = PersistentConfig(
    "SECURITY_SIEM_WEBHOOK_ENABLED",
    "security.siem.webhook.enabled",
    _env_bool("SECURITY_SIEM_WEBHOOK_ENABLED", "False"),
)
SECURITY_SIEM_WEBHOOK_URL = PersistentConfig(
    "SECURITY_SIEM_WEBHOOK_URL",
    "security.siem.webhook.url",
    _env_str("SECURITY_SIEM_WEBHOOK_URL"),
)
SECURITY_SIEM_WEBHOOK_HEADERS = PersistentConfig(
    "SECURITY_SIEM_WEBHOOK_HEADERS",
    "security.siem.webhook.headers",
    os.environ.get("SECURITY_SIEM_WEBHOOK_HEADERS", "{}"),
)


# ===========================================================================
# SECTION: Web Search Providers
# ===========================================================================

RAG_WEB_SEARCH_DOMAIN_FILTER_LIST = PersistentConfig(
    "RAG_WEB_SEARCH_DOMAIN_FILTER_LIST",
    "rag.web.search.domain.filter_list",
    [],
)

RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED = PersistentConfig(
    "RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED",
    "rag.web.search.query_rewrite_enabled",
    _env_bool("RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED", "True"),
)

RAG_WEB_SEARCH_QUERY_REWRITE_MODEL = PersistentConfig(
    "RAG_WEB_SEARCH_QUERY_REWRITE_MODEL",
    "rag.web.search.query_rewrite_model",
    _env_str("RAG_WEB_SEARCH_QUERY_REWRITE_MODEL"),
)

RAG_WEB_SEARCH_CONCURRENT_QUERIES = PersistentConfig(
    "RAG_WEB_SEARCH_CONCURRENT_QUERIES",
    "rag.web.search.concurrent_queries",
    _env_bool("RAG_WEB_SEARCH_CONCURRENT_QUERIES", "True"),
)

SEARXNG_QUERY_URL = PersistentConfig(
    "SEARXNG_QUERY_URL",
    "rag.web.search.searxng_query_url",
    _env_str("SEARXNG_QUERY_URL"),
)

GOOGLE_PSE_API_KEY = PersistentConfig(
    "GOOGLE_PSE_API_KEY",
    "rag.web.search.google_pse_api_key",
    _env_str("GOOGLE_PSE_API_KEY"),
)

GOOGLE_PSE_ENGINE_ID = PersistentConfig(
    "GOOGLE_PSE_ENGINE_ID",
    "rag.web.search.google_pse_engine_id",
    _env_str("GOOGLE_PSE_ENGINE_ID"),
)

BRAVE_SEARCH_API_KEY = PersistentConfig(
    "BRAVE_SEARCH_API_KEY",
    "rag.web.search.brave_search_api_key",
    _env_str("BRAVE_SEARCH_API_KEY"),
)

NAVER_CLIENT_ID = PersistentConfig(
    "NAVER_CLIENT_ID",
    "rag.web.search.naver_client_id",
    _env_str("NAVER_CLIENT_ID"),
)

NAVER_CLIENT_SECRET = PersistentConfig(
    "NAVER_CLIENT_SECRET",
    "rag.web.search.naver_client_secret",
    _env_str("NAVER_CLIENT_SECRET"),
)

NAVER_SEARCH_ENDPOINTS = PersistentConfig(
    "NAVER_SEARCH_ENDPOINTS",
    "rag.web.search.naver_search_endpoints",
    _env_str("NAVER_SEARCH_ENDPOINTS", "webkr"),
)

KAGI_SEARCH_API_KEY = PersistentConfig(
    "KAGI_SEARCH_API_KEY",
    "rag.web.search.kagi_search_api_key",
    _env_str("KAGI_SEARCH_API_KEY"),
)

MOJEEK_SEARCH_API_KEY = PersistentConfig(
    "MOJEEK_SEARCH_API_KEY",
    "rag.web.search.mojeek_search_api_key",
    _env_str("MOJEEK_SEARCH_API_KEY"),
)

BOCHA_SEARCH_API_KEY = PersistentConfig(
    "BOCHA_SEARCH_API_KEY",
    "rag.web.search.bocha_search_api_key",
    _env_str("BOCHA_SEARCH_API_KEY"),
)

SERPSTACK_API_KEY = PersistentConfig(
    "SERPSTACK_API_KEY",
    "rag.web.search.serpstack_api_key",
    _env_str("SERPSTACK_API_KEY"),
)

SERPSTACK_HTTPS = PersistentConfig(
    "SERPSTACK_HTTPS",
    "rag.web.search.serpstack_https",
    _env_bool("SERPSTACK_HTTPS", "True"),
)

SERPER_API_KEY = PersistentConfig(
    "SERPER_API_KEY",
    "rag.web.search.serper_api_key",
    _env_str("SERPER_API_KEY"),
)

SERPLY_API_KEY = PersistentConfig(
    "SERPLY_API_KEY",
    "rag.web.search.serply_api_key",
    _env_str("SERPLY_API_KEY"),
)

TAVILY_API_KEY = PersistentConfig(
    "TAVILY_API_KEY",
    "rag.web.search.tavily_api_key",
    _env_str("TAVILY_API_KEY"),
)

TAVILY_EXTRACT_DEPTH = PersistentConfig(
    "TAVILY_EXTRACT_DEPTH",
    "rag.web.search.tavily_extract_depth",
    _env_str("TAVILY_EXTRACT_DEPTH", "basic"),
)

JINA_API_KEY = PersistentConfig(
    "JINA_API_KEY",
    "rag.web.search.jina_api_key",
    _env_str("JINA_API_KEY"),
)

SEARCHAPI_API_KEY = PersistentConfig(
    "SEARCHAPI_API_KEY",
    "rag.web.search.searchapi_api_key",
    _env_str("SEARCHAPI_API_KEY"),
)

SEARCHAPI_ENGINE = PersistentConfig(
    "SEARCHAPI_ENGINE",
    "rag.web.search.searchapi_engine",
    _env_str("SEARCHAPI_ENGINE"),
)

SERPAPI_API_KEY = PersistentConfig(
    "SERPAPI_API_KEY",
    "rag.web.search.serpapi_api_key",
    _env_str("SERPAPI_API_KEY"),
)

SERPAPI_ENGINE = PersistentConfig(
    "SERPAPI_ENGINE",
    "rag.web.search.serpapi_engine",
    _env_str("SERPAPI_ENGINE"),
)

BING_SEARCH_V7_ENDPOINT = PersistentConfig(
    "BING_SEARCH_V7_ENDPOINT",
    "rag.web.search.bing_search_v7_endpoint",
    os.environ.get(
        "BING_SEARCH_V7_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
    ),
)

BING_SEARCH_V7_SUBSCRIPTION_KEY = PersistentConfig(
    "BING_SEARCH_V7_SUBSCRIPTION_KEY",
    "rag.web.search.bing_search_v7_subscription_key",
    _env_str("BING_SEARCH_V7_SUBSCRIPTION_KEY"),
)

EXA_API_KEY = PersistentConfig(
    "EXA_API_KEY",
    "rag.web.search.exa_api_key",
    _env_str("EXA_API_KEY"),
)

PERPLEXITY_API_KEY = PersistentConfig(
    "PERPLEXITY_API_KEY",
    "rag.web.search.perplexity_api_key",
    _env_str("PERPLEXITY_API_KEY"),
)

RAG_WEB_SEARCH_RESULT_COUNT = PersistentConfig(
    "RAG_WEB_SEARCH_RESULT_COUNT",
    "rag.web.search.result_count",
    _env_int("RAG_WEB_SEARCH_RESULT_COUNT", "3"),
)

RAG_WEB_SEARCH_CONCURRENT_REQUESTS = PersistentConfig(
    "RAG_WEB_SEARCH_CONCURRENT_REQUESTS",
    "rag.web.search.concurrent_requests",
    _env_int("RAG_WEB_SEARCH_CONCURRENT_REQUESTS", "10"),
)

RAG_WEB_LOADER_ENGINE = PersistentConfig(
    "RAG_WEB_LOADER_ENGINE",
    "rag.web.loader.engine",
    _env_str("RAG_WEB_LOADER_ENGINE", "safe_web"),
)

RAG_WEB_SEARCH_TRUST_ENV = PersistentConfig(
    "RAG_WEB_SEARCH_TRUST_ENV",
    "rag.web.search.trust_env",
    _env_bool("RAG_WEB_SEARCH_TRUST_ENV", "False"),
)

PLAYWRIGHT_WS_URI = PersistentConfig(
    "PLAYWRIGHT_WS_URI",
    "rag.web.loader.engine.playwright.ws.uri",
    _env_str_or_none("PLAYWRIGHT_WS_URI"),
)

PLAYWRIGHT_TIMEOUT = PersistentConfig(
    "PLAYWRIGHT_TIMEOUT",
    "rag.web.loader.engine.playwright.timeout",
    _env_int("PLAYWRIGHT_TIMEOUT", "10"),
)

FIRECRAWL_API_KEY = PersistentConfig(
    "FIRECRAWL_API_KEY",
    "firecrawl.api_key",
    _env_str("FIRECRAWL_API_KEY"),
)

FIRECRAWL_API_BASE_URL = PersistentConfig(
    "FIRECRAWL_API_BASE_URL",
    "firecrawl.api_url",
    os.environ.get("FIRECRAWL_API_BASE_URL", "https://api.firecrawl.dev"),
)


# ===========================================================================
# SECTION: Image Generation
# ===========================================================================

IMAGE_GENERATION_ENGINE = PersistentConfig(
    "IMAGE_GENERATION_ENGINE",
    "image_generation.engine",
    _env_str("IMAGE_GENERATION_ENGINE", "openai"),
)

ENABLE_IMAGE_GENERATION = PersistentConfig(
    "ENABLE_IMAGE_GENERATION",
    "image_generation.enable",
    _env_bool("ENABLE_IMAGE_GENERATION", ""),
)

ENABLE_IMAGE_PROMPT_GENERATION = PersistentConfig(
    "ENABLE_IMAGE_PROMPT_GENERATION",
    "image_generation.prompt.enable",
    _env_bool("ENABLE_IMAGE_PROMPT_GENERATION", "true"),
)

ENABLE_IMAGE_PROMPT_TRANSLATION = PersistentConfig(
    "ENABLE_IMAGE_PROMPT_TRANSLATION",
    "image_generation.prompt.translation",
    _env_bool("ENABLE_IMAGE_PROMPT_TRANSLATION", "true"),
)

ENABLE_IMAGE_PROMPT_EXPANSION = PersistentConfig(
    "ENABLE_IMAGE_PROMPT_EXPANSION",
    "image_generation.prompt.expansion",
    _env_bool("ENABLE_IMAGE_PROMPT_EXPANSION", "true"),
)

# AUTOMATIC1111
AUTOMATIC1111_BASE_URL = PersistentConfig(
    "AUTOMATIC1111_BASE_URL",
    "image_generation.automatic1111.base_url",
    _env_str("AUTOMATIC1111_BASE_URL"),
)

AUTOMATIC1111_API_AUTH = PersistentConfig(
    "AUTOMATIC1111_API_AUTH",
    "image_generation.automatic1111.api_auth",
    _env_str("AUTOMATIC1111_API_AUTH"),
)

AUTOMATIC1111_CFG_SCALE = PersistentConfig(
    "AUTOMATIC1111_CFG_SCALE",
    "image_generation.automatic1111.cfg_scale",
    float(v) if (v := os.environ.get("AUTOMATIC1111_CFG_SCALE")) else None,
)

AUTOMATIC1111_SAMPLER = PersistentConfig(
    "AUTOMATIC1111_SAMPLER",
    "image_generation.automatic1111.sampler",
    _env_str_or_none("AUTOMATIC1111_SAMPLER"),
)

AUTOMATIC1111_SCHEDULER = PersistentConfig(
    "AUTOMATIC1111_SCHEDULER",
    "image_generation.automatic1111.scheduler",
    _env_str_or_none("AUTOMATIC1111_SCHEDULER"),
)

# ComfyUI
COMFYUI_BASE_URL = PersistentConfig(
    "COMFYUI_BASE_URL",
    "image_generation.comfyui.base_url",
    _env_str("COMFYUI_BASE_URL"),
)

COMFYUI_API_KEY = PersistentConfig(
    "COMFYUI_API_KEY",
    "image_generation.comfyui.api_key",
    _env_str("COMFYUI_API_KEY"),
)

COMFYUI_DEFAULT_WORKFLOW = """
{
  "3": {
    "inputs": {
      "seed": 0,
      "steps": 20,
      "cfg": 8,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1,
      "model": [
        "4",
        0
      ],
      "positive": [
        "6",
        0
      ],
      "negative": [
        "7",
        0
      ],
      "latent_image": [
        "5",
        0
      ]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "KSampler"
    }
  },
  "4": {
    "inputs": {
      "ckpt_name": "model.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": {
      "title": "Load Checkpoint"
    }
  },
  "5": {
    "inputs": {
      "width": 512,
      "height": 512,
      "batch_size": 1
    },
    "class_type": "EmptyLatentImage",
    "_meta": {
      "title": "Empty Latent Image"
    }
  },
  "6": {
    "inputs": {
      "text": "Prompt",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "7": {
    "inputs": {
      "text": "",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "8": {
    "inputs": {
      "samples": [
        "3",
        0
      ],
      "vae": [
        "4",
        2
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE Decode"
    }
  },
  "9": {
    "inputs": {
      "filename_prefix": "ComfyUI",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "Save Image"
    }
  }
}
"""

COMFYUI_WORKFLOW = PersistentConfig(
    "COMFYUI_WORKFLOW",
    "image_generation.comfyui.workflow",
    os.getenv("COMFYUI_WORKFLOW", COMFYUI_DEFAULT_WORKFLOW),
)

COMFYUI_WORKFLOW_NODES = PersistentConfig(
    "COMFYUI_WORKFLOW",
    "image_generation.comfyui.nodes",
    [],
)

IMAGES_OPENAI_API_BASE_URL = PersistentConfig(
    "IMAGES_OPENAI_API_BASE_URL",
    "image_generation.openai.api_base_url",
    os.getenv("IMAGES_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
IMAGES_OPENAI_API_KEY = PersistentConfig(
    "IMAGES_OPENAI_API_KEY",
    "image_generation.openai.api_key",
    os.getenv("IMAGES_OPENAI_API_KEY", OPENAI_API_KEY),
)

IMAGES_GEMINI_API_BASE_URL = PersistentConfig(
    "IMAGES_GEMINI_API_BASE_URL",
    "image_generation.gemini.api_base_url",
    os.getenv("IMAGES_GEMINI_API_BASE_URL", GEMINI_API_BASE_URL),
)
IMAGES_GEMINI_API_KEY = PersistentConfig(
    "IMAGES_GEMINI_API_KEY",
    "image_generation.gemini.api_key",
    os.getenv("IMAGES_GEMINI_API_KEY", GEMINI_API_KEY),
)

IMAGE_SIZE = PersistentConfig(
    "IMAGE_SIZE", "image_generation.size", _env_str("IMAGE_SIZE", "512x512")
)

IMAGE_STEPS = PersistentConfig(
    "IMAGE_STEPS", "image_generation.steps", _env_int("IMAGE_STEPS", "50")
)

IMAGE_GENERATION_MODEL = PersistentConfig(
    "IMAGE_GENERATION_MODEL",
    "image_generation.model",
    _env_str("IMAGE_GENERATION_MODEL"),
)


# ===========================================================================
# SECTION: Audio (STT / TTS)
# ===========================================================================

DEEPGRAM_API_KEY = PersistentConfig(
    "DEEPGRAM_API_KEY",
    "audio.stt.deepgram.api_key",
    _env_str("DEEPGRAM_API_KEY"),
)

AUDIO_STT_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_STT_OPENAI_API_BASE_URL",
    "audio.stt.openai.api_base_url",
    os.getenv("AUDIO_STT_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)

AUDIO_STT_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_STT_OPENAI_API_KEY",
    "audio.stt.openai.api_key",
    os.getenv("AUDIO_STT_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_STT_ENGINE = PersistentConfig(
    "AUDIO_STT_ENGINE",
    "audio.stt.engine",
    _env_str("AUDIO_STT_ENGINE"),
)

AUDIO_STT_MODEL = PersistentConfig(
    "AUDIO_STT_MODEL",
    "audio.stt.model",
    _env_str("AUDIO_STT_MODEL"),
)

AUDIO_TTS_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_BASE_URL",
    "audio.tts.openai.api_base_url",
    os.getenv("AUDIO_TTS_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
AUDIO_TTS_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_KEY",
    "audio.tts.openai.api_key",
    os.getenv("AUDIO_TTS_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_TTS_API_KEY = PersistentConfig(
    "AUDIO_TTS_API_KEY",
    "audio.tts.api_key",
    _env_str("AUDIO_TTS_API_KEY"),
)

AUDIO_TTS_ENGINE = PersistentConfig(
    "AUDIO_TTS_ENGINE",
    "audio.tts.engine",
    _env_str("AUDIO_TTS_ENGINE"),
)

AUDIO_TTS_MODEL = PersistentConfig(
    "AUDIO_TTS_MODEL",
    "audio.tts.model",
    _env_str("AUDIO_TTS_MODEL", "tts-1"),
)

AUDIO_TTS_VOICE = PersistentConfig(
    "AUDIO_TTS_VOICE",
    "audio.tts.voice",
    _env_str("AUDIO_TTS_VOICE", "alloy"),
)

AUDIO_TTS_SPLIT_ON = PersistentConfig(
    "AUDIO_TTS_SPLIT_ON",
    "audio.tts.split_on",
    _env_str("AUDIO_TTS_SPLIT_ON", "punctuation"),
)

AUDIO_TTS_AZURE_SPEECH_REGION = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_REGION",
    "audio.tts.azure.speech_region",
    _env_str("AUDIO_TTS_AZURE_SPEECH_REGION", "eastus"),
)

AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT",
    "audio.tts.azure.speech_output_format",
    os.getenv(
        "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT", "audio-24khz-160kbitrate-mono-mp3"
    ),
)


# ===========================================================================
# SECTION: LDAP
# ===========================================================================

ENABLE_LDAP = PersistentConfig(
    "ENABLE_LDAP",
    "ldap.enable",
    _env_bool("ENABLE_LDAP", "false"),
)

LDAP_SERVER_LABEL = PersistentConfig(
    "LDAP_SERVER_LABEL",
    "ldap.server.label",
    _env_str("LDAP_SERVER_LABEL", "LDAP Server"),
)

LDAP_SERVER_HOST = PersistentConfig(
    "LDAP_SERVER_HOST",
    "ldap.server.host",
    _env_str("LDAP_SERVER_HOST", "localhost"),
)

LDAP_SERVER_PORT = PersistentConfig(
    "LDAP_SERVER_PORT",
    "ldap.server.port",
    _env_int("LDAP_SERVER_PORT", "389"),
)

LDAP_ATTRIBUTE_FOR_MAIL = PersistentConfig(
    "LDAP_ATTRIBUTE_FOR_MAIL",
    "ldap.server.attribute_for_mail",
    _env_str("LDAP_ATTRIBUTE_FOR_MAIL", "mail"),
)

LDAP_ATTRIBUTE_FOR_USERNAME = PersistentConfig(
    "LDAP_ATTRIBUTE_FOR_USERNAME",
    "ldap.server.attribute_for_username",
    _env_str("LDAP_ATTRIBUTE_FOR_USERNAME", "uid"),
)

LDAP_APP_DN = PersistentConfig(
    "LDAP_APP_DN", "ldap.server.app_dn", _env_str("LDAP_APP_DN")
)

LDAP_APP_PASSWORD = PersistentConfig(
    "LDAP_APP_PASSWORD",
    "ldap.server.app_password",
    _env_str("LDAP_APP_PASSWORD"),
)

LDAP_SEARCH_BASE = PersistentConfig(
    "LDAP_SEARCH_BASE", "ldap.server.users_dn", _env_str("LDAP_SEARCH_BASE")
)

LDAP_SEARCH_FILTERS = PersistentConfig(
    "LDAP_SEARCH_FILTER",
    "ldap.server.search_filter",
    os.environ.get("LDAP_SEARCH_FILTER", os.environ.get("LDAP_SEARCH_FILTERS", "")),
)

LDAP_USE_TLS = PersistentConfig(
    "LDAP_USE_TLS",
    "ldap.server.use_tls",
    _env_bool("LDAP_USE_TLS", "True"),
)

LDAP_CA_CERT_FILE = PersistentConfig(
    "LDAP_CA_CERT_FILE",
    "ldap.server.ca_cert_file",
    _env_str("LDAP_CA_CERT_FILE"),
)

LDAP_CIPHERS = PersistentConfig(
    "LDAP_CIPHERS", "ldap.server.ciphers", _env_str("LDAP_CIPHERS", "ALL")
)


# ===========================================================================
# SECTION: Security Scanner Pipeline
# ===========================================================================

SECURITY_SCANNER_ENABLED = PersistentConfig(
    "SECURITY_SCANNER_ENABLED",
    "security.scanner.enabled",
    _env_bool("SECURITY_SCANNER_ENABLED", "False"),
)

SECURITY_SHADOW_MODE = PersistentConfig(
    "SECURITY_SHADOW_MODE",
    "security.shadow_mode",
    _env_bool("SECURITY_SHADOW_MODE", "True"),
)

SECURITY_FAIL_CLOSED = PersistentConfig(
    "SECURITY_FAIL_CLOSED",
    "security.fail_closed",
    _env_bool("SECURITY_FAIL_CLOSED", "False"),
)

SECURITY_OUTPUT_ENFORCEMENT = PersistentConfig(
    "SECURITY_OUTPUT_ENFORCEMENT",
    "security.output_enforcement",
    _env_bool("SECURITY_OUTPUT_ENFORCEMENT", "False"),
)

SECURITY_PRESET = PersistentConfig(
    "SECURITY_PRESET",
    "security.preset",
    os.environ.get("SECURITY_PRESET", ""),
)

SECURITY_LOG_DETECTIONS = PersistentConfig(
    "SECURITY_LOG_DETECTIONS",
    "security.log_detections",
    _env_bool("SECURITY_LOG_DETECTIONS", "True"),
)

SECURITY_PROMPT_INJECTION_ENABLED = PersistentConfig(
    "SECURITY_PROMPT_INJECTION_ENABLED",
    "security.scanners.prompt_injection.enabled",
    _env_bool("SECURITY_PROMPT_INJECTION_ENABLED", "False"),
)

SECURITY_JAILBREAK_ENABLED = PersistentConfig(
    "SECURITY_JAILBREAK_ENABLED",
    "security.scanners.jailbreak.enabled",
    _env_bool("SECURITY_JAILBREAK_ENABLED", "False"),
)

SECURITY_PII_ENABLED = PersistentConfig(
    "SECURITY_PII_ENABLED",
    "security.scanners.pii.enabled",
    _env_bool("SECURITY_PII_ENABLED", "False"),
)

SECURITY_PII_MASK_MODE = PersistentConfig(
    "SECURITY_PII_MASK_MODE",
    "security.scanners.pii.mask_mode",
    _env_str("SECURITY_PII_MASK_MODE", "redact"),
)

SECURITY_TOXICITY_ENABLED = PersistentConfig(
    "SECURITY_TOXICITY_ENABLED",
    "security.scanners.toxicity.enabled",
    _env_bool("SECURITY_TOXICITY_ENABLED", "False"),
)

SECURITY_TOXICITY_CUSTOM_WORD_LIST = PersistentConfig(
    "SECURITY_TOXICITY_CUSTOM_WORD_LIST",
    "security.scanners.toxicity.custom_word_list",
    _env_str("SECURITY_TOXICITY_CUSTOM_WORD_LIST"),
)

SECURITY_SECRETS_ENABLED = PersistentConfig(
    "SECURITY_SECRETS_ENABLED",
    "security.scanners.secrets.enabled",
    _env_bool("SECURITY_SECRETS_ENABLED", "False"),
)

SECURITY_OUTPUT_FILTER_ENABLED = PersistentConfig(
    "SECURITY_OUTPUT_FILTER_ENABLED",
    "security.scanners.output_filter.enabled",
    _env_bool("SECURITY_OUTPUT_FILTER_ENABLED", "False"),
)

SECURITY_EVENT_RETENTION_DAYS = PersistentConfig(
    "SECURITY_EVENT_RETENTION_DAYS",
    "security.event_retention_days",
    _env_int("SECURITY_EVENT_RETENTION_DAYS", "1825"),
)

SECURITY_EMERGENCY_STOP = PersistentConfig(
    "SECURITY_EMERGENCY_STOP",
    "security.emergency_stop",
    _env_bool("SECURITY_EMERGENCY_STOP", "False"),
)

SECURITY_CONVERSATION_SCANNING_ENABLED = PersistentConfig(
    "SECURITY_CONVERSATION_SCANNING_ENABLED",
    "security.conversation_scanning_enabled",
    _env_bool("SECURITY_CONVERSATION_SCANNING_ENABLED", "False"),
)

SECURITY_CONVERSATION_THRESHOLD = PersistentConfig(
    "SECURITY_CONVERSATION_THRESHOLD",
    "security.conversation_threshold",
    os.environ.get("SECURITY_CONVERSATION_THRESHOLD", "2.0"),
)

SECURITY_CONFIDENCE_THRESHOLD = PersistentConfig(
    "SECURITY_CONFIDENCE_THRESHOLD",
    "security.confidence_threshold",
    os.environ.get("SECURITY_CONFIDENCE_THRESHOLD", "0.0"),
)

SECURITY_SCAN_FILE_UPLOADS = PersistentConfig(
    "SECURITY_SCAN_FILE_UPLOADS",
    "security.scan_file_uploads",
    _env_bool("SECURITY_SCAN_FILE_UPLOADS", "True"),
)

SECURITY_SCAN_WEB_RESULTS = PersistentConfig(
    "SECURITY_SCAN_WEB_RESULTS",
    "security.scan_web_results",
    _env_bool("SECURITY_SCAN_WEB_RESULTS", "True"),
)

SECURITY_LLM_SCANNER_ENABLED = PersistentConfig(
    "SECURITY_LLM_SCANNER_ENABLED",
    "security.scanners.llm.enabled",
    _env_bool("SECURITY_LLM_SCANNER_ENABLED", "False"),
)

SECURITY_LLM_SCANNER_MODEL = PersistentConfig(
    "SECURITY_LLM_SCANNER_MODEL",
    "security.scanners.llm.model",
    _env_str("SECURITY_LLM_SCANNER_MODEL"),
)


# ===========================================================================
# SECTION: AI Transparency (Korean AI Basic Act Compliance)
# ===========================================================================

AI_TRANSPARENCY_ENABLED = PersistentConfig(
    "AI_TRANSPARENCY_ENABLED",
    "ai_transparency.enabled",
    _env_bool("AI_TRANSPARENCY_ENABLED", "True"),
)

AI_NOTIFICATION_TITLE = PersistentConfig(
    "AI_NOTIFICATION_TITLE",
    "ai_transparency.notification_title",
    _env_str("AI_NOTIFICATION_TITLE", "AI Assistant Notice"),
)

AI_NOTIFICATION_MESSAGE = PersistentConfig(
    "AI_NOTIFICATION_MESSAGE",
    "ai_transparency.notification_message",
    os.environ.get(
        "AI_NOTIFICATION_MESSAGE",
        "This service utilizes generative AI. AI responses are for reference only. Please consult with the relevant staff for important financial transaction decisions.",
    ),
)

AI_DISCLAIMER_TEXT = PersistentConfig(
    "AI_DISCLAIMER_TEXT",
    "ai_transparency.disclaimer_text",
    os.environ.get(
        "AI_DISCLAIMER_TEXT",
        "AI responses are for reference only. Please contact the responsible staff for final confirmation regarding financial transactions.",
    ),
)

AI_RESPONSE_LABEL = PersistentConfig(
    "AI_RESPONSE_LABEL",
    "ai_transparency.response_label",
    _env_str("AI_RESPONSE_LABEL", "AI-Generated Response"),
)


# ===========================================================================
# SECTION: Prometheus Metrics
# ===========================================================================

PROMETHEUS_METRICS_ENABLED = PersistentConfig(
    "PROMETHEUS_METRICS_ENABLED",
    "observability.prometheus_metrics_enabled",
    _env_bool("PROMETHEUS_METRICS_ENABLED", "False"),
)


# ===========================================================================
# SECTION: Agent Handoff
# ===========================================================================

HANDOFF_ENABLED = PersistentConfig(
    "HANDOFF_ENABLED",
    "features.handoff.enabled",
    _env_bool("HANDOFF_ENABLED", "True"),
)

HANDOFF_EMAIL_ENABLED = PersistentConfig(
    "HANDOFF_EMAIL_ENABLED",
    "features.handoff.email_enabled",
    _env_bool("HANDOFF_EMAIL_ENABLED", "False"),
)

HANDOFF_EMAIL_RECIPIENTS = PersistentConfig(
    "HANDOFF_EMAIL_RECIPIENTS",
    "features.handoff.email_recipients",
    os.environ.get("HANDOFF_EMAIL_RECIPIENTS", "[]"),
)

HANDOFF_WEBHOOK_ENABLED = PersistentConfig(
    "HANDOFF_WEBHOOK_ENABLED",
    "features.handoff.webhook_enabled",
    _env_bool("HANDOFF_WEBHOOK_ENABLED", "False"),
)

HANDOFF_WEBHOOK_URL = PersistentConfig(
    "HANDOFF_WEBHOOK_URL",
    "features.handoff.webhook_url",
    _env_str("HANDOFF_WEBHOOK_URL"),
)


# ===========================================================================
# SECTION: Rate Limiting (OWASP LLM10)
# ===========================================================================

RATE_LIMIT_CHAT_ENABLED = PersistentConfig(
    "RATE_LIMIT_CHAT_ENABLED",
    "rate_limit.chat.enabled",
    _env_bool("RATE_LIMIT_CHAT_ENABLED", "True"),
)
RATE_LIMIT_CHAT_PER_MINUTE = PersistentConfig(
    "RATE_LIMIT_CHAT_PER_MINUTE",
    "rate_limit.chat.per_minute",
    _env_int("RATE_LIMIT_CHAT_PER_MINUTE", "30"),
)
RATE_LIMIT_CHAT_PER_HOUR = PersistentConfig(
    "RATE_LIMIT_CHAT_PER_HOUR",
    "rate_limit.chat.per_hour",
    _env_int("RATE_LIMIT_CHAT_PER_HOUR", "500"),
)
RATE_LIMIT_CHAT_PER_DAY = PersistentConfig(
    "RATE_LIMIT_CHAT_PER_DAY",
    "rate_limit.chat.per_day",
    _env_int("RATE_LIMIT_CHAT_PER_DAY", "5000"),
)


# ===========================================================================
# SECTION: Context Compression
# ===========================================================================

ENABLE_CONTEXT_COMPRESSION = PersistentConfig(
    "ENABLE_CONTEXT_COMPRESSION",
    "rag.context_compression.enabled",
    _env_bool("ENABLE_CONTEXT_COMPRESSION", "False"),
)

CONTEXT_COMPRESSION_MODEL = PersistentConfig(
    "CONTEXT_COMPRESSION_MODEL",
    "rag.context_compression.model",
    _env_str("CONTEXT_COMPRESSION_MODEL"),
)

CONTEXT_COMPRESSION_PROMPT_TEMPLATE = PersistentConfig(
    "CONTEXT_COMPRESSION_PROMPT_TEMPLATE",
    "rag.context_compression.prompt_template",
    _env_str("CONTEXT_COMPRESSION_PROMPT_TEMPLATE"),
)

DEFAULT_CONTEXT_COMPRESSION_PROMPT_TEMPLATE = """### Task:
Summarize the following conversation concisely, preserving all key facts, decisions, technical details, names, dates, and any important context. The summary will be used as context for continuing the conversation.

### Guidelines:
- Preserve all specific technical details, numbers, names, and decisions
- Keep the summary factual and objective
- Do not add information not present in the conversation
- Write in the same language as the conversation
- Keep the summary under 500 words
- Focus on information that would be needed to continue the conversation meaningfully

### Output:
Return ONLY the summary text. No JSON, no labels, no prefixes.

### Conversation to Summarize:
<conversation>
{{MESSAGES}}
</conversation>
"""


# ===========================================================================
# SECTION: Smart Query
# ===========================================================================

ENABLE_SMART_QUERY = PersistentConfig(
    "ENABLE_SMART_QUERY",
    "rag.smart_query.enabled",
    _env_bool("ENABLE_SMART_QUERY", "False"),
)

SMART_QUERY_MODEL = PersistentConfig(
    "SMART_QUERY_MODEL",
    "rag.smart_query.model",
    _env_str("SMART_QUERY_MODEL"),
)

SMART_QUERY_PROMPT_TEMPLATE = PersistentConfig(
    "SMART_QUERY_PROMPT_TEMPLATE",
    "rag.smart_query.prompt_template",
    _env_str("SMART_QUERY_PROMPT_TEMPLATE"),
)

DEFAULT_SMART_QUERY_PROMPT_TEMPLATE = """### Task:
Given the chat history and the current user question, rewrite the question to be a standalone, self-contained question that includes all necessary context from the conversation. This enhanced question will be used for information retrieval (web search, RAG).

### Guidelines:
- The rewritten question must be fully understandable WITHOUT the conversation history
- Include all relevant context (names, topics, specific details) from the conversation
- Keep the same language as the user's question
- Do NOT change the intent of the question
- Be concise but comprehensive
- If the question is already self-contained, return it as-is

### Output:
JSON format: { "query": "your enhanced question here" }

### Chat History:
<chat_history>
{{MESSAGES:END:10}}
</chat_history>

### Current Question:
{{prompt}}
"""


# ===========================================================================
# SECTION: Langfuse RAG Tracing
# ===========================================================================

RAG_TRACING_ENABLED = PersistentConfig(
    "RAG_TRACING_ENABLED",
    "rag.tracing_enabled",
    _env_bool("RAG_TRACING_ENABLED", "False"),
)

LANGFUSE_PUBLIC_KEY = PersistentConfig(
    "LANGFUSE_PUBLIC_KEY",
    "rag.langfuse_public_key",
    _env_str("LANGFUSE_PUBLIC_KEY"),
)

LANGFUSE_SECRET_KEY = PersistentConfig(
    "LANGFUSE_SECRET_KEY",
    "rag.langfuse_secret_key",
    _env_str("LANGFUSE_SECRET_KEY"),
)

LANGFUSE_HOST = PersistentConfig(
    "LANGFUSE_HOST",
    "rag.langfuse_host",
    os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


# ===========================================================================
# SECTION: AI Compliance Module
# Korean AI Basic Act (Law No. 20676), FSC Financial AI Guidelines,
# EU AI Act, ISO/IEC 42001, PIPA Art. 37-2
# ===========================================================================

# Master switch — when OFF, all compliance endpoints return 403
COMPLIANCE_ENABLED = PersistentConfig(
    "COMPLIANCE_ENABLED",
    "compliance.enabled",
    _env_bool("COMPLIANCE_ENABLED", "False"),
)

# 3.1 AI Model Inventory + risk tiering (AI Basic Act Art. 33)
COMPLIANCE_INVENTORY_ENABLED = PersistentConfig(
    "COMPLIANCE_INVENTORY_ENABLED",
    "compliance.inventory.enabled",
    _env_bool("COMPLIANCE_INVENTORY_ENABLED", "False"),
)

# 3.2 AIIA — AI Impact Assessment workflow (AI Basic Act Art. 35)
COMPLIANCE_AIIA_ENABLED = PersistentConfig(
    "COMPLIANCE_AIIA_ENABLED",
    "compliance.aiia.enabled",
    _env_bool("COMPLIANCE_AIIA_ENABLED", "False"),
)

# 3.4 HITL — Human-in-the-Loop approval gates (AI Basic Act Art. 34(1)(4))
COMPLIANCE_HITL_ENABLED = PersistentConfig(
    "COMPLIANCE_HITL_ENABLED",
    "compliance.hitl.enabled",
    _env_bool("COMPLIANCE_HITL_ENABLED", "False"),
)
COMPLIANCE_HITL_SLA_SECONDS = PersistentConfig(
    "COMPLIANCE_HITL_SLA_SECONDS",
    "compliance.hitl.sla_seconds",
    _env_int("COMPLIANCE_HITL_SLA_SECONDS", "300"),
)

# 3.5 AI Incident Response + regulatory reporting (EU AI Act Art. 73)
COMPLIANCE_INCIDENT_ENABLED = PersistentConfig(
    "COMPLIANCE_INCIDENT_ENABLED",
    "compliance.incident.enabled",
    _env_bool("COMPLIANCE_INCIDENT_ENABLED", "False"),
)

# 3.6 Fairness / Bias Testing (FSC principle "Reliability", EU Annex III)
COMPLIANCE_FAIRNESS_ENABLED = PersistentConfig(
    "COMPLIANCE_FAIRNESS_ENABLED",
    "compliance.fairness.enabled",
    _env_bool("COMPLIANCE_FAIRNESS_ENABLED", "False"),
)

# 3.7 RAG Provenance — tamper-evident retrieval chain (EU AI Act Art. 12)
COMPLIANCE_PROVENANCE_ENABLED = PersistentConfig(
    "COMPLIANCE_PROVENANCE_ENABLED",
    "compliance.provenance.enabled",
    _env_bool("COMPLIANCE_PROVENANCE_ENABLED", "False"),
)

# 3.9 DSAR — Data Subject Access Requests (PIPA Art. 37-2)
COMPLIANCE_DSAR_ENABLED = PersistentConfig(
    "COMPLIANCE_DSAR_ENABLED",
    "compliance.dsar.enabled",
    _env_bool("COMPLIANCE_DSAR_ENABLED", "False"),
)

# 3.10 Vendor / AIBOM management (NIST GOVERN-6, OWASP LLM03)
COMPLIANCE_VENDOR_ENABLED = PersistentConfig(
    "COMPLIANCE_VENDOR_ENABLED",
    "compliance.vendor.enabled",
    _env_bool("COMPLIANCE_VENDOR_ENABLED", "False"),
)
