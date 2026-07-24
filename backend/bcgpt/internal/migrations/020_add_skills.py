"""Migration 020 — Create the ``skill`` table.

Stores SKILL.md skill definitions: frontmatter, body (prompt instructions),
and bundled reference resources (as JSON metadata). Prompt + reference
content only — no executable scripts.

Schema:
- ``id`` — TextField, unique, primary key.
- ``user_id`` — TextField, owner.
- ``name`` — TextField, skill name.
- ``description`` — TextField, one-line catalog description.
- ``content`` — TextField, SKILL.md body.
- ``meta`` — TextField (JSON), metadata + bundled resources.
- ``is_active`` — BooleanField, default False.
- ``is_global`` — BooleanField, default False (admin catalog).
- ``is_builtin`` — BooleanField, default False (seeded).
- ``created_at`` / ``updated_at`` — BigIntegerField.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create the ``skill`` table."""

    @migrator.create_model
    class Skill(pw.Model):
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        name = pw.TextField()
        description = pw.TextField(default="")
        content = pw.TextField(default="")
        meta = pw.TextField(null=True)
        is_active = pw.BooleanField(default=False)
        is_global = pw.BooleanField(default=False)
        is_builtin = pw.BooleanField(default=False)
        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "skill"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``skill`` table."""
    migrator.remove_model("skill")
