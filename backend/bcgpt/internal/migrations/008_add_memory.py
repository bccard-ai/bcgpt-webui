"""Migration 008 — Create the ``memory`` table.

Introduces a dedicated table for storing user-specific persistent memories.
Each memory record is a snippet of content that the LLM can recall across
conversations to personalise responses.

Schema:

- ``id`` — ``CharField(255)``, unique, primary key.
- ``user_id`` — ``CharField(255)``, owner of the memory.
- ``content`` — ``TextField``, the memory text (NOT NULL).
- ``updated_at`` — ``BigIntegerField``, last modification timestamp.
- ``created_at`` — ``BigIntegerField``, creation timestamp.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create the ``memory`` table."""

    @migrator.create_model
    class Memory(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        content = pw.TextField(null=False)
        updated_at = pw.BigIntegerField(null=False)
        created_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "memory"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``memory`` table."""
    migrator.remove_model("memory")
