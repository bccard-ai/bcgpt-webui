"""Migration 004 — Add archived flag to chats.

Adds an ``archived`` boolean column to the ``chat`` table so that users can
soft-delete / archive conversations without permanently removing them.

Forward:  ``chat.archived`` — ``BooleanField``, default ``False``.
Rollback: removes ``archived``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``archived`` boolean column to the ``chat`` table."""
    migrator.add_fields("chat", archived=pw.BooleanField(default=False))


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``archived`` column from ``chat``."""
    migrator.remove_fields("chat", "archived")
