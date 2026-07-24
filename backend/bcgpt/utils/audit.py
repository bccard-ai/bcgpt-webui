"""Audit logging middleware and utilities.

Provides ASGI middleware that intercepts mutating HTTP requests (POST, PUT,
PATCH, DELETE) and records structured audit entries.  Captured bodies are
optionally scrubbed for personally identifiable information (PII) before
being persisted.

Public exports (re-exported from ``bcgpt.utils.__init__``):
    AuditContext, AuditLevel, AuditLogEntry, AuditLogger,
    AuditLoggingMiddleware
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    MutableMapping,
    Optional,
    cast,
)

from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGIReceiveEvent,
    ASGISendCallable,
    ASGISendEvent,
    Scope as ASGIScope,
)
from loguru import logger
from starlette.requests import Request

from bcgpt.utils import get_current_user, get_http_authorization_cred
from bcgpt.models import UserModel

if TYPE_CHECKING:
    from loguru import Logger

# ---------------------------------------------------------------------------
# Optional PII scanner – graceful degradation when unavailable
# ---------------------------------------------------------------------------

try:
    from bcgpt.utils.security.pii import PIIScanner

    _pii_scanner: Optional[PIIScanner] = PIIScanner()
except Exception:
    _pii_scanner = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_config_value(val: Any) -> Any:
    """Resolve a value that may be a ``PersistentConfig`` wrapper."""
    from bcgpt.config import PersistentConfig

    if isinstance(val, PersistentConfig):
        return val.value
    return val


# ---------------------------------------------------------------------------
# Verb → action mapping
# ---------------------------------------------------------------------------

_VERB_ACTION_MAP: dict[str, str] = {
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
}

# URI segment → resource type mapping
_RESOURCE_MAP: dict[str, str] = {
    "users": "user",
    "chats": "chat",
    "messages": "message",
    "files": "file",
    "functions": "function",
    "configs": "config",
    "auths": "auth",
    "auth": "auth",
    "signin": "auth",
    "signup": "auth",
    "knowledge": "knowledge",
    "models": "model",
    "prompts": "prompt",
    "tools": "tool",
    "memories": "memory",
    "folders": "folder",
    "groups": "group",
    "evaluations": "evaluation",
    "channels": "channel",
    "security": "system",
    "retrieval": "system",
    "pipelines": "system",
    "audio": "system",
    "images": "system",
    "utils": "system",
}


# ---------------------------------------------------------------------------
# Data classes & enums
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditLogEntry:
    """Structured representation of a single auditable event."""

    id: str
    user: dict[str, Any]
    audit_level: str
    verb: str
    request_uri: str
    user_agent: Optional[str] = None
    source_ip: Optional[str] = None
    request_object: Any = None
    response_object: Any = None
    response_status_code: Optional[int] = None


class AuditLevel(str, Enum):
    """Granularity of information captured in audit logs."""

    NONE = "NONE"
    METADATA = "METADATA"
    REQUEST = "REQUEST"
    REQUEST_RESPONSE = "REQUEST_RESPONSE"


# ---------------------------------------------------------------------------
# AuditLogger – thin wrapper over Loguru
# ---------------------------------------------------------------------------


class AuditLogger:
    """Writes structured audit entries via Loguru with an ``auditable`` binding.

    Args:
        logger: A Loguru logger instance.
    """

    def __init__(self, logger: "Logger") -> None:
        self.logger = logger.bind(auditable=True)

    def write(
        self,
        audit_entry: AuditLogEntry,
        *,
        log_level: str = "INFO",
        extra: Optional[dict] = None,
    ) -> None:
        """Emit a structured audit log entry."""
        entry = asdict(audit_entry)
        if extra:
            entry["extra"] = extra
        self.logger.log(log_level, "", **entry)


def log_business_event(
    *,
    action: str,
    resource_type: str,
    user: Any = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[dict] = None,
    severity: str = "INFO",
    category: str = "rag",
) -> None:
    """Persist a first-class business audit event (P2.3).

    Unlike the ASGI :class:`AuditLoggingMiddleware` (which records raw HTTP
    request/response), this captures *semantic* events that are not bound to a
    single HTTP round-trip — e.g. ``file_added_to_kb``, ``kb_reprocessed``,
    ``embedding_config_changed``, ``file_deleted``. Best-effort: failures are
    logged at debug and never raised, so auditing cannot break the calling
    operation.
    """
    try:
        from bcgpt.models.audit_log import AuditLogForm, AuditLogsTable

        form = AuditLogForm(
            user_id=getattr(user, "id", None),
            user_email=getattr(user, "email", None),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            audit_details=details,
            severity=severity,
            category=category,
        )
        AuditLogsTable().insert_log(form)
    except Exception:
        logging.getLogger(__name__).debug(
            "log_business_event failed (action=%s, resource=%s/%s)",
            action,
            resource_type,
            resource_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# AuditContext – accumulates request/response bodies
# ---------------------------------------------------------------------------


class AuditContext:
    """Captures and aggregates HTTP request/response bodies for auditing.

    Attributes:
        request_body: Accumulated request payload bytes.
        response_body: Accumulated response payload bytes.
        max_body_size: Maximum number of bytes to retain.
        metadata: Additional audit metadata (status code, etc.).
    """

    def __init__(self, max_body_size: int = 2048) -> None:
        self.request_body = bytearray()
        self.response_body = bytearray()
        self.max_body_size = max_body_size
        self.metadata: Dict[str, Any] = {}

    # -- mutators -----------------------------------------------------------

    def add_request_chunk(self, chunk: bytes) -> None:
        """Append *chunk* to the request body, respecting ``max_body_size``."""
        remaining = self.max_body_size - len(self.request_body)
        if remaining > 0:
            self.request_body.extend(chunk[:remaining])

    def add_response_chunk(self, chunk: bytes) -> None:
        """Append *chunk* to the response body, respecting ``max_body_size``."""
        remaining = self.max_body_size - len(self.response_body)
        if remaining > 0:
            self.response_body.extend(chunk[:remaining])


# ---------------------------------------------------------------------------
# AuditLoggingMiddleware – ASGI middleware
# ---------------------------------------------------------------------------


class AuditLoggingMiddleware:
    """ASGI middleware that intercepts mutating HTTP requests for audit logging.

    Captures request/response bodies (depending on the configured audit
    level), headers, HTTP method, and authenticated user information, then
    emits a structured audit entry at the end of the request lifecycle.
    """

    AUDITED_METHODS = {"PUT", "PATCH", "DELETE", "POST"}

    def __init__(
        self,
        app: ASGI3Application,
        *,
        starlette_app: Any = None,
    ) -> None:
        self.app = app
        self.starlette_app = starlette_app
        self.audit_logger = AuditLogger(logger)

    # -- config resolution --------------------------------------------------

    def _resolve_config(self) -> Any:
        """Resolve the FastAPI/Starlette app config, if available."""
        if (
            self.starlette_app is not None
            and hasattr(self.starlette_app, "state")
            and hasattr(self.starlette_app.state, "config")
        ):
            return self.starlette_app.state.config
        return None

    # -- ASGI entry point ---------------------------------------------------

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        app_config = self._resolve_config()

        # Resolve audit level ------------------------------------------------
        audit_level_str = (
            str(_get_config_value(app_config.AUDIT_LOG_LEVEL)).upper()
            if app_config is not None
            else "NONE"
        )
        try:
            audit_level = AuditLevel(audit_level_str)
        except ValueError:
            audit_level = AuditLevel.NONE

        # Resolve excluded paths ---------------------------------------------
        excluded_paths_str = (
            str(_get_config_value(app_config.AUDIT_EXCLUDED_PATHS))
            if app_config is not None
            else ""
        )
        excluded_paths = [
            p.strip().lstrip("/") for p in excluded_paths_str.split(",") if p.strip()
        ]

        # Resolve max body size ----------------------------------------------
        max_body_size = (
            int(_get_config_value(app_config.MAX_BODY_LOG_SIZE))
            if app_config is not None
            else 2048
        )

        request = Request(scope=cast(MutableMapping, scope))

        if self._should_skip_auditing(request, audit_level, excluded_paths):
            return await self.app(scope, receive, send)

        # -- audit context ---------------------------------------------------
        async with self._audit_context(request, audit_level, max_body_size) as ctx:

            async def send_wrapper(message: ASGISendEvent) -> None:
                if audit_level == AuditLevel.REQUEST_RESPONSE:
                    await self._capture_response(message, ctx)
                await send(message)

            async def receive_wrapper() -> ASGIReceiveEvent:
                message = await receive()
                if audit_level in (AuditLevel.REQUEST, AuditLevel.REQUEST_RESPONSE):
                    await self._capture_request(message, ctx)
                return message

            await self.app(scope, receive_wrapper, send_wrapper)

    # -- context manager ----------------------------------------------------

    @asynccontextmanager
    async def _audit_context(
        self,
        request: Request,
        audit_level: AuditLevel,
        max_body_size: int,
    ) -> AsyncGenerator[AuditContext, None]:
        """Ensure an audit entry is recorded after request processing."""
        context = AuditContext(max_body_size=max_body_size)
        try:
            yield context
        finally:
            await self._log_audit_entry(request, context, audit_level)

    # -- capture helpers ----------------------------------------------------

    async def _capture_request(
        self, message: ASGIReceiveEvent, context: AuditContext
    ) -> None:
        """Capture request body chunks from the ASGI receive event."""
        if message["type"] == "http.request":
            context.add_request_chunk(message.get("body", b""))

    async def _capture_response(
        self, message: ASGISendEvent, context: AuditContext
    ) -> None:
        """Capture response status and body chunks from the ASGI send event."""
        if message["type"] == "http.response.start":
            context.metadata["response_status_code"] = message["status"]
        elif message["type"] == "http.response.body":
            context.add_response_chunk(message.get("body", b""))

    # -- authentication -----------------------------------------------------

    async def _get_authenticated_user(self, request: Request) -> UserModel:
        """Extract the authenticated user from the request's Authorization header."""
        auth_header = request.headers.get("Authorization")
        assert auth_header
        return get_current_user(
            request,
            None,
            get_http_authorization_cred(auth_header),
        )

    # -- skip logic ---------------------------------------------------------

    def _should_skip_auditing(
        self,
        request: Request,
        audit_level: AuditLevel,
        excluded_paths: list[str],
    ) -> bool:
        """Return ``True`` when the request should not be audited."""
        if (
            request.method not in self.AUDITED_METHODS
            or audit_level == AuditLevel.NONE
            or not request.headers.get("authorization")
        ):
            return True

        # Match /api/<resource> or /api/v1/<resource>
        if excluded_paths:
            pattern = re.compile(r"^/api(?:/v1)?/(" + "|".join(excluded_paths) + r")\b")
            if pattern.match(request.url.path):
                return True

        return False

    # -- audit entry persistence --------------------------------------------

    async def _log_audit_entry(
        self,
        request: Request,
        context: AuditContext,
        audit_level: AuditLevel,
    ) -> None:
        """Build and persist an ``AuditLogEntry`` from the captured context."""
        try:
            user = await self._get_authenticated_user(request)

            request_body_raw = context.request_body.decode("utf-8", errors="replace")
            response_body_raw = context.response_body.decode("utf-8", errors="replace")

            request_body_safe = self._mask_pii_in_body(request_body_raw)
            response_body_safe = self._mask_pii_in_body(response_body_raw)

            entry = AuditLogEntry(
                id=str(uuid.uuid4()),
                user=user.model_dump(include={"id", "name", "email", "role"}),
                audit_level=audit_level.value,
                verb=request.method,
                request_uri=str(request.url),
                response_status_code=context.metadata.get("response_status_code"),
                source_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                request_object=request_body_safe,
                response_object=response_body_safe,
            )

            self.audit_logger.write(entry)
            self._persist_to_database(entry)

        except Exception as exc:
            logger.error(f"Failed to log audit entry: {exc}")

    def _persist_to_database(self, entry: AuditLogEntry) -> None:
        """Attempt to persist the audit entry to the database."""
        try:
            from bcgpt.models.audit_log import AuditLogs, AuditLogForm

            # ``audit_details`` is a JSON/dict column.  The captured
            # request/response bodies are strings, so they MUST be wrapped
            # in a dict — a raw string would cause Pydantic validation to
            # reject the whole ``AuditLogForm``.
            details: dict[str, Any] = {}
            if entry.request_object:
                details["request_body"] = entry.request_object
            if entry.response_object:
                details["response_body"] = entry.response_object

            AuditLogs.insert_log(
                AuditLogForm(
                    user_id=entry.user.get("id") if entry.user else None,
                    user_email=entry.user.get("email") if entry.user else None,
                    action=self._map_verb_to_action(entry.verb),
                    resource_type=self._infer_resource_type(entry.request_uri),
                    request_method=entry.verb,
                    request_path=entry.request_uri,
                    response_status=entry.response_status_code,
                    ip_address=entry.source_ip,
                    user_agent=entry.user_agent,
                    audit_details=details or None,
                    severity=(
                        "WARNING"
                        if entry.response_status_code is not None
                        and entry.response_status_code >= 400
                        else "INFO"
                    ),
                    category=self._infer_category(entry.verb, entry.request_uri),
                ),
            )
        except Exception as db_err:
            logger.warning(f"Failed to persist audit log to DB: {db_err}")

    # -- classification helpers ---------------------------------------------

    @staticmethod
    def _map_verb_to_action(verb: str) -> str:
        """Map an HTTP verb to a high-level action label."""
        return _VERB_ACTION_MAP.get(verb, "ACCESS")

    @staticmethod
    def _infer_resource_type(uri: str) -> str:
        """Infer the resource type from the URI path segments."""
        path = uri.split("?")[0]
        segments = [s for s in path.split("/") if s]
        for segment in segments:
            if segment in _RESOURCE_MAP:
                return _RESOURCE_MAP[segment]
        return "system"

    @staticmethod
    def _infer_category(verb: str, uri: str) -> str:
        """Infer an audit category from the HTTP verb and URI."""
        path = uri.split("?")[0].lower()
        if "auth" in path or "signin" in path or "signup" in path:
            return "authentication"
        if "export" in path:
            return "export"
        if "config" in path or "setting" in path:
            return "configuration"
        if verb in ("DELETE", "POST", "PUT", "PATCH"):
            return "data_modification"
        return "data_access"

    # -- PII masking --------------------------------------------------------

    @staticmethod
    def _mask_pii_in_body(body: str) -> str:
        """Mask PII in *body* using the optional ``PIIScanner``.

        For JSON payloads the scanner targets ``messages[*].content`` fields
        specifically; for plain-text payloads the entire string is masked.
        Returns *body* unchanged if the scanner is unavailable or an error
        occurs.
        """
        if not body or not _pii_scanner:
            return body
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                messages = parsed.get("messages")
                if isinstance(messages, list):
                    for msg in messages:
                        if isinstance(msg, dict) and isinstance(
                            msg.get("content"), str
                        ):
                            masked = _pii_scanner.mask(msg["content"])
                            if masked != msg["content"]:
                                msg["content"] = masked
                return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return _pii_scanner.mask(body)
        except Exception:
            return body
