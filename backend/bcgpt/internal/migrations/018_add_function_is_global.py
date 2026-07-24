"""Migration 018 — Add is_global flag to functions.

Adds an ``is_global`` boolean column to the ``function`` table.  When set to
``True``, the function is available to all users regardless of ownership,
enabling administrator-published global functions.

Forward:  ``function.is_global`` — ``BooleanField``, default ``False``.
Rollback: removes ``is_global``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``is_global`` column to the ``function`` table."""
    migrator.add_fields(
        "function",
        is_global=pw.BooleanField(default=False),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``is_global`` column from ``function``."""
    migrator.remove_fields("function", "is_global")
