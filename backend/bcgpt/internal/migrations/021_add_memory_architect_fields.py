"""Peewee migrations -- 021_add_memory_architect_fields.py.

Adds tier, importance, and category columns to the memory table
for the memory-architect feature. All default safely for existing rows.
"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    migrator.add_fields(
        "memory",
        tier=pw.CharField(default="long_term"),
        importance=pw.FloatField(default=0.5),
        category=pw.CharField(default="general"),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_fields("memory", "tier", "importance", "category")
