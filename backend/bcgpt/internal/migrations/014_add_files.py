"""Migration 014 — Create the ``file`` table.

Introduces a table for tracking uploaded files that can be attached to chats
or used as RAG knowledge sources.

Schema:

- ``id`` — ``TextField``, unique, primary key.
- ``user_id`` — ``TextField``, owner of the file.
- ``filename`` — ``TextField``, original filename as uploaded.
- ``meta`` — ``TextField``, JSON metadata (content type, size, hash, etc.).
- ``created_at`` — ``BigIntegerField``, upload timestamp.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create the ``file`` table."""

    @migrator.create_model
    class File(pw.Model):
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        filename = pw.TextField()
        meta = pw.TextField()
        created_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "file"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``file`` table."""
    migrator.remove_model("file")
