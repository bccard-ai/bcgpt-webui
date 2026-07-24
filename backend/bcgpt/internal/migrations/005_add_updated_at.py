"""Migration 005 — Replace chat timestamp with created_at / updated_at.

Converts the single ``timestamp`` column on the ``chat`` table into two
explicit fields:

- ``created_at`` — When the chat was originally created.
- ``updated_at`` — When the chat was last modified.

The migration copies the existing ``timestamp`` value into both new columns,
drops ``timestamp``, and then tightens the NOT NULL constraint.

The column types differ by backend:

- **SQLite** — :class:`~peewee.DateTimeField` (ISO-8601 strings).
- **External (PostgreSQL)** — :class:`~peewee.BigIntegerField` (epoch millis).

Rollback reverses the process: recreates ``timestamp`` from ``created_at``,
drops the two new columns, and restores NOT NULL.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


# ---------------------------------------------------------------------------
# Forward migration
# ---------------------------------------------------------------------------


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Dispatch to the backend-specific timestamp migration."""
    if isinstance(database, pw.SqliteDatabase):
        migrate_sqlite(migrator, database, fake=fake)
    else:
        migrate_external(migrator, database, fake=fake)


def migrate_sqlite(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """SQLite: DateTimeField-based created_at / updated_at."""
    # Add nullable columns first for safe transition
    migrator.add_fields(
        "chat",
        created_at=pw.DateTimeField(null=True),
        updated_at=pw.DateTimeField(null=True),
    )

    # Copy existing timestamp data
    migrator.sql(
        "UPDATE chat SET created_at = timestamp, updated_at = timestamp "
        "WHERE timestamp IS NOT NULL"
    )

    # Drop the legacy column
    migrator.remove_fields("chat", "timestamp")

    # Tighten constraints now that data is populated
    migrator.change_fields(
        "chat",
        created_at=pw.DateTimeField(null=False),
        updated_at=pw.DateTimeField(null=False),
    )


def migrate_external(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """PostgreSQL: BigIntegerField-based created_at / updated_at."""
    # Add nullable columns first for safe transition
    migrator.add_fields(
        "chat",
        created_at=pw.BigIntegerField(null=True),
        updated_at=pw.BigIntegerField(null=True),
    )

    # Copy existing timestamp data
    migrator.sql(
        "UPDATE chat SET created_at = timestamp, updated_at = timestamp "
        "WHERE timestamp IS NOT NULL"
    )

    # Drop the legacy column
    migrator.remove_fields("chat", "timestamp")

    # Tighten constraints now that data is populated
    migrator.change_fields(
        "chat",
        created_at=pw.BigIntegerField(null=False),
        updated_at=pw.BigIntegerField(null=False),
    )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Dispatch to the backend-specific rollback."""
    if isinstance(database, pw.SqliteDatabase):
        rollback_sqlite(migrator, database, fake=fake)
    else:
        rollback_external(migrator, database, fake=fake)


def rollback_sqlite(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """SQLite rollback: restore timestamp from created_at."""
    # Recreate timestamp as nullable for safe transition
    migrator.add_fields("chat", timestamp=pw.DateTimeField(null=True))

    # Copy created_at back to timestamp
    migrator.sql("UPDATE chat SET timestamp = created_at")

    # Remove the replacement columns
    migrator.remove_fields("chat", "created_at", "updated_at")

    # Restore NOT NULL
    migrator.change_fields("chat", timestamp=pw.DateTimeField(null=False))


def rollback_external(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """PostgreSQL rollback: restore timestamp from created_at."""
    # Recreate timestamp as nullable for safe transition
    migrator.add_fields("chat", timestamp=pw.BigIntegerField(null=True))

    # Copy created_at back to timestamp
    migrator.sql("UPDATE chat SET timestamp = created_at")

    # Remove the replacement columns
    migrator.remove_fields("chat", "created_at", "updated_at")

    # Restore NOT NULL
    migrator.change_fields("chat", timestamp=pw.BigIntegerField(null=False))
