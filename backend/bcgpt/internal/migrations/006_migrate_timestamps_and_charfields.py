"""Migration 006 — Normalise timestamp and string column types.

This migration performs two categories of column-type changes:

1. **Timestamp normalisation** — Changes ``timestamp`` columns on
   ``chatidtag``, ``document``, ``modelfile``, ``prompt``, and ``user``
   from whatever type they were originally created with to
   :class:`~peewee.BigIntegerField`.  This ensures a uniform epoch-millisecond
   representation across all tables.

2. **CharField → TextField widening** — Converts several ``CharField`` /
   ``CharField(max_length=255)`` columns to unbounded ``TextField`` so that
   the schema is compatible with external databases (PostgreSQL) that enforce
   length constraints:

   - ``auth.password``
   - ``chat.title``
   - ``document.title``, ``document.filename``
   - ``prompt.title``
   - ``user.profile_image_url``

Rollback reverses to ``DateField`` for timestamps (SQLite) and ``CharField``
for the widened columns.
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
    """Normalise timestamp fields to BigIntegerField and widen string fields to TextField."""

    # --- Timestamp normalisation (epoch millis) ---
    migrator.change_fields("chatidtag", timestamp=pw.BigIntegerField())
    migrator.change_fields("document", timestamp=pw.BigIntegerField())
    migrator.change_fields("modelfile", timestamp=pw.BigIntegerField())
    migrator.change_fields("prompt", timestamp=pw.BigIntegerField())
    migrator.change_fields("user", timestamp=pw.BigIntegerField())

    # --- String widening (CharField → TextField) ---
    migrator.change_fields("auth", password=pw.TextField())
    migrator.change_fields("chat", title=pw.TextField())
    migrator.change_fields("document", title=pw.TextField(), filename=pw.TextField())
    migrator.change_fields("prompt", title=pw.TextField())
    migrator.change_fields("user", profile_image_url=pw.TextField())


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Revert timestamp and string column types to their pre-migration state."""

    # --- Timestamp revert ---
    if isinstance(database, pw.SqliteDatabase):
        # SQLite originally used DateField for these columns
        migrator.change_fields("chatidtag", timestamp=pw.DateField())
        migrator.change_fields("document", timestamp=pw.DateField())
        migrator.change_fields("modelfile", timestamp=pw.DateField())
        migrator.change_fields("prompt", timestamp=pw.DateField())
        migrator.change_fields("user", timestamp=pw.DateField())

    # --- String revert (TextField → CharField) ---
    migrator.change_fields("auth", password=pw.CharField(max_length=255))
    migrator.change_fields("chat", title=pw.CharField())
    migrator.change_fields("document", title=pw.CharField(), filename=pw.CharField())
    migrator.change_fields("prompt", title=pw.CharField())
    migrator.change_fields("user", profile_image_url=pw.CharField())
