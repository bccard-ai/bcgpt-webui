"""Telemetry span attribute constants.

Defines standard attribute names used across OpenTelemetry spans for
database, Redis, HTTP, and error instrumentation.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

from opentelemetry.semconv.trace import SpanAttributes as _SpanAttributes


# ---------------------------------------------------------------------------
# Tag constants
# ---------------------------------------------------------------------------

SPAN_DB_TYPE: str = "mysql"
SPAN_REDIS_TYPE: str = "redis"
SPAN_DURATION: str = "duration"
SPAN_SQL_STR: str = "sql"
SPAN_SQL_EXPLAIN: str = "explain"
SPAN_ERROR_TYPE: str = "error"


# ---------------------------------------------------------------------------
# Extended span attributes
# ---------------------------------------------------------------------------


class SpanAttributes(_SpanAttributes):
    """Extended span attributes for database and error instrumentation.

    Inherits all standard OpenTelemetry semantic-convention attributes and
    adds project-specific keys for DB instance, error classification, and
    result metadata.
    """

    DB_INSTANCE = "db.instance"
    DB_TYPE = "db.type"
    DB_IP = "db.ip"
    DB_PORT = "db.port"
    ERROR_KIND = "error.kind"
    ERROR_OBJECT = "error.object"
    ERROR_MESSAGE = "error.message"
    RESULT_CODE = "result.code"
    RESULT_MESSAGE = "result.message"
    RESULT_ERRORS = "result.errors"
