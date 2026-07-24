"""OpenTelemetry instrumentation hooks and auto-instrumentor.

Registers request/response hooks for ``requests``, ``httpx``, ``aiohttp``,
``redis``, ``sqlalchemy``, and ``fastapi`` so that spans carry rich
metadata (URLs, status codes, DB statements, etc.).

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Collection, Dict, Union

from aiohttp import (
    TraceRequestEndParams,
    TraceRequestExceptionParams,
    TraceRequestStartParams,
)
from fastapi import FastAPI, status
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
    RequestInfo,
    ResponseInfo,
)
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.trace import Span, StatusCode
from redis import Redis
from requests import PreparedRequest, Response
from sqlalchemy import Engine

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.utils import SPAN_REDIS_TYPE, SpanAttributes

logger = logging.getLogger(__name__)
logger.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# requests hooks
# ---------------------------------------------------------------------------


def requests_hook(span: Span, request: PreparedRequest) -> None:
    """Enrich an HTTP span with request method and URL.

    Args:
        span: The current OpenTelemetry span.
        request: Outgoing :class:`PreparedRequest`.
    """
    span.update_name(f"{request.method} {request.url}")
    span.set_attributes(
        {
            SpanAttributes.HTTP_URL: request.url,
            SpanAttributes.HTTP_METHOD: request.method,
        }
    )


def response_hook(span: Span, request: PreparedRequest, response: Response) -> None:
    """Enrich an HTTP span with the response status code.

    Args:
        span: The current OpenTelemetry span.
        request: Original :class:`PreparedRequest`.
        response: Received :class:`Response`.
    """
    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
    span.set_status(
        StatusCode.ERROR if response.status_code >= 400 else StatusCode.OK
    )


# ---------------------------------------------------------------------------
# Redis hooks
# ---------------------------------------------------------------------------


def redis_request_hook(
    span: Span,
    instance: Redis,
    args: tuple,
    kwargs: dict,
) -> None:
    """Enrich a Redis span with connection and command metadata.

    Args:
        span: The current OpenTelemetry span.
        instance: The :class:`Redis` client issuing the command.
        args: Positional arguments to the Redis command.
        kwargs: Keyword arguments (unused).
    """
    try:
        conn: Dict[str, Any] = instance.connection_pool.connection_kwargs
        host = conn.get("host")
        port = conn.get("port")
        db = conn.get("db")
        span.set_attributes(
            {
                SpanAttributes.DB_INSTANCE: f"{host}/{db}",
                SpanAttributes.DB_NAME: f"{host}/{db}",
                SpanAttributes.DB_TYPE: SPAN_REDIS_TYPE,
                SpanAttributes.DB_PORT: port,
                SpanAttributes.DB_IP: host,
                SpanAttributes.DB_STATEMENT: " ".join(str(i) for i in args),
                SpanAttributes.DB_OPERATION: str(args[0]),
            }
        )
    except Exception:  # pylint: disable=W0718
        logger.error(traceback.format_exc())


# ---------------------------------------------------------------------------
# httpx hooks
# ---------------------------------------------------------------------------


def httpx_request_hook(span: Span, request: RequestInfo) -> None:
    """Enrich a synchronous httpx span with method and URL.

    Args:
        span: The current OpenTelemetry span.
        request: Outgoing httpx request info.
    """
    span.update_name(f"{request.method.decode()} {str(request.url)}")
    span.set_attributes(
        {
            SpanAttributes.HTTP_URL: str(request.url),
            SpanAttributes.HTTP_METHOD: request.method.decode(),
        }
    )


def httpx_response_hook(
    span: Span,
    request: RequestInfo,
    response: ResponseInfo,
) -> None:
    """Enrich a synchronous httpx span with the response status code.

    Args:
        span: The current OpenTelemetry span.
        request: Original request info.
        response: Received response info.
    """
    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
    span.set_status(
        StatusCode.ERROR
        if response.status_code >= status.HTTP_400_BAD_REQUEST
        else StatusCode.OK
    )


async def httpx_async_request_hook(span: Span, request: RequestInfo) -> None:
    """Enrich an async httpx span with method and URL.

    Delegates to :func:`httpx_request_hook`.
    """
    httpx_request_hook(span, request)


async def httpx_async_response_hook(
    span: Span,
    request: RequestInfo,
    response: ResponseInfo,
) -> None:
    """Enrich an async httpx span with the response status code.

    Delegates to :func:`httpx_response_hook`.
    """
    httpx_response_hook(span, request, response)


# ---------------------------------------------------------------------------
# aiohttp hooks
# ---------------------------------------------------------------------------


def aiohttp_request_hook(span: Span, request: TraceRequestStartParams) -> None:
    """Enrich an aiohttp span with method and URL.

    Args:
        span: The current OpenTelemetry span.
        request: aiohttp trace request-start parameters.
    """
    span.update_name(f"{request.method} {str(request.url)}")
    span.set_attributes(
        {
            SpanAttributes.HTTP_URL: str(request.url),
            SpanAttributes.HTTP_METHOD: request.method,
        }
    )


def aiohttp_response_hook(
    span: Span,
    response: Union[TraceRequestExceptionParams, TraceRequestEndParams],
) -> None:
    """Enrich an aiohttp span with the response status or error.

    Args:
        span: The current OpenTelemetry span.
        response: Either end params (status available) or exception params.
    """
    if isinstance(response, TraceRequestEndParams):
        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.response.status)
        span.set_status(
            StatusCode.ERROR
            if response.response.status >= status.HTTP_400_BAD_REQUEST
            else StatusCode.OK
        )
    elif isinstance(response, TraceRequestExceptionParams):
        span.set_status(StatusCode.ERROR)
        span.set_attribute(SpanAttributes.ERROR_MESSAGE, str(response.exception))


# ---------------------------------------------------------------------------
# Composite instrumentor
# ---------------------------------------------------------------------------


class Instrumentor(BaseInstrumentor):
    """Auto-instrument a FastAPI application with all supported libraries.

    Registers instrumentation for FastAPI, SQLAlchemy, Redis, requests,
    httpx (sync + async), aiohttp, and Python logging.

    Args:
        app: The :class:`FastAPI` application to instrument.
        db_engine: The SQLAlchemy :class:`Engine` to instrument.
    """

    def __init__(self, app: FastAPI, db_engine: Engine) -> None:
        self.app = app
        self.db_engine = db_engine

    def instrumentation_dependencies(self) -> Collection[str]:
        """Return an empty collection (no external version constraints)."""
        return []

    def _instrument(self, **kwargs: Any) -> None:
        """Activate all instrumentation hooks."""
        FastAPIInstrumentor().instrument(app=self.app)
        SQLAlchemyInstrumentor().instrument(engine=self.db_engine)
        RedisInstrumentor().instrument(request_hook=redis_request_hook)
        RequestsInstrumentor().instrument(
            request_hook=requests_hook, response_hook=response_hook
        )
        LoggingInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument(
            request_hook=httpx_request_hook,
            response_hook=httpx_response_hook,
            async_request_hook=httpx_async_request_hook,
            async_response_hook=httpx_async_response_hook,
        )
        AioHttpClientInstrumentor().instrument(
            request_hook=aiohttp_request_hook,
            response_hook=aiohttp_response_hook,
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        """Tear down all registered instrumentors."""
        if getattr(self, "instrumentors", None) is None:
            return
        for instrumentor in self.instrumentors:
            instrumentor.uninstrument()
