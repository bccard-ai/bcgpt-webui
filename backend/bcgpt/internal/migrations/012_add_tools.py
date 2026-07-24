"""Migration 012 — Create the ``tool`` table.

Introduces a dedicated table for user-defined tools that can be invoked by
LLM agents during conversations (BYOF — Bring Your Own Function).

Schema:

- ``id`` — ``TextField``, unique, primary key.
- ``user_id`` — ``TextField``, owner of the tool.
- ``name`` — ``TextField``, human-readable tool name.
- ``content`` — ``TextField``, the Python source code of the tool.
- ``specs`` — ``TextField``, JSON OpenAI-compatible function specs.
- ``meta`` — ``TextField``, JSON metadata (description, manifest, etc.).
- ``created_at`` — ``BigIntegerField``, creation timestamp.
- ``updated_at`` — ``BigIntegerField``, last modification timestamp.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create the ``tool`` table."""

    @migrator.create_model
    class Tool(pw.Model):
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        name = pw.TextField()
        content = pw.TextField()
        specs = pw.TextField()
        meta = pw.TextField()
        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "tool"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``tool`` table."""
    migrator.remove_model("tool")
