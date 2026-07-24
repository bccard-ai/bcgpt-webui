"""In-memory rate-limiting middleware for BCGPT WebUI.

Provides a sliding-window rate limiter that protects authentication,
file-upload, and chat-completion endpoints from brute-force and abuse.
Each client is identified by its IP address, with optional
``X-Forwarded-For`` support for reverse-proxy deployments.

Public exports (re-exported via ``bcgpt.utils.__init__``):
    InMemoryRateLimiter
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)


class InMemoryRateLimiter(BaseHTTPMiddleware):
    """Token-bucket rate limiter using only the Python standard library.

    Uses a sliding-window approach: for each request the middleware
    removes expired timestamps from the per-client bucket and checks
    whether the remaining count exceeds the configured maximum.

    Path rules are matched with ``startswith`` — more specific rules
    **must** be listed before broader ones.

    Environment variables:
        ``PROXY_TRUST_DEPTH`` — Number of trusted reverse-proxy hops.
        ``0`` (default) means ``X-Forwarded-For`` is ignored entirely.
    """

    PATH_RULES: dict[str, tuple[int, int]] = {
        # Specific rules MUST come before broad rules (startswith matching)
        "/api/v1/auths/signin": (10, 60),
        "/api/v1/auths/signup": (5, 60),
        "/api/v1/auths/ldap": (5, 60),
        "/api/v1/auths/signout": (10, 60),
        "/api/v1/auths": (10, 60),
        "/api/chat/completions": (30, 60),
        "/api/v1/files": (20, 60),
    }
    """Mapping of URL path prefixes to ``(max_requests, window_seconds)``."""

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._buckets: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = Lock()

        # Parse proxy trust depth safely — degrade to 0 on bad values.
        raw_depth = os.environ.get("PROXY_TRUST_DEPTH", "0")
        try:
            self._proxy_trust_depth = max(0, int(raw_depth))
        except (TypeError, ValueError):
            log.warning(
                "Invalid PROXY_TRUST_DEPTH=%r; defaulting to 0 (ignore X-Forwarded-For).",
                raw_depth,
            )
            self._proxy_trust_depth = 0

    # ------------------------------------------------------------------
    # Middleware entry point
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting before passing the request to the next handler.

        Only mutating methods (``POST``, ``PUT``, ``PATCH``) are subject
        to rate limiting; all others pass through unconditionally.
        """
        rule = self._match_rule(request.url.path, request.method)
        if rule is None:
            return await call_next(request)

        max_requests, window_seconds = rule
        client_id = self._client_id(request)

        with self._lock:
            now = time.time()
            bucket = self._buckets[client_id][request.url.path]

            # Evict expired timestamps
            self._buckets[client_id][request.url.path] = [
                ts for ts in bucket if now - ts < window_seconds
            ]
            bucket = self._buckets[client_id][request.url.path]

            if len(bucket) >= max_requests:
                log.warning(
                    "Rate limit exceeded for %s on %s",
                    client_id,
                    request.url.path,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later.",
                )

            bucket.append(now)

        return await call_next(request)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_rule(
        self, path: str, method: str
    ) -> tuple[int, int] | None:
        """Find the first matching rate-limit rule for *path* and *method*.

        Only mutating HTTP methods are rate-limited.

        Args:
            path: The request URL path.
            method: The HTTP method (upper-cased).

        Returns:
            A ``(max_requests, window_seconds)`` tuple, or ``None``.
        """
        if method not in ("POST", "PUT", "PATCH"):
            return None

        for rule_path, rule in self.PATH_RULES.items():
            if path.startswith(rule_path):
                return rule

        return None

    def _client_id(self, request: Request) -> str:
        """Determine the client identity for rate-limit bucketing.

        When ``PROXY_TRUST_DEPTH`` > 0 the middleware reads
        ``X-Forwarded-For`` and selects the entry *N* positions from the
        right (the closest trusted proxy appended the real client IP).
        Otherwise the direct socket address is used.

        Args:
            request: The incoming HTTP request.

        Returns:
            A string identifying the client (IP address or ``"unknown"``).
        """
        if self._proxy_trust_depth > 0:
            forwarded = request.headers.get("X-Forwarded-For", "")
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                idx = max(0, len(parts) - self._proxy_trust_depth)
                return parts[idx]

        if request.client:
            return request.client.host

        return "unknown"
