"""
Per-user rate limiter with exponential backoff (OWASP LLM10 - Unbounded Consumption).

Sliding window implementation using in-memory storage.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitEntry:
    timestamps: list = field(default_factory=list)
    violation_count: int = 0


class PerUserRateLimiter:
    """Sliding window rate limiter with exponential backoff."""

    def __init__(self):
        self._windows: dict[str, RateLimitEntry] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()

    def check_rate_limit(
        self,
        client_id: str,
        max_per_minute: int = 30,
        max_per_hour: int = 500,
        max_per_day: int = 5000,
    ) -> tuple[bool, Optional[str]]:
        """Returns (is_allowed, error_message)."""
        now = time.time()

        with self._lock:
            self._maybe_cleanup(now)

            if client_id not in self._windows:
                self._windows[client_id] = RateLimitEntry()

            entry = self._windows[client_id]
            entry.timestamps.append(now)

            # Exponential backoff multiplier (capped at 32x)
            backoff_multiplier = min(2**entry.violation_count, 32)

            # Check per-minute limit
            minute_ago = now - 60
            minute_count = sum(1 for t in entry.timestamps if t > minute_ago)
            minute_limit = max(max_per_minute // backoff_multiplier, 1)
            if minute_count > minute_limit:
                entry.violation_count += 1
                return (
                    False,
                    "Rate limit exceeded. Please try again in 60 seconds.",
                )

            # Check per-hour limit
            hour_ago = now - 3600
            hour_count = sum(1 for t in entry.timestamps if t > hour_ago)
            hour_limit = max(max_per_hour // backoff_multiplier, 1)
            if hour_count > hour_limit:
                entry.violation_count += 1
                return (
                    False,
                    "Hourly rate limit exceeded. Please try again shortly.",
                )

            # Check per-day limit
            day_ago = now - 86400
            day_count = sum(1 for t in entry.timestamps if t > day_ago)
            day_limit = max(max_per_day // backoff_multiplier, 1)
            if day_count > day_limit:
                entry.violation_count += 1
                return (
                    False,
                    "Daily rate limit exceeded.",
                )

            return True, None

    def _maybe_cleanup(self, now: float):
        """Remove old entries to prevent memory leak."""
        if now - self._last_cleanup < self._cleanup_interval:
            return

        day_ago = now - 86400
        expired = []
        for client_id, entry in self._windows.items():
            entry.timestamps = [t for t in entry.timestamps if t > day_ago]
            if not entry.timestamps:
                expired.append(client_id)

        for client_id in expired:
            del self._windows[client_id]

        self._last_cleanup = now

    def get_status(self, client_id: str) -> dict:
        """Get current rate limit status for a client."""
        now = time.time()
        with self._lock:
            if client_id not in self._windows:
                return {
                    "requests_last_minute": 0,
                    "requests_last_hour": 0,
                    "requests_last_day": 0,
                }

            entry = self._windows[client_id]
            return {
                "requests_last_minute": sum(
                    1 for t in entry.timestamps if t > now - 60
                ),
                "requests_last_hour": sum(
                    1 for t in entry.timestamps if t > now - 3600
                ),
                "requests_last_day": sum(
                    1 for t in entry.timestamps if t > now - 86400
                ),
                "violation_count": entry.violation_count,
            }


# Singleton instance
rate_limiter = PerUserRateLimiter()


class TokenBudgetLimiter:
    """Per-user token/cost budget (OWASP LLM10 denial-of-wallet).

    Sliding windows over consumed tokens: per-minute + per-day. Distinct from
    the request-COUNT limiter above — this caps total *tokens* spent, so a single
    runaway agent loop can't burn unbounded LLM spend. In-memory primary
    (per-worker, like the request limiter); uses Redis INCR+TTL when REDIS_URL is
    configured so caps hold across workers/pods.
    """

    def __init__(self):
        # client_id -> list[(timestamp, tokens)]
        self._windows: dict[str, list] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()
        self._redis = None
        self._redis_tried = False

    def _get_redis(self):
        if self._redis_tried:
            return self._redis
        self._redis_tried = True
        try:
            from bcgpt.env import REDIS_URL

            if REDIS_URL:
                from bcgpt.utils import get_redis_connection

                self._redis = get_redis_connection(REDIS_URL)
        except Exception:
            self._redis = None
        return self._redis

    def get_usage(self, client_id: str) -> tuple[int, int]:
        """Return (per_minute_tokens, per_day_tokens) already consumed."""
        r = self._get_redis()
        if r is not None:
            try:
                day = int(time.time() // 86400)
                minute = int(time.time() // 60)
                d = r.get(f"tokbudget:d:{client_id}:{day}")
                m = r.get(f"tokbudget:m:{client_id}:{minute}")
                return (int(m or 0), int(d or 0))
            except Exception:
                pass
        now = time.time()
        with self._lock:
            evts = self._windows.get(client_id, [])
            minute_sum = sum(t for ts, t in evts if ts > now - 60)
            day_sum = sum(t for ts, t in evts if ts > now - 86400)
            return (minute_sum, day_sum)

    def check_token_budget(
        self, client_id: str, daily_cap: int = 0, per_min_cap: int = 0
    ) -> tuple[bool, Optional[str]]:
        """Block once a cap is reached. 0 caps mean unlimited. Returns
        (is_allowed, error_message)."""
        if daily_cap <= 0 and per_min_cap <= 0:
            return True, None
        minute_used, day_used = self.get_usage(client_id)
        if daily_cap > 0 and day_used >= daily_cap:
            return (
                False,
                f"Daily token budget exceeded ({day_used}/{daily_cap} tokens). "
                "Try again tomorrow.",
            )
        if per_min_cap > 0 and minute_used >= per_min_cap:
            return (
                False,
                f"Per-minute token budget exceeded ({minute_used}/{per_min_cap} "
                "tokens). Try again shortly.",
            )
        return True, None

    def record_token_usage(self, client_id: str, tokens: int) -> None:
        """Record consumed tokens against the minute + day windows."""
        if not tokens or tokens <= 0:
            return
        tokens = int(tokens)
        r = self._get_redis()
        if r is not None:
            try:
                day = int(time.time() // 86400)
                minute = int(time.time() // 60)
                dk = f"tokbudget:d:{client_id}:{day}"
                mk = f"tokbudget:m:{client_id}:{minute}"
                pipe = r.pipeline()
                pipe.incrby(dk, tokens)
                pipe.expire(dk, 90000)  # ~25h
                pipe.incrby(mk, tokens)
                pipe.expire(mk, 120)
                pipe.execute()
                return
            except Exception:
                pass
        now = time.time()
        with self._lock:
            self._maybe_cleanup(now)
            self._windows.setdefault(client_id, []).append((now, tokens))

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup < self._cleanup_interval:
            return
        day_ago = now - 86400
        expired = []
        for cid, evts in self._windows.items():
            kept = [(ts, t) for ts, t in evts if ts > day_ago]
            self._windows[cid] = kept
            if not kept:
                expired.append(cid)
        for cid in expired:
            del self._windows[cid]
        self._last_cleanup = now


# Singleton instance
token_budget_limiter = TokenBudgetLimiter()
