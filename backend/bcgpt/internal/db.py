"""SQLAlchemy database engine, session management, and Peewee migration bridge.

This module initializes the application's database layer in two phases:

1. **Peewee migration phase** — Runs all numbered Peewee migrations found in
   ``bcgpt/internal/migrations/`` via :class:`peewee_migrate.Router`.  This
   handles legacy schema evolution inherited from the upstream Open WebUI
   codebase.

2. **SQLAlchemy engine phase** — Creates a :class:`sqlalchemy.engine.Engine`
   (with optional connection pooling for PostgreSQL) and exposes a
   :class:`sqlalchemy.orm.sessionmaker` / scoped session for the rest of the
   application.

Key exports (re-exported through ``bcgpt.internal.__init__``):

- :data:`engine`          — SQLAlchemy engine instance
- :data:`SessionLocal`    — Session factory
- :data:`Session`         — Thread-local scoped session
- :data:`Base`            — Declarative base for ORM models
- :data:`metadata_obj`    — :class:`sqlalchemy.MetaData` bound to the schema
- :func:`get_session`     — Generator-based session dependency (FastAPI)
- :func:`get_db`          — Context-manager wrapper around *get_session*
- :class:`JSONField`      — SQLAlchemy type that stores Python objects as JSON
- :func:`handle_peewee_migration` — Runs the Peewee migration router
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

from typing_extensions import Self

from bcgpt.env import (
    BCGPT_DIR,
    DATABASE_POOL_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
    DATABASE_SCHEMA,
    DATABASE_URL,
    SRC_LOG_LEVELS,
)
from bcgpt.internal import register_connection
from peewee_migrate import Router
from sqlalchemy import Dialect, MetaData, create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.sql.type_api import _T

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])


# ---------------------------------------------------------------------------
# Custom SQLAlchemy column types
# ---------------------------------------------------------------------------


class JSONField(types.TypeDecorator):
    """SQLAlchemy column type that transparently serialises Python objects to
    JSON text and deserialises them on read.

    This is used throughout the ORM models for columns that store arbitrary
    JSON-serialisable data (e.g. model metadata, function specs, user settings).
    """

    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Any:
        """Serialise *value* to a JSON string before writing to the database."""
        return json.dumps(value)

    def process_result_value(self, value: Optional[_T], dialect: Dialect) -> Any:
        """Deserialise a JSON string from the database into a Python object."""
        if value is not None:
            return json.loads(value)
        return None

    def copy(self, **kw: Any) -> Self:
        """Return a copy of this type instance (required by SQLAlchemy)."""
        return JSONField(self.impl.length)

    def db_value(self, value: Any) -> str:
        """Peewee-compatible bind-value converter."""
        return json.dumps(value)

    def python_value(self, value: Any) -> Any:
        """Peewee-compatible result-value converter."""
        if value is not None:
            return json.loads(value)
        return None


# ---------------------------------------------------------------------------
# Peewee migration bridge
# ---------------------------------------------------------------------------


def handle_peewee_migration(database_url: str) -> None:
    """Run all pending Peewee schema migrations.

    The function opens a Peewee database connection (replacing
    ``postgresql://`` with ``postgres://`` for driver compatibility), runs the
    migration router, and then asserts the connection is fully closed so that
    the subsequent SQLAlchemy engine can take over without conflicts.

    Args:
        database_url: The database connection string.  PostgreSQL URLs are
            automatically rewritten to the ``postgres://`` scheme expected by
            Peewee's :func:`playhouse.db_url.connect`.

    Raises:
        Exception: If the migration router fails to initialise or execute.
    """
    db = None
    try:
        # Peewee uses the 'postgres://' scheme; SQLAlchemy uses 'postgresql://'
        db = register_connection(database_url.replace("postgresql://", "postgres://"))
        migrate_dir = BCGPT_DIR / "internal" / "migrations"
        router = Router(db, logger=log, migrate_dir=migrate_dir)
        router.run()
        db.close()

    except Exception:
        log.exception("Failed to initialise the database connection")
        raise
    finally:
        if db and not db.is_closed():
            db.close()

        # Safety assertion — the Peewee connection must not leak
        assert db is None or db.is_closed(), "Database connection is still open."


# Execute Peewee migrations eagerly at import time so that the schema is
# up-to-date before any SQLAlchemy models reference it.
# Skip when BCGPT_SKIP_IMPORT_TIME_MIGRATIONS is set (Phase 1 of ADR Option D —
# import-safe contract per BACKEND_ARCHITECTURE_TESTABILITY_PLAN §5 Phase 1).
if not os.environ.get("BCGPT_SKIP_IMPORT_TIME_MIGRATIONS"):
    handle_peewee_migration(DATABASE_URL)


# ---------------------------------------------------------------------------
# SQLAlchemy engine & session configuration
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL: str = DATABASE_URL

if "sqlite" in SQLALCHEMY_DATABASE_URL:
    # SQLite only allows single-threaded access unless we explicitly opt in.
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
elif DATABASE_POOL_SIZE > 0:
    # PostgreSQL with connection pooling for production workloads.
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=DATABASE_POOL_SIZE,
        max_overflow=DATABASE_POOL_MAX_OVERFLOW,
        pool_timeout=DATABASE_POOL_TIMEOUT,
        pool_recycle=DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        poolclass=QueuePool,
    )
else:
    # PostgreSQL without pooling (e.g. in serverless / short-lived processes).
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        poolclass=NullPool,
    )

SessionLocal: sessionmaker = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

metadata_obj: MetaData = MetaData(schema=DATABASE_SCHEMA)
Base = declarative_base(metadata=metadata_obj)
Session = scoped_session(SessionLocal)


def get_session() -> Generator[Any, None, None]:
    """Yield a database session and guarantee it is closed afterwards.

    This is the standard FastAPI ``Depends`` callable for injecting a
    database session into route handlers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)
"""Context-manager wrapper around :func:`get_session` for non-FastAPI usage."""
