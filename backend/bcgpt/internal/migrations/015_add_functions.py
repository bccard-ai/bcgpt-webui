"""Migration 015 — Create the ``function`` table.

Introduces a table for storing user-defined Python functions that extend the
platform's capabilities (pipelines, filters, etc.).

Schema:

- ``id`` — ``TextField``, unique, primary key.
- ``user_id`` — ``TextField``, owner of the function.
- ``name`` — ``TextField``, human-readable function name.
- ``type`` — ``TextField``, function type (e.g. ``filter``, ``pipe``).
- ``content`` — ``TextField``, the Python source code.
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
    """Create the ``function`` table."""

    @migrator.create_model
    class Function(pw.Model):
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        name = pw.TextField()
        type = pw.TextField()
        content = pw.TextField()
        meta = pw.TextField()
        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "function"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``function`` table."""
    migrator.remove_model("function")
