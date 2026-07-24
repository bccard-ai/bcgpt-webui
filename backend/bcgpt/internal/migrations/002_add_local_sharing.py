"""Migration 002 — Add local chat sharing.

Adds a ``share_id`` column to the ``chat`` table.  When set, the chat becomes
publicly accessible via the share ID, enabling local (non-OAuth) sharing of
conversations.

Forward:  ``chat.share_id`` — ``CharField(255)``, nullable, unique.
Rollback: removes ``share_id``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``share_id`` column to the ``chat`` table."""
    migrator.add_fields(
        "chat",
        share_id=pw.CharField(max_length=255, null=True, unique=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``share_id`` column from ``chat``."""
    migrator.remove_fields("chat", "share_id")
