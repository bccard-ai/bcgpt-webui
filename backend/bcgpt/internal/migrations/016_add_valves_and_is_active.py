"""Migration 016 — Add valves and is_active columns to tools and functions.

Adds runtime-configuration columns:

- ``tool.valves`` — ``TextField``, nullable.  JSON blob holding user-configured
  valve values (runtime parameters) for tools.
- ``function.valves`` — ``TextField``, nullable.  Same as above for functions.
- ``function.is_active`` — ``BooleanField``, default ``False``.  Controls
  whether the function is currently enabled for execution.

Forward:  adds ``valves`` to both tables and ``is_active`` to ``function``.
Rollback: removes all three columns.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``valves`` and ``is_active`` columns."""
    migrator.add_fields("tool", valves=pw.TextField(null=True))
    migrator.add_fields("function", valves=pw.TextField(null=True))
    migrator.add_fields("function", is_active=pw.BooleanField(default=False))


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove ``valves`` and ``is_active`` columns."""
    migrator.remove_fields("tool", "valves")
    migrator.remove_fields("function", "valves")
    migrator.remove_fields("function", "is_active")
