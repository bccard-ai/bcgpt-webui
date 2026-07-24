"""LLM API resilience — retry with exponential backoff using tenacity."""

import asyncio
import logging
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

log = logging.getLogger(__name__)

# Exceptions that indicate transient failures — safe to retry.
# These cover: network timeout, connection refused, rate limit (429), server errors (5xx).
TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
    OSError,
)

MAX_ATTEMPTS = 3
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 10

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def _is_retryable_status(status_code: int) -> bool:
    """Return True if *status_code* indicates a transient HTTP error."""
    return status_code in _RETRYABLE_STATUSES


class RetryableLLMError(Exception):
    """Wrapper for LLM errors that should be retried."""


def make_retryable_llm_call(func):
    """Decorator that adds retry logic to async LLM call functions.

    - Retries on transient network errors (timeout, connection failures, OSError).
    - Retries on HTTP 429 / 5xx responses (via :class:`RetryableLLMError`).
    - Does **not** retry on 400 (bad request), 401 (auth), 403 (forbidden), 404.

    The retry uses exponential back-off (1 s – 10 s) with up to 3 attempts.
    """

    @retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS + (RetryableLLMError,)),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            if status is not None:
                try:
                    code = int(status)
                except (TypeError, ValueError):
                    raise
                if _is_retryable_status(code):
                    raise RetryableLLMError(str(e)) from e
            raise

    return wrapper
