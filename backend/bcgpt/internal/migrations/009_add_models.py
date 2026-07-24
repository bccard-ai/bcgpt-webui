"""Migration 009 — Create the ``model`` table.

Introduces a unified ``model`` table that replaces the legacy ``modelfile``
table.  Each record represents a model configuration that can reference a base
model, carry custom parameters, and store rich metadata.

Schema:

- ``id`` — ``TextField``, unique, primary key (e.g. ``ollama-llama3``).
- ``user_id`` — ``TextField``, owner of the model entry.
- ``base_model_id`` — ``TextField``, nullable, references the parent model.
- ``name`` — ``TextField``, human-readable display name.
- ``meta`` — ``TextField``, JSON blob with description, profile image, etc.
- ``params`` — ``TextField``, JSON blob with model parameters.
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
    """Create the ``model`` table."""

    @migrator.create_model
    class Model(pw.Model):
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        base_model_id = pw.TextField(null=True)
        name = pw.TextField()
        meta = pw.TextField()
        params = pw.TextField()
        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "model"


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Drop the ``model`` table."""
    migrator.remove_model("model")
