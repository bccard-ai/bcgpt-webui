"""Migration 013 — Add user info column.

Adds a nullable ``info`` text column to the ``user`` table for storing
additional user profile information as a JSON blob (e.g. bio, company, job
title).

Forward:  ``user.info`` — ``TextField``, nullable.
Rollback: removes ``info``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``info`` column to the ``user`` table."""
    migrator.add_fields("user", info=pw.TextField(null=True))


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``info`` column from ``user``."""
    migrator.remove_fields("user", "info")
