"""Socket.IO server for real-time event broadcasting.

Manages WebSocket connections, user presence, model usage tracking,
and chat event dispatch. Supports both in-memory and Redis-backed
state via the ``WEBSOCKET_MANAGER`` environment variable.

Public API (exported symbols):
    ``app``, ``sio``, ``log``, ``TIMEOUT_DURATION``,
    ``periodic_usage_pool_cleanup``,
    ``get_models_in_use``, ``usage``, ``connect``, ``disconnect``,
    ``user_join``, ``join_channel``, ``channel_events``, ``user_list``,
    ``get_event_emitter``, ``get_event_call``, ``get_event_caller``,
    ``get_user_id_from_session_pool``, ``get_user_ids_from_room``,
    ``get_active_status_by_user_id``
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Callable, Coroutine

import socketio

from bcgpt.env import (
    ENABLE_WEBSOCKET_SUPPORT,
    GLOBAL_LOG_LEVEL,
    SRC_LOG_LEVELS,
    WEBSOCKET_MANAGER,
    WEBSOCKET_REDIS_LOCK_TIMEOUT,
    WEBSOCKET_REDIS_URL,
    WEBSOCKET_SENTINEL_HOSTS,
    WEBSOCKET_SENTINEL_PORT,
)
from bcgpt.models import Channels, Chats, UserNameResponse, Users
from bcgpt.socket import RedisDict, RedisLock
from bcgpt.utils import decode_token
from bcgpt.utils.redis import (
    AsyncRedisSentinelManager,
    get_sentinels_from_env,
    parse_redis_sentinel_url,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["SOCKET"])

# ---------------------------------------------------------------------------
# Server & transport configuration
# ---------------------------------------------------------------------------

_COMMON_SIO_KWARGS: dict[str, Any] = dict(
    cors_allowed_origins=[],
    async_mode="asgi",
    transports=(["websocket"] if ENABLE_WEBSOCKET_SUPPORT else ["polling"]),
    allow_upgrades=ENABLE_WEBSOCKET_SUPPORT,
    always_connect=True,
)

if WEBSOCKET_MANAGER == "redis":
    if WEBSOCKET_SENTINEL_HOSTS:
        _redis_conf = parse_redis_sentinel_url(WEBSOCKET_REDIS_URL)
        _mgr = AsyncRedisSentinelManager(
            WEBSOCKET_SENTINEL_HOSTS.split(","),
            sentinel_port=int(WEBSOCKET_SENTINEL_PORT),
            redis_port=_redis_conf["port"],
            service=_redis_conf["service"],
            db=_redis_conf["db"],
            username=_redis_conf["username"],
            password=_redis_conf["password"],
        )
    else:
        _mgr = socketio.AsyncRedisManager(WEBSOCKET_REDIS_URL)  # type: ignore[assignment]
    sio = socketio.AsyncServer(client_manager=_mgr, **_COMMON_SIO_KWARGS)
else:
    sio = socketio.AsyncServer(**_COMMON_SIO_KWARGS)

# ---------------------------------------------------------------------------
# State pools
# ---------------------------------------------------------------------------

TIMEOUT_DURATION: int = 3  # seconds before a usage entry is considered stale

if WEBSOCKET_MANAGER == "redis":
    log.debug("Using Redis to manage websockets.")
    _sentinels = get_sentinels_from_env(
        WEBSOCKET_SENTINEL_HOSTS, WEBSOCKET_SENTINEL_PORT
    )
    SESSION_POOL: dict = RedisDict(
        "bcgpt:session_pool",
        redis_url=WEBSOCKET_REDIS_URL,
        redis_sentinels=_sentinels,
    )
    USER_POOL: dict = RedisDict(
        "bcgpt:user_pool",
        redis_url=WEBSOCKET_REDIS_URL,
        redis_sentinels=_sentinels,
    )
    USAGE_POOL: dict = RedisDict(
        "bcgpt:usage_pool",
        redis_url=WEBSOCKET_REDIS_URL,
        redis_sentinels=_sentinels,
    )
    _cleanup_lock = RedisLock(
        redis_url=WEBSOCKET_REDIS_URL,
        lock_name="usage_cleanup_lock",
        timeout_secs=WEBSOCKET_REDIS_LOCK_TIMEOUT,
        redis_sentinels=_sentinels,
    )
    _acquire_lock: Callable[[], Any] = _cleanup_lock.aquire_lock
    _renew_lock: Callable[[], Any] = _cleanup_lock.renew_lock
    _release_lock: Callable[[], Any] = _cleanup_lock.release_lock
else:
    SESSION_POOL: dict = {}
    USER_POOL: dict = {}
    USAGE_POOL: dict = {}
    _acquire_lock = _renew_lock = _release_lock = lambda: True  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# ASGI app
# ---------------------------------------------------------------------------

app = socketio.ASGIApp(sio, socketio_path="/ws/socket.io")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _authenticate_user(auth_data: dict[str, Any] | None) -> Any | None:
    """Decode a JWT token from *auth_data* and return the matching ``User``.

    Returns ``None`` when the token is missing, invalid, or the user
    cannot be resolved.
    """
    if not auth_data or "token" not in auth_data:
        return None
    payload = decode_token(auth_data["token"])
    if payload is None or "id" not in payload:
        return None
    return Users.get_user_by_id(payload["id"])


async def _register_session(sid: str, user: Any) -> None:
    """Add *sid* to the session and user pools and broadcast presence."""
    SESSION_POOL[sid] = user.model_dump()
    USER_POOL[user.id] = USER_POOL.get(user.id, []) + [sid]


async def _broadcast_user_list() -> None:
    """Emit the current list of active user ids to all clients."""
    await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})


async def _broadcast_usage() -> None:
    """Emit the current model-usage snapshot to all clients."""
    await sio.emit("usage", {"models": get_models_in_use()})


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------


def get_models_in_use() -> list[str]:
    """Return the model ids that currently have at least one active session."""
    return list(USAGE_POOL.keys())


async def periodic_usage_pool_cleanup() -> None:
    """Background task that evicts stale usage entries every ``TIMEOUT_DURATION`` seconds.

    Requires a distributed lock when the Redis manager is active so that
    only one instance runs the cleanup loop at a time.
    """
    if not _acquire_lock():
        log.debug("Usage pool cleanup lock already exists. Not running it.")
        return
    log.debug("Running periodic_usage_pool_cleanup")
    try:
        while True:
            if not _renew_lock():
                log.error("Unable to renew cleanup lock. Exiting usage pool cleanup.")
                raise RuntimeError("Unable to renew usage pool cleanup lock")

            now = int(time.time())
            dirty = False
            for model_id in list(USAGE_POOL):
                connections = USAGE_POOL[model_id]
                expired = [
                    sid
                    for sid, details in connections.items()
                    if now - details["updated_at"] > TIMEOUT_DURATION
                ]
                for sid in expired:
                    del connections[sid]

                if not connections:
                    log.debug("Cleaning up model %s from usage pool", model_id)
                    del USAGE_POOL[model_id]
                else:
                    USAGE_POOL[model_id] = connections
                dirty = True

            if dirty:
                await _broadcast_usage()

            await asyncio.sleep(TIMEOUT_DURATION)
    finally:
        _release_lock()


# ---------------------------------------------------------------------------
# Socket.IO event handlers
# ---------------------------------------------------------------------------


@sio.on("usage")  # type: ignore[misc]
async def usage(sid: str, data: dict[str, Any]) -> None:
    """Record that *sid* is actively using ``data["model"]``."""
    model_id: str = data["model"]
    current_time = int(time.time())
    USAGE_POOL[model_id] = {
        **(USAGE_POOL.get(model_id, {})),
        sid: {"updated_at": current_time},
    }
    await _broadcast_usage()


@sio.event  # type: ignore[misc]
async def connect(
    sid: str, environ: dict[str, Any], auth: dict[str, Any] | None
) -> None:
    """Authenticate a new connection and register the user in the presence pool."""
    user = _authenticate_user(auth)
    if user is None:
        return

    await _register_session(sid, user)
    await _broadcast_user_list()
    await _broadcast_usage()


@sio.on("user-join")  # type: ignore[misc]
async def user_join(sid: str, data: dict[str, Any]) -> dict[str, str] | None:
    """Authenticate the user and subscribe their session to all accessible channels.

    Returns ``{"id": ..., "name": ...}`` on success, ``None`` otherwise.
    """
    user = _authenticate_user(data.get("auth"))
    if user is None:
        return None

    await _register_session(sid, user)

    channels = Channels.get_channels_by_user_id(user.id)
    log.debug("user_join %s: channels=%s", user.id, channels)
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")

    await _broadcast_user_list()
    return {"id": user.id, "name": user.name}


@sio.on("join-channels")  # type: ignore[misc]
async def join_channel(sid: str, data: dict[str, Any]) -> None:
    """Subscribe *sid* to every channel the authenticated user can access."""
    user = _authenticate_user(data.get("auth"))
    if user is None:
        return

    channels = Channels.get_channels_by_user_id(user.id)
    log.debug("join_channel %s: channels=%s", user.id, channels)
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")


@sio.on("channel-events")  # type: ignore[misc]
async def channel_events(sid: str, data: dict[str, Any]) -> None:
    """Forward a channel-scoped event (e.g. typing indicator) to all room members."""
    room = f"channel:{data['channel_id']}"
    participants = sio.manager.get_participants(namespace="/", room=room)
    member_sids = [s for s, _ in participants]
    if sid not in member_sids:
        return

    event_data = data["data"]
    if event_data.get("type") != "typing":
        return

    await sio.emit(
        "channel-events",
        {
            "channel_id": data["channel_id"],
            "message_id": data.get("message_id"),
            "data": event_data,
            "user": UserNameResponse(**SESSION_POOL[sid]).model_dump(),
        },
        room=room,
    )


@sio.on("user-list")  # type: ignore[misc]
async def user_list(sid: str) -> None:
    """Broadcast the current user-list to all connected clients."""
    await _broadcast_user_list()


@sio.event  # type: ignore[misc]
async def disconnect(sid: str) -> None:
    """Remove *sid* from the session and user pools and broadcast the updated presence."""
    user = SESSION_POOL.get(sid)
    if user is None:
        return

    del SESSION_POOL[sid]
    user_id = user["id"]
    remaining = [s for s in USER_POOL.get(user_id, []) if s != sid]

    if remaining:
        USER_POOL[user_id] = remaining
    else:
        USER_POOL.pop(user_id, None)

    await _broadcast_user_list()


# ---------------------------------------------------------------------------
# Event emitter / caller factories
# ---------------------------------------------------------------------------


def get_event_emitter(
    request_info: dict[str, Any],
    *,
    update_db: bool = True,
) -> Callable[[dict[str, Any]], Coroutine[Any, Any, None]]:
    """Return a callable that emits ``chat-events`` to the sessions belonging to *request_info["user_id"]*.

    When *update_db* is ``True`` the handler also persists status, message
    and replace events into the chat database.
    """

    async def _emit(event_data: dict[str, Any]) -> None:
        user_id = request_info["user_id"]
        session_ids = list(
            set(
                USER_POOL.get(user_id, [])
                + (
                    [request_info["session_id"]]
                    if request_info.get("session_id")
                    else []
                )
            )
        )

        chat_id = request_info.get("chat_id")
        message_id = request_info.get("message_id")
        generation_id = request_info.get("generation_id")

        for session_id in session_ids:
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "data": event_data,
            }
            if generation_id:
                payload["generation_id"] = generation_id
            await sio.emit(
                "chat-events",
                payload,
                to=session_id,
            )

        if not update_db:
            return

        event_type = event_data.get("type")
        if event_type == "status":
            Chats.add_message_status_to_chat_by_id_and_message_id(
                chat_id,
                message_id,
                event_data.get("data", {}),
            )
        elif event_type == "message":
            message = Chats.get_message_by_id_and_message_id(chat_id, message_id)
            content = message.get("content", "") + event_data.get("data", {}).get(
                "content", ""
            )
            Chats.upsert_message_to_chat_by_id_and_message_id(
                chat_id, message_id, {"content": content}
            )
        elif event_type == "replace":
            content = event_data.get("data", {}).get("content", "")
            Chats.upsert_message_to_chat_by_id_and_message_id(
                chat_id, message_id, {"content": content}
            )

    return _emit


def get_event_call(
    request_info: dict[str, Any],
) -> Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]:
    """Return a callable that sends a ``chat-events`` call and awaits the response."""

    async def _call(event_data: dict[str, Any]) -> Any:
        return await sio.call(
            "chat-events",
            {
                "chat_id": request_info.get("chat_id"),
                "message_id": request_info.get("message_id"),
                "data": event_data,
            },
            to=request_info["session_id"],
        )

    return _call


# Backward-compatible alias (exported in ``__init__.py``).
get_event_caller = get_event_call


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_user_id_from_session_pool(sid: str) -> str | None:
    """Return the user id associated with *sid*, or ``None``."""
    user = SESSION_POOL.get(sid)
    return user["id"] if user else None


def get_user_ids_from_room(room: str) -> list[str]:
    """Return the distinct user ids of all sessions currently in *room*."""
    participants = sio.manager.get_participants(namespace="/", room=room)
    return list(
        {
            SESSION_POOL[pair[0]]["id"]
            for pair in participants
            if pair[0] in SESSION_POOL
        }
    )


def get_active_status_by_user_id(user_id: str) -> bool:
    """Return ``True`` when *user_id* has at least one live session."""
    return user_id in USER_POOL
