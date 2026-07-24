"""Redis-backed distributed data structures for Socket.IO.

Provides :class:`RedisLock` for distributed mutual exclusion and
:class:`RedisDict` for a dict-like interface over a Redis hash.

Both classes support direct Redis connections as well as Redis Sentinel
for high-availability deployments.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple

from bcgpt.utils import get_redis_connection


class RedisLock:
    """Distributed lock backed by a Redis key with TTL.

    Uses ``SET NX EX`` semantics for atomic acquisition and verifies
    ownership before release.

    Args:
        redis_url: Redis connection URL.
        lock_name: Key name used as the lock identifier.
        timeout_secs: Lock time-to-live in seconds (auto-release).
        redis_sentinels: Optional list of ``(host, port)`` Sentinel addresses.
    """

    def __init__(
        self,
        redis_url: str,
        lock_name: str,
        timeout_secs: int,
        redis_sentinels: Optional[List[Tuple[str, int]]] = None,
    ) -> None:
        if redis_sentinels is None:
            redis_sentinels = []
        self.lock_name = lock_name
        self.lock_id = str(uuid.uuid4())
        self.timeout_secs = timeout_secs
        self.lock_obtained = False
        self.redis = get_redis_connection(
            redis_url, redis_sentinels, decode_responses=True
        )

    def aquire_lock(self) -> bool:
        """Attempt to acquire the lock (non-blocking).

        Returns:
            ``True`` if the lock was obtained, ``False`` otherwise.
        """
        self.lock_obtained = bool(
            self.redis.set(self.lock_name, self.lock_id, nx=True, ex=self.timeout_secs)
        )
        return self.lock_obtained

    def renew_lock(self) -> Any:
        """Renew the lock TTL (only if we still hold it).

        Returns:
            The result of the Redis ``SET`` command.
        """
        return self.redis.set(
            self.lock_name, self.lock_id, xx=True, ex=self.timeout_secs
        )

    def release_lock(self) -> None:
        """Release the lock only if the current holder still owns it."""
        lock_value = self.redis.get(self.lock_name)
        if lock_value and lock_value == self.lock_id:
            self.redis.delete(self.lock_name)


class RedisDict:
    """Dict-like interface over a Redis hash.

    Values are JSON-serialised before storage and deserialised on access.

    Args:
        name: Redis hash key.
        redis_url: Redis connection URL.
        redis_sentinels: Optional list of ``(host, port)`` Sentinel addresses.
    """

    def __init__(
        self,
        name: str,
        redis_url: str,
        redis_sentinels: Optional[List[Tuple[str, int]]] = None,
    ) -> None:
        if redis_sentinels is None:
            redis_sentinels = []
        self.name = name
        self.redis = get_redis_connection(
            redis_url, redis_sentinels, decode_responses=True
        )

    def __setitem__(self, key: str, value: Any) -> None:
        self.redis.hset(self.name, key, json.dumps(value))

    def __getitem__(self, key: str) -> Any:
        value = self.redis.hget(self.name, key)
        if value is None:
            raise KeyError(key)
        return json.loads(value)

    def __delitem__(self, key: str) -> None:
        result = self.redis.hdel(self.name, key)
        if result == 0:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return bool(self.redis.hexists(self.name, key))

    def __len__(self) -> int:
        return self.redis.hlen(self.name)

    def keys(self) -> List[str]:
        """Return all hash field names."""
        return self.redis.hkeys(self.name)

    def values(self) -> List[Any]:
        """Return all hash field values (deserialised)."""
        return [json.loads(v) for v in self.redis.hvals(self.name)]

    def items(self) -> List[Tuple[str, Any]]:
        """Return all ``(key, value)`` pairs (values deserialised)."""
        return [
            (k, json.loads(v)) for k, v in self.redis.hgetall(self.name).items()
        ]

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if missing."""
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self) -> None:
        """Delete the entire hash."""
        self.redis.delete(self.name)

    def update(self, other: Any = None, **kwargs: Any) -> None:
        """Merge *other* mapping and keyword arguments into this dict."""
        if other is not None:
            for k, v in other.items() if hasattr(other, "items") else other:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def setdefault(self, key: str, default: Any = None) -> Any:
        """Return *key*'s value, setting it to *default* first if absent."""
        if key not in self:
            self[key] = default
        return self[key]
