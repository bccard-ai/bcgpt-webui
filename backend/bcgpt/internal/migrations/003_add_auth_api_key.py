"""Migration 003 — Add API key column to user table.

Adds an ``api_key`` column to the ``user`` table so that users can authenticate
via an API key instead of session-based auth.

Forward:  ``user.api_key`` — ``CharField(255)``, nullable, unique.
Rollback: removes ``api_key``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``api_key`` column to the ``user`` table."""
    migrator.add_fields(
        "user",
        api_key=pw.CharField(max_length=255, null=True, unique=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``api_key`` column from ``user``."""
    migrator.remove_fields("user", "api_key")
