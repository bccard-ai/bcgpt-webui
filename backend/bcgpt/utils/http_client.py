"""
Shared aiohttp ClientSession with connection pooling.

Instead of creating a new ClientSession per request (which re-opens TCP
connections, re-negotiates TLS, and re-resolves DNS every time), we keep
a single long-lived session with a connection pool.

IMPORTANT: The session is created WITHOUT a default timeout so that each
request can specify its own via the ``timeout`` parameter of
``session.request()`` / ``session.get()`` / ``session.post()`` etc.
If a request does not pass a timeout, it will wait indefinitely — callers
MUST supply appropriate timeouts for non-streaming operations.

Usage:
    from bcgpt.utils.http_client import get_client_session, close_client_session

    # In request handlers:
    session = await get_client_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        ...

    # Streaming (no timeout needed):
    session = await get_client_session()
    async with session.post(url, data=body) as resp:
        ...

    # In app lifespan shutdown (optional — lifespan exit handles it):
    await close_client_session()
"""

import aiohttp
import logging

log = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None


async def get_client_session(
    trust_env: bool = True,
) -> aiohttp.ClientSession:
    """Return (or lazily create) the shared aiohttp ClientSession.

    The session has NO default timeout — every caller must pass its own
    ``timeout`` to ``session.request()`` / ``.get()`` / ``.post()`` etc.
    """
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None),
            trust_env=trust_env,
            # Request only gzip/deflate to avoid Brotli decode errors when
            # the brotli library is unavailable.  Some upstream LLM APIs
            # (e.g. OpenAI) default to Content-Encoding: br otherwise.
            headers={"Accept-Encoding": "gzip, deflate"},
            auto_decompress=True,
            # TCPConnector with connection pooling enabled by default
            connector=aiohttp.TCPConnector(
                limit=100,  # max total connections
                limit_per_host=20,  # max connections per host
                ttl_dns_cache=300,  # DNS cache 5 minutes
                enable_cleanup_closed=True,
            ),
        )
    return _session


async def close_client_session() -> None:
    """Close the shared session. Call on app shutdown."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        _session = None
