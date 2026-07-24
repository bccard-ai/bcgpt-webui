"""Migration 011 — Add user settings column.

Adds a nullable ``settings`` text column to the ``user`` table for storing
per-user preference data as a JSON blob (e.g. UI theme, notification prefs).

Forward:  ``user.settings`` — ``TextField``, nullable.
Rollback: removes ``settings``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``settings`` column to the ``user`` table."""
    migrator.add_fields("user", settings=pw.TextField(null=True))


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``settings`` column from ``user``."""
    migrator.remove_fields("user", "settings")
