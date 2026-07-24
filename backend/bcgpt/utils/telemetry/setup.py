"""OpenTelemetry bootstrap for BCGPT WebUI.

Configures a :class:`TracerProvider` with an OTLP gRPC exporter, wraps it
in a :class:`LazyBatchSpanProcessor`, and instruments the application.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import Engine

from bcgpt.env import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME
from bcgpt.utils import Instrumentor, LazyBatchSpanProcessor


def setup(app: FastAPI, db_engine: Engine) -> None:
    """Initialise OpenTelemetry tracing and auto-instrumentation.

    Creates a :class:`TracerProvider` named via :data:`OTEL_SERVICE_NAME`,
    attaches a :class:`LazyBatchSpanProcessor` pointed at
    :data:`OTEL_EXPORTER_OTLP_ENDPOINT`, and runs all registered
    instrumentors.

    Args:
        app: The FastAPI application to instrument.
        db_engine: SQLAlchemy engine for DB-level tracing.
    """
    # Configure tracer provider
    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create(attributes={SERVICE_NAME: OTEL_SERVICE_NAME})
        )
    )

    # Attach OTLP exporter with lazy batching
    exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
    trace.get_tracer_provider().add_span_processor(LazyBatchSpanProcessor(exporter))

    # Activate all instrumentors
    Instrumentor(app=app, db_engine=db_engine).instrument()
