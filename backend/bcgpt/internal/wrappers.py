"""Peewee database connection wrappers and reconnection support.

This module provides the Peewee ORM connection layer used exclusively by the
migration bridge in :mod:`bcgpt.internal.db`.  It handles:

- A custom :class:`PeeweeConnectionState` that stores connection state in a
  :class:`contextvars.ContextVar` instead of instance attributes (needed for
  thread-safe operation with Gradio / FastAPI).
- :class:`CustomReconnectMixin` / :class:`ReconnectingPostgresqlDatabase` that
  automatically reconnect when PostgreSQL drops idle connections.
- :func:`register_connection` — the public entry-point for creating a Peewee
  database instance from a connection URL.

Key exports (re-exported through ``bcgpt.internal.__init__``):

- :func:`register_connection` — Create and return a Peewee ``Database``.
- :class:`PeeweeConnectionState`
- :class:`CustomReconnectMixin`
- :class:`ReconnectingPostgresqlDatabase`
- :data:`db_state_default` / :data:`db_state`
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Dict

from bcgpt.env import SRC_LOG_LEVELS
from peewee import InterfaceError as PeeWeeInterfaceError
from peewee import OperationalError
from peewee import PostgresqlDatabase
from peewee import SqliteDatabase
from psycopg2 import InterfaceError
from playhouse.db_url import connect, parse
from playhouse.shortcuts import ReconnectMixin

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])


# ---------------------------------------------------------------------------
# Thread-safe connection state via ContextVar
# ---------------------------------------------------------------------------

db_state_default: Dict[str, Any] = {
    "closed": None,
    "conn": None,
    "ctx": None,
    "transactions": None,
}
"""Default connection state dictionary used to initialise the context var."""

db_state: ContextVar[Dict[str, Any]] = ContextVar(
    "db_state",
    default=db_state_default.copy(),
)
"""Thread-local store for the current Peewee connection state."""


class PeeweeConnectionState:
    """Proxy that delegates attribute access to a :class:`ContextVar`.

    Peewee's :class:`~peewee.Database` stores connection metadata as instance
    attributes.  In a multi-threaded ASGI application this leads to races.
    By intercepting ``__setattr__`` / ``__getattr__`` and routing them through
    a :class:`ContextVar`, each thread (or asyncio task) gets its own isolated
    connection state.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__setattr__("_state", db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        self._state.get()[name] = value

    def __getattr__(self, name: str) -> Any:
        return self._state.get()[name]


# ---------------------------------------------------------------------------
# Auto-reconnecting PostgreSQL driver
# ---------------------------------------------------------------------------


class CustomReconnectMixin(ReconnectMixin):
    """Reconnection mixin that recognises PostgreSQL connection-lost errors.

    Catches ``OperationalError`` with "termin" (typical when PG terminates an
    idle connection) and ``InterfaceError`` with "closed" (psycopg2 / Peewee
    wrapper).
    """

    reconnect_errors = (
        # psycopg2
        (OperationalError, "termin"),
        (InterfaceError, "closed"),
        # peewee
        (PeeWeeInterfaceError, "closed"),
    )


class ReconnectingPostgresqlDatabase(CustomReconnectMixin, PostgresqlDatabase):
    """PostgreSQL database class with automatic reconnection on lost connections.

    Combines :class:`CustomReconnectMixin` with Peewee's built-in
    :class:`~peewee.PostgresqlDatabase`.
    """

    pass


# ---------------------------------------------------------------------------
# Public connection factory
# ---------------------------------------------------------------------------


def register_connection(db_url: str) -> Any:
    """Create a Peewee database instance from a connection URL.

    For PostgreSQL URLs the function wraps the connection in
    :class:`ReconnectingPostgresqlDatabase` so that dropped connections are
    transparently re-established.

    Args:
        db_url: A Peewee-compatible database URL (e.g.
            ``postgres://user:pass@host/db`` or ``sqlite:///path/to/file``).

    Returns:
        A :class:`~peewee.Database` subclass instance ready for queries.

    Raises:
        ValueError: If the URL does not resolve to a supported database type.
    """
    db = connect(db_url, unquote_password=True)

    if isinstance(db, PostgresqlDatabase):
        # Enable autoconnect for PostgreSQL databases, managed by Peewee
        db.autoconnect = True
        db.reuse_if_open = True
        log.info("Connected to PostgreSQL database")

        # Parse the URL again to extract connection parameters
        connection = parse(db_url, unquote_password=True)

        # Replace with our custom database class that supports reconnection
        db = ReconnectingPostgresqlDatabase(**connection)
        db.connect(reuse_if_open=True)

    elif isinstance(db, SqliteDatabase):
        # Enable autoconnect for SQLite databases, managed by Peewee
        db.autoconnect = True
        db.reuse_if_open = True
        log.info("Connected to SQLite database")

    else:
        raise ValueError("Unsupported database connection")

    return db
