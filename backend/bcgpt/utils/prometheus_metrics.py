"""Prometheus Metrics for RAG Pipeline Monitoring.

Custom metrics for:
- RAG request count, latency, success/failure
- Retrieval score distribution
- Cache hit/miss ratio
- LLM token usage (input/output)
- Active concurrent requests

All metric recording functions degrade gracefully when prometheus_client
is not installed — they become no-ops so request processing is never blocked.
"""

import logging
import time
from functools import wraps
from typing import Optional

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_metrics_initialized = False

RAG_REQUEST_COUNT = None
RAG_REQUEST_LATENCY = None
RAG_RETRIEVAL_SCORE = None
RAG_CACHE_HITS = None
RAG_CACHE_MISSES = None
LLM_TOKEN_USAGE = None
RAG_ACTIVE_REQUESTS = None


def init_metrics():
    """Initialize all Prometheus metrics. Call once on startup."""
    global _metrics_initialized
    global RAG_REQUEST_COUNT, RAG_REQUEST_LATENCY, RAG_RETRIEVAL_SCORE
    global RAG_CACHE_HITS, RAG_CACHE_MISSES, LLM_TOKEN_USAGE, RAG_ACTIVE_REQUESTS

    if _metrics_initialized:
        return

    try:
        from prometheus_client import Counter, Histogram, Gauge

        RAG_REQUEST_COUNT = Counter(
            "bcgpt_rag_requests_total",
            "Total RAG requests",
            ["status", "model"],
        )
        RAG_REQUEST_LATENCY = Histogram(
            "bcgpt_rag_request_duration_seconds",
            "RAG request latency in seconds",
            ["operation"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )
        RAG_RETRIEVAL_SCORE = Histogram(
            "bcgpt_rag_retrieval_score",
            "Retrieval relevance scores",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        RAG_CACHE_HITS = Counter(
            "bcgpt_rag_cache_hits_total",
            "Semantic cache hits",
        )
        RAG_CACHE_MISSES = Counter(
            "bcgpt_rag_cache_misses_total",
            "Semantic cache misses",
        )
        LLM_TOKEN_USAGE = Counter(
            "bcgpt_llm_tokens_total",
            "LLM token usage",
            ["type", "model"],
        )
        RAG_ACTIVE_REQUESTS = Gauge(
            "bcgpt_rag_active_requests",
            "Currently processing RAG requests",
        )

        _metrics_initialized = True
        log.info("Prometheus RAG metrics initialized")
    except ImportError:
        log.warning("prometheus_client not installed — metrics disabled")
    except Exception as e:
        log.error(f"Failed to initialize Prometheus metrics: {e}")


def setup_instrumentator(app):
    """Set up prometheus-fastapi-instrumentator on the FastAPI app.

    Adds standard HTTP metrics (request count, latency, in-progress, response size)
    plus the /metrics endpoint. Falls back to prometheus_client start_http_server
    when the instrumentator is not available.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument_app(
            app,
            should_group_status_codes=True,
            should_ignore_untemplated=True,
        ).expose(app, endpoint="/metrics", include_in_schema=False)
        log.info("Prometheus FastAPI instrumentator enabled — /metrics endpoint active")
    except ImportError:
        log.warning(
            "prometheus_fastapi_instrumentator not installed — falling back to standalone metrics server"
        )
        try:
            from prometheus_client import start_http_server

            start_http_server(9090)
            log.info("Prometheus metrics server started on :9090")
        except Exception:
            pass


def record_rag_request(status: str, model: str = "unknown"):
    """Record a RAG request outcome."""
    try:
        if RAG_REQUEST_COUNT:
            RAG_REQUEST_COUNT.labels(status=status, model=model).inc()
    except Exception:
        pass


def record_rag_latency(operation: str, duration: float):
    """Record RAG request latency."""
    try:
        if RAG_REQUEST_LATENCY:
            RAG_REQUEST_LATENCY.labels(operation=operation).observe(duration)
    except Exception:
        pass


def record_retrieval_score(score: float):
    """Record a retrieval relevance score."""
    try:
        if RAG_RETRIEVAL_SCORE:
            RAG_RETRIEVAL_SCORE.observe(score)
    except Exception:
        pass


def record_cache_hit():
    """Record a semantic cache hit."""
    try:
        if RAG_CACHE_HITS:
            RAG_CACHE_HITS.inc()
    except Exception:
        pass


def record_cache_miss():
    """Record a semantic cache miss."""
    try:
        if RAG_CACHE_MISSES:
            RAG_CACHE_MISSES.inc()
    except Exception:
        pass


def record_token_usage(token_type: str, count: int, model: str = "unknown"):
    """Record LLM token usage (input or output)."""
    try:
        if LLM_TOKEN_USAGE:
            LLM_TOKEN_USAGE.labels(type=token_type, model=model).inc(count)
    except Exception:
        pass


def track_rag_request(operation: str = "full"):
    """Decorator to track RAG request latency and active count."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if RAG_ACTIVE_REQUESTS:
                try:
                    RAG_ACTIVE_REQUESTS.inc()
                except Exception:
                    pass
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                record_rag_latency(operation, time.monotonic() - start)
                record_rag_request("success")
                return result
            except Exception:
                record_rag_latency(operation, time.monotonic() - start)
                record_rag_request("error")
                raise
            finally:
                if RAG_ACTIVE_REQUESTS:
                    try:
                        RAG_ACTIVE_REQUESTS.dec()
                    except Exception:
                        pass

        return wrapper

    return decorator
