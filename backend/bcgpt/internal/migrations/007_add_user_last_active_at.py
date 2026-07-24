"""Migration 007 — Replace user timestamp with created_at, updated_at, last_active_at.

Converts the single ``timestamp`` column on the ``user`` table into three
fields:

- ``created_at`` — When the account was originally created.
- ``updated_at`` — When the account was last modified.
- ``last_active_at`` — When the user last interacted with the platform.

The migration copies the existing ``timestamp`` value into all three new
columns, drops ``timestamp``, and tightens the NOT NULL constraint.

All columns use :class:`~peewee.BigIntegerField` (epoch milliseconds).

Rollback reverses the process: recreates ``timestamp`` from ``created_at``,
drops the three new columns, and restores NOT NULL.
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
    """Replace ``user.timestamp`` with ``created_at``, ``updated_at``, ``last_active_at``."""
    # Add nullable columns for safe transition
    migrator.add_fields(
        "user",
        created_at=pw.BigIntegerField(null=True),
        updated_at=pw.BigIntegerField(null=True),
        last_active_at=pw.BigIntegerField(null=True),
    )

    # Populate from the existing timestamp
    migrator.sql(
        'UPDATE "user" SET created_at = timestamp, updated_at = timestamp, '
        "last_active_at = timestamp WHERE timestamp IS NOT NULL"
    )

    # Drop the legacy column
    migrator.remove_fields("user", "timestamp")

    # Tighten constraints
    migrator.change_fields(
        "user",
        created_at=pw.BigIntegerField(null=False),
        updated_at=pw.BigIntegerField(null=False),
        last_active_at=pw.BigIntegerField(null=False),
    )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Restore ``user.timestamp`` from ``created_at`` and drop the new columns."""
    # Recreate timestamp as nullable
    migrator.add_fields("user", timestamp=pw.BigIntegerField(null=True))

    # Copy created_at back
    migrator.sql('UPDATE "user" SET timestamp = created_at')

    # Remove replacement columns
    migrator.remove_fields("user", "created_at", "updated_at", "last_active_at")

    # Restore NOT NULL
    migrator.change_fields("user", timestamp=pw.BigIntegerField(null=False))
