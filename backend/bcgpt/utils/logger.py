"""Logging configuration for BCGPT WebUI.

Configures `Loguru <https://loguru.readthedocs.io/>`_ as the primary
logging backend, intercepting Python's standard :mod:`logging` module
and routing all log output through Loguru's handlers.

Two log sinks are configured:

* **stdout** — colour-formatted console output for all non-audit messages.
* **file** (optional) — structured JSON audit records written to a
  rotating file when :envvar:`AUDIT_LOG_LEVEL` is not ``NONE``.

Public exports (re-exported via ``bcgpt.utils.__init__``):
    InterceptHandler, stdout_format, file_format, start_logger
"""

from __future__ import annotations

import json
import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

from bcgpt.env import (
    AUDIT_LOG_FILE_ROTATION_SIZE,
    AUDIT_LOG_LEVEL,
    AUDIT_LOGS_FILE_PATH,
    GLOBAL_LOG_LEVEL,
)

if TYPE_CHECKING:
    from loguru import Record

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def stdout_format(record: "Record") -> str:
    """Format a log record for coloured console output.

    The output includes timestamp, level, source location (module,
    function, line), the message, and any extra context serialised
    as JSON.

    Args:
        record: A Loguru log record.

    Returns:
        A Loguru format string (with colour tags).
    """
    record["extra"]["extra_json"] = json.dumps(record["extra"])
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> - {extra[extra_json]}"
        "\n{exception}"
    )


def file_format(record: "Record") -> str:
    """Format an audit log record as a structured JSON line.

    Extracts standard audit fields from the record's ``extra`` dict and
    serialises them as a single JSON object followed by a newline.

    Args:
        record: A Loguru log record carrying audit metadata in ``extra``.

    Returns:
        A Loguru format string that resolves to the JSON line.
    """
    audit_data = {
        "id": record["extra"].get("id", ""),
        "timestamp": int(record["time"].timestamp()),
        "user": record["extra"].get("user", {}),
        "audit_level": record["extra"].get("audit_level", ""),
        "verb": record["extra"].get("verb", ""),
        "request_uri": record["extra"].get("request_uri", ""),
        "response_status_code": record["extra"].get("response_status_code", 0),
        "source_ip": record["extra"].get("source_ip", ""),
        "user_agent": record["extra"].get("user_agent", ""),
        "request_object": record["extra"].get("request_object", b""),
        "response_object": record["extra"].get("response_object", b""),
        "extra": record["extra"].get("extra", {}),
    }

    record["extra"]["file_extra"] = json.dumps(audit_data, default=str)
    return "{extra[file_extra]}\n"


# ---------------------------------------------------------------------------
# Standard-logging bridge
# ---------------------------------------------------------------------------


class InterceptHandler(logging.Handler):
    """Bridge that redirects stdlib :mod:`logging` records into Loguru.

    This allows third-party libraries that use the standard logging module
    to have their output captured and formatted by Loguru transparently.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Handle a standard ``LogRecord`` by forwarding it to Loguru.

        The handler walks the call stack to find the correct source
        location so that Loguru's output shows the *original* caller
        rather than this bridge class.

        Args:
            record: The standard library log record to forward.
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def start_logger() -> None:
    """Initialise and configure the Loguru-based logging pipeline.

    This function:

    1. Removes all existing Loguru handlers.
    2. Adds a **stdout** handler for general log messages (excluding audit).
    3. Optionally adds a **file** handler for audit logs when
       :envvar:`AUDIT_LOG_LEVEL` is not ``NONE``.
    4. Redirects Python's standard :mod:`logging` through the
       :class:`InterceptHandler` bridge.
    5. Configures Uvicorn loggers to use the same bridge.
    """
    logger.remove()

    # Console sink — all non-audit messages
    logger.add(
        sys.stdout,
        level=GLOBAL_LOG_LEVEL,
        format=stdout_format,
        filter=lambda record: "auditable" not in record["extra"],
    )

    # Audit file sink — only audit-flagged messages
    if AUDIT_LOG_LEVEL != "NONE":
        try:
            logger.add(
                AUDIT_LOGS_FILE_PATH,
                level="INFO",
                rotation=AUDIT_LOG_FILE_ROTATION_SIZE,
                compression="zip",
                format=file_format,
                filter=lambda record: record["extra"].get("auditable") is True,
            )
        except Exception as exc:
            logger.error("Failed to initialise audit log file handler: {}", exc)

    # Bridge stdlib logging → Loguru
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=GLOBAL_LOG_LEVEL,
        force=True,
    )

    # Reconfigure Uvicorn loggers to route through the bridge
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.setLevel(GLOBAL_LOG_LEVEL)
        uv_logger.handlers = []

    for name in ("uvicorn.access",):
        uv_logger = logging.getLogger(name)
        uv_logger.setLevel(GLOBAL_LOG_LEVEL)
        uv_logger.handlers = [InterceptHandler()]

    logger.info("GLOBAL_LOG_LEVEL: {}", GLOBAL_LOG_LEVEL)
