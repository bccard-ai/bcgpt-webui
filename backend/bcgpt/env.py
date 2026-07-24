"""Application environment configuration.

Resolves all runtime settings from environment variables, .env files, and
package metadata.  Every public name in this module is a configuration value
consumed elsewhere in the codebase; nothing here should be considered private
or internal to the module.

Sections:
    Paths & Directories  - Filesystem layout for the application.
    Environment Metadata - Version, changelog, and branding.
    Device & Compute     - GPU / accelerator detection.
    Logging              - Global and per-subsystem log levels.
    Database             - Connection string and pool tuning.
    Redis                - Redis / Sentinel connection details.
    Authentication       - Auth mode, trusted headers, secrets, cookies.
    WebSocket            - WebSocket transport settings.
    HTTP Client          - aiohttp timeout knobs.
    Security             - Safe-mode, tool execution, forward headers.
    Audit                - Audit-log file, rotation, and filtering.
    OpenTelemetry        - Distributed tracing configuration.
    Offline Mode         - Air-gapped / offline deployment.
    Pip Options          - Extra pip flags for tool/function deps.
"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helper: parse ``"true"`` / ``"false"`` strings from env vars
# ---------------------------------------------------------------------------


def _env_bool(key: str, default: str = "False") -> bool:
    """Return a boolean parsed from an environment variable."""
    return os.environ.get(key, default).lower() == "true"


def _env_int(key: str, default: int) -> int:
    """Return an integer parsed from an environment variable, with fallback."""
    raw = os.environ.get(key, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Paths & Directories
# ---------------------------------------------------------------------------

#: Root of the ``bcgpt`` Python package (directory that contains this file).
BCGPT_DIR: Path = Path(__file__).resolve().parent

#: ``backend/`` directory (parent of the package).
BACKEND_DIR: Path = BCGPT_DIR.parent

#: Project root (parent of ``backend/``).
BASE_DIR: Path = BACKEND_DIR.parent

# ---------------------------------------------------------------------------
# .env loading (best-effort; ``python-dotenv`` is optional)
# ---------------------------------------------------------------------------

os.environ.setdefault("USER_AGENT", "bcgpt-webui")

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(str(BASE_DIR / ".env")))
except ImportError:
    pass

#: Whether the application is running inside a Docker container.
DOCKER: bool = _env_bool("DOCKER", "False")

#: ``True`` when invoked via ``python -m bcgpt`` (or ``bcgpt serve``).
FROM_INIT_PY: bool = _env_bool("FROM_INIT_PY", "False")

#: Primary data directory (database, uploads, etc.).
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BACKEND_DIR / "data"))).resolve()

if FROM_INIT_PY:
    _new_data_dir: Path = Path(os.getenv("DATA_DIR", str(BCGPT_DIR / "data"))).resolve()
    _new_data_dir.mkdir(parents=True, exist_ok=True)

    if DATA_DIR.exists() and DATA_DIR != _new_data_dir:
        _log_tmp = logging.getLogger(__name__)
        _log_tmp.info("Moving %s to %s", DATA_DIR, _new_data_dir)
        for _item in DATA_DIR.iterdir():
            _dest = _new_data_dir / _item.name
            if _item.is_dir():
                shutil.copytree(_item, _dest, dirs_exist_ok=True)
            else:
                shutil.copy2(_item, _dest)
        shutil.make_archive(DATA_DIR.parent / "bcgpt_data", "zip", DATA_DIR)
        shutil.rmtree(DATA_DIR)

    DATA_DIR = Path(os.getenv("DATA_DIR", str(BCGPT_DIR / "data")))

#: Static assets directory.
STATIC_DIR: Path = Path(os.getenv("STATIC_DIR", str(BCGPT_DIR / "static")))

#: Font files directory.
FONTS_DIR: Path = Path(os.getenv("FONTS_DIR", str(BCGPT_DIR / "static" / "fonts")))

#: Built frontend assets (HTML/JS/CSS produced by Vite).
FRONTEND_BUILD_DIR: Path = Path(
    os.getenv("FRONTEND_BUILD_DIR", str(BASE_DIR / "build"))
).resolve()

if FROM_INIT_PY:
    FRONTEND_BUILD_DIR = Path(
        os.getenv("FRONTEND_BUILD_DIR", str(BCGPT_DIR / "frontend"))
    ).resolve()

# ---------------------------------------------------------------------------
# Device & Compute
# ---------------------------------------------------------------------------

#: Detected accelerator: ``"cuda"``, ``"mps"``, or ``"cpu"``.
DEVICE_TYPE: str = "cpu"

_use_cuda = os.environ.get("USE_CUDA_DOCKER", "false")
if _use_cuda.lower() == "true":
    try:
        import torch

        assert torch.cuda.is_available(), "CUDA not available"
        DEVICE_TYPE = "cuda"
    except Exception as _exc:
        os.environ["USE_CUDA_DOCKER"] = "false"
        _use_cuda = "false"
        _cuda_error_msg = (
            "Error when testing CUDA but USE_CUDA_DOCKER is true. "
            f"Resetting USE_CUDA_DOCKER to false: {_exc}"
        )
    else:
        _cuda_error_msg = None
else:
    _cuda_error_msg = None

try:
    import torch

    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        DEVICE_TYPE = "mps"
except Exception:
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

#: Global log level string (e.g. ``"INFO"``, ``"DEBUG"``).
GLOBAL_LOG_LEVEL: str = os.environ.get("GLOBAL_LOG_LEVEL", "").upper()
if GLOBAL_LOG_LEVEL in logging.getLevelNamesMapping():
    logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)
else:
    GLOBAL_LOG_LEVEL = "INFO"

log: logging.Logger = logging.getLogger(__name__)
log.info("GLOBAL_LOG_LEVEL: %s", GLOBAL_LOG_LEVEL)

if _cuda_error_msg is not None:
    log.exception(_cuda_error_msg)

#: Per-subsystem log levels keyed by subsystem name.
SRC_LOG_LEVELS: dict[str, str] = {}

_LOG_SUBSYSTEMS: list[str] = [
    "AUDIO",
    "COMFYUI",
    "CONFIG",
    "DB",
    "IMAGES",
    "MAIN",
    "MODELS",
    "OLLAMA",
    "OPENAI",
    "RAG",
    "WEBHOOK",
    "SOCKET",
    "OAUTH",
]

for _subsystem in _LOG_SUBSYSTEMS:
    _env_key = f"{_subsystem}_LOG_LEVEL"
    _level = os.environ.get(_env_key, "").upper()
    if _level not in logging.getLevelNamesMapping():
        _level = GLOBAL_LOG_LEVEL
    SRC_LOG_LEVELS[_subsystem] = _level
    log.info("%s: %s", _env_key, _level)

log.setLevel(SRC_LOG_LEVELS["CONFIG"])

# ---------------------------------------------------------------------------
# Environment Metadata & Branding
# ---------------------------------------------------------------------------

#: Human-readable application name.
BCGPT_APP_NAME: str = "BCGPT"

#: Favicon path served by the web server.
BCGPT_FAVICON_URL: str = "/static/favicon.png"

#: Key for verifying signed payloads (webhooks, etc.).
TRUSTED_SIGNATURE_KEY: str = os.environ.get("TRUSTED_SIGNATURE_KEY", "")

#: Deployment environment: ``"dev"``, ``"test"``, or ``"prod"``.
ENV: str = os.environ.get("ENV", "dev")

if FROM_INIT_PY:
    PACKAGE_DATA: dict[str, str] = {"version": importlib.metadata.version("bcgpt")}
else:
    try:
        PACKAGE_DATA = json.loads((BASE_DIR / "package.json").read_text())
    except Exception:
        PACKAGE_DATA = {"version": "0.0.0"}

#: Application version (from ``package.json`` or package metadata).
VERSION: str = PACKAGE_DATA["version"]

# ---------------------------------------------------------------------------
# Changelog Parsing
# ---------------------------------------------------------------------------

import markdown as _markdown
from bs4 import BeautifulSoup as _BeautifulSoup


def _parse_changelog_section(section: "_Tag") -> list[dict[str, str]]:
    """Extract structured items from an HTML ``<ul>`` section of the changelog."""
    items: list[dict[str, str]] = []
    for li in section.find_all("li"):
        raw_html = str(li)
        text = li.get_text(separator=" ", strip=True)
        parts = text.split(": ", 1)
        title = parts[0].strip() if len(parts) > 1 else ""
        content = parts[1].strip() if len(parts) > 1 else text
        items.append({"title": title, "content": content, "raw": raw_html})
    return items


_changelog_content: str
try:
    _changelog_path = BASE_DIR / "CHANGELOG.md"
    _changelog_content = _changelog_path.read_text(encoding="utf-8")
except Exception:
    import pkgutil as _pkgutil

    _changelog_content = (_pkgutil.get_data("bcgpt", "CHANGELOG.md") or b"").decode()

_soup = _BeautifulSoup(_markdown.markdown(_changelog_content), "html.parser")
_changelog_json: dict[str, dict] = {}

for _version_tag in _soup.find_all("h2"):
    _tag_text = _version_tag.get_text().strip()
    _parts = _tag_text.split(" - ", 1)
    _version_number = _parts[0][1:-1]  # strip brackets
    _date = _parts[1] if len(_parts) > 1 else ""
    _version_data: dict[str, object] = {"date": _date}

    _current = _version_tag.find_next_sibling()
    while _current and _current.name != "h2":
        if _current.name == "h3":
            _section_title = _current.get_text().lower()
            _ul = _current.find_next_sibling("ul")
            if _ul:
                _version_data[_section_title] = _parse_changelog_section(_ul)
        _current = _current.find_next_sibling()

    _changelog_json[_version_number] = _version_data

#: Parsed changelog keyed by version string.
CHANGELOG: dict[str, dict] = _changelog_json

# ---------------------------------------------------------------------------
# Security Flags
# ---------------------------------------------------------------------------

#: Restrict potentially dangerous operations.
SAFE_MODE: bool = _env_bool("SAFE_MODE", "false")

#: Forward authenticated-user information headers to upstream LLM providers.
ENABLE_FORWARD_USER_INFO_HEADERS: bool = _env_bool(
    "ENABLE_FORWARD_USER_INFO_HEADERS", "False"
)

#: Git-style build hash injected at deploy time.
BCGPT_BUILD_HASH: str = os.environ.get("BCGPT_BUILD_HASH", "dev-build")

#: Allow non-admin users to author executable tool code (RCE risk).
TOOLS_ALLOW_NON_ADMIN_CODE: bool = _env_bool("TOOLS_ALLOW_NON_ADMIN_CODE", "False")

if TOOLS_ALLOW_NON_ADMIN_CODE:
    logging.getLogger(__name__).warning(
        "SECURITY: TOOLS_ALLOW_NON_ADMIN_CODE is enabled — non-admin users with the "
        "'workspace.tools' permission can author tool/function code that runs WITHOUT "
        "sandboxing (full process privileges). Ensure OS-level isolation is in place."
    )

#: Skip model-level access control checks.
BYPASS_MODEL_ACCESS_CONTROL: bool = _env_bool("BYPASS_MODEL_ACCESS_CONTROL", "False")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Legacy migration: rename ``ollama.db`` → ``bcgpt.db`` if it still exists.
if os.path.exists(str(DATA_DIR / "ollama.db")):
    os.rename(str(DATA_DIR / "ollama.db"), str(DATA_DIR / "bcgpt.db"))
    log.info("Database migrated from Ollama-WebUI successfully.")

#: SQLAlchemy connection string.
DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR}/bcgpt.db")

# Normalise ``postgres://`` → ``postgresql://`` (SQLAlchemy 2.x requirement).
if "postgres://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

#: Optional database schema (for PostgreSQL).
DATABASE_SCHEMA: str | None = os.environ.get("DATABASE_SCHEMA", None)

#: Connection pool size (0 = unlimited).
DATABASE_POOL_SIZE: int = _env_int("DATABASE_POOL_SIZE", 0)

#: Maximum overflow connections beyond the pool size.
DATABASE_POOL_MAX_OVERFLOW: int = _env_int("DATABASE_POOL_MAX_OVERFLOW", 0)

#: Seconds to wait for a connection from the pool.
DATABASE_POOL_TIMEOUT: int = _env_int("DATABASE_POOL_TIMEOUT", 30)

#: Seconds before a pooled connection is recycled.
DATABASE_POOL_RECYCLE: int = _env_int("DATABASE_POOL_RECYCLE", 3600)

#: Reset persisted config from the database on startup.
RESET_CONFIG_ON_START: bool = _env_bool("RESET_CONFIG_ON_START", "False")

#: Persist real-time chat events to the database as they stream.
ENABLE_REALTIME_CHAT_SAVE: bool = _env_bool("ENABLE_REALTIME_CHAT_SAVE", "False")

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

#: Redis connection URL (empty string disables Redis).
REDIS_URL: str = os.environ.get("REDIS_URL", "")

#: Comma-separated Redis Sentinel host addresses.
REDIS_SENTINEL_HOSTS: str = os.environ.get("REDIS_SENTINEL_HOSTS", "")

#: Redis Sentinel port.
REDIS_SENTINEL_PORT: str = os.environ.get("REDIS_SENTINEL_PORT", "26379")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

#: Master toggle: require authentication for all endpoints.
BCGPT_AUTH: bool = _env_bool("BCGPT_AUTH", "True")

#: Trusted header carrying the authenticated user's email (set by reverse proxy).
BCGPT_AUTH_TRUSTED_EMAIL_HEADER: str | None = os.environ.get(
    "BCGPT_AUTH_TRUSTED_EMAIL_HEADER", None
)

#: Trusted header carrying the authenticated user's display name.
BCGPT_AUTH_TRUSTED_NAME_HEADER: str | None = os.environ.get(
    "BCGPT_AUTH_TRUSTED_NAME_HEADER", None
)

#: CIDR / IP allowlist for trusted-header authentication.
BCGPT_AUTH_TRUSTED_PROXY_IPS: list[str] = [
    p.strip()
    for p in os.environ.get("BCGPT_AUTH_TRUSTED_PROXY_IPS", "").split(",")
    if p.strip()
]

if BCGPT_AUTH_TRUSTED_EMAIL_HEADER and not BCGPT_AUTH_TRUSTED_PROXY_IPS:
    logging.getLogger(__name__).warning(
        "SECURITY: BCGPT_AUTH_TRUSTED_EMAIL_HEADER is set but BCGPT_AUTH_TRUSTED_PROXY_IPS "
        "is empty — the email header is trusted from ANY source. If the backend port is "
        "reachable without traversing your proxy, anyone can authenticate as any user. "
        "Set BCGPT_AUTH_TRUSTED_PROXY_IPS to your proxy IP(s)/CIDR(s)."
    )

# -- Secret key & cookies --------------------------------------------------

#: Primary signing key for JWTs / sessions.
BCGPT_SECRET_KEY: str | None = os.environ.get(
    "BCGPT_SECRET_KEY",
) or os.environ.get("WEBUI_SECRET_KEY")

# ---------------------------------------------------------------------------
# JWT signing algorithm (open-moai adoption 3.4)
# HS256 (default; symmetric, uses BCGPT_SECRET_KEY) or RS256 (asymmetric — the
# public key is published at the JWKS endpoint, shrinking the HS256 shared-secret
# blast radius and enabling key rotation). For RS256 provide PEM keys inline
# (JWT_RSA_PRIVATE_KEY / JWT_RSA_PUBLIC_KEY, "\n"-escaped) or via *_FILE paths.
# Misconfiguration falls back to HS256 with a warning (utils/auth.py).
# ---------------------------------------------------------------------------
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256").upper()
JWT_KEY_ID: str = os.environ.get("JWT_KEY_ID", "bcgpt-key-1")


def _read_jwt_key(inline_var: str, file_var: str) -> str | None:
    inline = os.environ.get(inline_var)
    if inline:
        return inline.replace("\\n", "\n")
    path = os.environ.get(file_var)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except Exception:
            return None
    return None


JWT_RSA_PRIVATE_KEY: str | None = _read_jwt_key(
    "JWT_RSA_PRIVATE_KEY", "JWT_RSA_PRIVATE_KEY_FILE"
)
JWT_RSA_PUBLIC_KEY: str | None = _read_jwt_key(
    "JWT_RSA_PUBLIC_KEY", "JWT_RSA_PUBLIC_KEY_FILE"
)

#: ``SameSite`` attribute on the session cookie.
BCGPT_SESSION_COOKIE_SAME_SITE: str = os.environ.get(
    "BCGPT_SESSION_COOKIE_SAME_SITE", "lax"
)

#: Whether the session cookie sets the ``Secure`` flag.
#: Defaults to True (secure by default, for HTTPS deployments). Development (`bun run dev` →
#: watch-backend.js) overrides this with BCGPT_SESSION_COOKIE_SECURE=false for http://localhost.
BCGPT_SESSION_COOKIE_SECURE: bool = _env_bool("BCGPT_SESSION_COOKIE_SECURE", "true")

#: ``SameSite`` attribute on the auth cookie.
BCGPT_AUTH_COOKIE_SAME_SITE: str = os.environ.get(
    "BCGPT_AUTH_COOKIE_SAME_SITE", BCGPT_SESSION_COOKIE_SAME_SITE
)

#: Whether the auth cookie sets the ``Secure`` flag.
BCGPT_AUTH_COOKIE_SECURE: bool = (
    os.environ.get(
        "BCGPT_AUTH_COOKIE_SECURE",
        os.environ.get("BCGPT_SESSION_COOKIE_SECURE", "false"),
    ).lower()
    == "true"
)

if BCGPT_AUTH and not BCGPT_SECRET_KEY:
    from bcgpt.constants import ERROR_MESSAGES

    raise ValueError(ERROR_MESSAGES.ENV_VAR_NOT_FOUND)

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

#: Enable WebSocket transport for real-time features.
ENABLE_WEBSOCKET_SUPPORT: bool = _env_bool("ENABLE_WEBSOCKET_SUPPORT", "True")

#: WebSocket manager backend (``""`` = in-process, ``"redis"``).
WEBSOCKET_MANAGER: str = os.environ.get("WEBSOCKET_MANAGER", "")

#: Redis URL used by the WebSocket manager.
WEBSOCKET_REDIS_URL: str = os.environ.get("WEBSOCKET_REDIS_URL", REDIS_URL)

#: Lock timeout (seconds) for Redis-based WebSocket coordination.
WEBSOCKET_REDIS_LOCK_TIMEOUT: int = _env_int("WEBSOCKET_REDIS_LOCK_TIMEOUT", 60)

#: Redis Sentinel hosts for WebSocket manager.
WEBSOCKET_SENTINEL_HOSTS: str = os.environ.get("WEBSOCKET_SENTINEL_HOSTS", "")

#: Redis Sentinel port for WebSocket manager.
WEBSOCKET_SENTINEL_PORT: str = os.environ.get("WEBSOCKET_SENTINEL_PORT", "26379")

# ---------------------------------------------------------------------------
# HTTP Client Timeouts
# ---------------------------------------------------------------------------

#: Default aiohttp client timeout in seconds (``None`` = no timeout).
AIOHTTP_CLIENT_TIMEOUT: int | None = _env_int("AIOHTTP_CLIENT_TIMEOUT", 600) or None
if os.environ.get("AIOHTTP_CLIENT_TIMEOUT", "") == "":
    AIOHTTP_CLIENT_TIMEOUT = None

#: Timeout for model-list fetches (shorter than general timeout).
_raw_model_list_timeout = os.environ.get(
    "AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST",
    os.environ.get("AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST", "10"),
)
if _raw_model_list_timeout == "":
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST: int | None = None
else:
    try:
        AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = int(_raw_model_list_timeout)
    except (ValueError, TypeError):
        AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = 10

# ---------------------------------------------------------------------------
# Offline Mode
# ---------------------------------------------------------------------------

#: Run without any outbound network access (sets ``HF_HUB_OFFLINE=1``).
OFFLINE_MODE: bool = _env_bool("OFFLINE_MODE", "false")

if OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"

# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

#: File path for the audit log.
AUDIT_LOGS_FILE_PATH: str = f"{DATA_DIR}/audit.log"

#: Maximum log file size before rotation (e.g. ``"10MB"``).
AUDIT_LOG_FILE_ROTATION_SIZE: str = os.getenv("AUDIT_LOG_FILE_ROTATION_SIZE", "10MB")

#: Audit detail level: ``"NONE"``, ``"METADATA"``, ``"REQUEST"``, or ``"REQUEST_RESPONSE"``.
AUDIT_LOG_LEVEL: str = os.getenv("AUDIT_LOG_LEVEL", "NONE").upper()

#: Maximum request/response body size captured in audit logs (bytes).
try:
    MAX_BODY_LOG_SIZE: int = int(os.environ.get("MAX_BODY_LOG_SIZE") or 2048)
except ValueError:
    MAX_BODY_LOG_SIZE = 2048

#: URL path prefixes excluded from audit logging (stored without leading ``/``).
AUDIT_EXCLUDED_PATHS: list[str] = [
    path.lstrip("/")
    for path in (
        p.strip()
        for p in os.getenv("AUDIT_EXCLUDED_PATHS", "/chats,/folders").split(",")
    )
]

# ---------------------------------------------------------------------------
# OpenTelemetry
# ---------------------------------------------------------------------------

#: Enable OpenTelemetry distributed tracing.
ENABLE_OTEL: bool = _env_bool("ENABLE_OTEL", "False")

#: OTLP exporter endpoint.
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)

#: Service name reported to the telemetry backend.
OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "bcgpt")

#: Resource attributes (``key1=val1,key2=val2``).
OTEL_RESOURCE_ATTRIBUTES: str = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")

#: Trace sampler strategy.
OTEL_TRACES_SAMPLER: str = os.environ.get(
    "OTEL_TRACES_SAMPLER", "parentbased_always_on"
).lower()

# ---------------------------------------------------------------------------
# Pip Options (for tool/function dependencies)
# ---------------------------------------------------------------------------

#: Extra flags passed to ``pip install`` when installing tool deps.
PIP_OPTIONS: list[str] = os.getenv("PIP_OPTIONS", "").split()

#: Extra index / package-index options for ``pip install``.
PIP_PACKAGE_INDEX_OPTIONS: list[str] = os.getenv(
    "PIP_PACKAGE_INDEX_OPTIONS", ""
).split()
