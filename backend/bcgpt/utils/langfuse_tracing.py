"""LangFuse RAG Tracing — integrates with existing OpenTelemetry pipeline.

Adds a LangfuseSpanProcessor to the shared TracerProvider so all RAG traces
(retrieval, reranking, generation, evaluation) flow to LangFuse dashboard.
"""

import logging
from typing import Optional

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_processor_added = False


def setup_langfuse_tracing(
    tracer_provider,
    public_key: str,
    secret_key: str,
    host: str = "https://cloud.langfuse.com",
    enabled: bool = True,
) -> bool:
    """Add LangfuseSpanProcessor to the existing TracerProvider.

    Args:
        tracer_provider: Existing OTel TracerProvider
        public_key: LangFuse public key
        secret_key: LangFuse secret key
        host: LangFuse host URL
        enabled: Master switch

    Returns:
        True if successfully set up, False otherwise
    """
    global _processor_added
    if _processor_added or not enabled:
        return False

    if not public_key or not secret_key:
        log.warning("LangFuse keys not configured — tracing disabled")
        return False

    try:
        from langfuse.exporter import LangfuseExporter
        from langfuse.sdk import LangfuseSpanProcessor

        exporter = LangfuseExporter(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

        processor = LangfuseSpanProcessor(exporter)
        tracer_provider.add_span_processor(processor)

        _processor_added = True
        log.info(f"LangFuse tracing enabled (host={host})")
        return True
    except ImportError:
        log.warning(
            "langfuse not installed — tracing disabled. "
            "Install with: pip install langfuse"
        )
        return False
    except Exception as e:
        log.error(f"Failed to set up LangFuse tracing: {e}")
        return False


def get_tracer(name: str = "bcgpt.rag"):
    """Get an OTel tracer for RAG operations."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return None


def trace_rag_operation(operation_name: str):
    """Decorator to trace RAG operations with OTel spans.

    Usage:
        @trace_rag_operation("retrieval")
        async def retrieve_documents(query: str):
            ...
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer is None:
                return await func(*args, **kwargs)

            with tracer.start_as_current_span(f"rag.{operation_name}") as span:
                span.set_attribute("rag.operation", operation_name)
                span.set_attribute("rag.function", func.__name__)
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("rag.status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("rag.status", "error")
                    span.set_attribute("rag.error", str(e))
                    raise

        return wrapper

    return decorator
