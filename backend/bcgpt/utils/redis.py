"""Redis connection helpers with Sentinel support.

Provides synchronous and asynchronous Redis connection factories, an
environment-variable parser for Sentinel configuration, and a custom
Socket.IO manager that routes traffic through Redis Sentinel.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import redis
import socketio
from redis import asyncio as aioredis


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def parse_redis_sentinel_url(redis_url: str) -> Dict[str, Any]:
    """Extract Sentinel-compatible connection parameters from a Redis URL.

    Args:
        redis_url: URL string (``redis://user:pass@host:port/db``).

    Returns:
        Dict with ``username``, ``password``, ``service``, ``port``, and
        ``db`` keys.

    Raises:
        ValueError: If the URL scheme is not ``redis://``.
    """
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        raise ValueError("Invalid Redis URL scheme. Must be 'redis'.")

    return {
        "username": parsed.username or None,
        "password": parsed.password or None,
        "service": parsed.hostname or "mymaster",
        "port": parsed.port or 6379,
        "db": int(parsed.path.lstrip("/") or 0),
    }


# ---------------------------------------------------------------------------
# Connection factories
# ---------------------------------------------------------------------------


def get_redis_connection(
    redis_url: str,
    redis_sentinels: Optional[List[Any]] = None,
    decode_responses: bool = True,
) -> redis.Redis:
    """Create a synchronous Redis client, optionally via Sentinel.

    When *redis_sentinels* is non-empty the connection is routed through
    a Redis Sentinel cluster; otherwise a standard direct connection is
    established.

    Args:
        redis_url: Redis connection URL.
        redis_sentinels: Optional list of ``(host, port)`` Sentinel addresses.
        decode_responses: Whether to decode byte responses to strings.

    Returns:
        Connected :class:`redis.Redis` instance.
    """
    if redis_sentinels:
        config = parse_redis_sentinel_url(redis_url)
        sentinel = redis.sentinel.Sentinel(
            redis_sentinels,
            port=config["port"],
            db=config["db"],
            username=config["username"],
            password=config["password"],
            decode_responses=decode_responses,
        )
        return sentinel.master_for(config["service"])

    return redis.Redis.from_url(redis_url, decode_responses=decode_responses)


def get_sentinels_from_env(
    sentinel_hosts_env: Optional[str],
    sentinel_port_env: Optional[str],
) -> List[Tuple[str, int]]:
    """Parse Sentinel host/port environment variables into address tuples.

    Args:
        sentinel_hosts_env: Comma-separated Sentinel hostnames (or ``None``).
        sentinel_port_env: Sentinel port as a string (or ``None``).

    Returns:
        List of ``(host, port)`` tuples, or an empty list when
        *sentinel_hosts_env* is falsy.
    """
    if sentinel_hosts_env:
        hosts = sentinel_hosts_env.split(",")
        port = int(sentinel_port_env)
        return [(host, port) for host in hosts]
    return []


# ---------------------------------------------------------------------------
# Socket.IO Redis Sentinel manager
# ---------------------------------------------------------------------------


class AsyncRedisSentinelManager(socketio.AsyncRedisManager):
    """Socket.IO async manager backed by Redis Sentinel.

    Replicates the initialisation sequence of
    :class:`socketio.AsyncRedisManager` but routes all traffic through
    a Sentinel-monitored master instead of a standalone Redis instance.

    The worker thread is lazily started on the first ``on_end`` call to
    avoid unnecessary resource allocation when no spans are emitted.

    Args:
        sentinel_hosts: List of Sentinel hostnames.
        sentinel_port: Sentinel listener port.
        redis_port: Redis data port (forwarded to aioredis).
        service: Sentinel master service name.
        db: Redis database number.
        username: Redis username (if any).
        password: Redis password (if any).
        channel: Pub/sub channel for Socket.IO notifications.
        write_only: If ``True``, only emit events (no receiving).
        logger: Optional logger instance.
        redis_options: Extra keyword arguments forwarded to aioredis.
    """

    def __init__(
        self,
        sentinel_hosts: List[str],
        sentinel_port: int = 26379,
        redis_port: int = 6379,
        service: str = "mymaster",
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        channel: str = "socketio",
        write_only: bool = False,
        logger: Optional[Any] = None,
        redis_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._sentinels = [(host, sentinel_port) for host in sentinel_hosts]
        self._redis_port = redis_port
        self._service = service
        self._db = db
        self._username = username
        self._password = password
        self._channel = channel
        self.redis_options = redis_options or {}

        # Establish connection and initialise grandparent constructor
        self._redis_connect()
        super(socketio.AsyncRedisManager, self).__init__(
            channel=channel, write_only=write_only, logger=logger
        )

    def _redis_connect(self) -> None:
        """Open async Redis connections through Sentinel."""
        sentinel = aioredis.sentinel.Sentinel(
            self._sentinels,
            port=self._redis_port,
            db=self._db,
            password=self._password,
            **self.redis_options,
        )
        self.redis = sentinel.master_for(self._service)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
