"""Migration 010 — Migrate modelfile entries to the new model table.

This is a data migration that:

1. Reads every row from the legacy ``modelfile`` table.
2. Parses the Ollama modelfile content to extract the base model ID and
   parameters.
3. Constructs a JSON ``meta`` blob with description, image URL, suggestion
   prompts, categories, and community user info.
4. Inserts a corresponding row into the ``model`` table (created in migration
   009) with the transformed data.
5. Drops the ``modelfile`` table.

Rollback recreates the ``modelfile`` table and reverse-transforms the data
back from ``model`` to ``modelfile``, then drops the ``model`` table.
"""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any, Dict

import peewee as pw
from peewee_migrate import Migrator

from bcgpt.utils import parse_ollama_modelfile

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


# ---------------------------------------------------------------------------
# Forward migration
# ---------------------------------------------------------------------------


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Move all modelfile data into the model table and drop modelfile."""
    migrate_modelfile_to_model(migrator, database)
    migrator.remove_model("modelfile")


def migrate_modelfile_to_model(migrator: Migrator, database: pw.Database) -> None:
    """Read each ``modelfile`` row, transform its data, and insert into ``model``."""
    ModelFile = migrator.orm["modelfile"]
    Model = migrator.orm["model"]

    modelfiles = ModelFile.select()

    for modelfile in modelfiles:
        modelfile_data: Dict[str, Any] = json.loads(modelfile.modelfile)

        meta: str = json.dumps(
            {
                "description": modelfile_data.get("desc"),
                "profile_image_url": modelfile_data.get("imageUrl"),
                "ollama": {"modelfile": modelfile_data.get("content")},
                "suggestion_prompts": modelfile_data.get("suggestionPrompts"),
                "categories": modelfile_data.get("categories"),
                "user": {**modelfile_data.get("user", {}), "community": True},
            }
        )

        info: Dict[str, Any] = parse_ollama_modelfile(modelfile_data.get("content"))

        Model.create(
            id=f"ollama-{modelfile.tag_name}",
            user_id=modelfile.user_id,
            base_model_id=info.get("base_model_id"),
            name=modelfile_data.get("title"),
            meta=meta,
            params=json.dumps(info.get("params", {})),
            created_at=modelfile.timestamp,
            updated_at=modelfile.timestamp,
        )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Recreate the modelfile table, reverse-migrate data, and drop model."""
    recreate_modelfile_table(migrator, database)
    move_data_back_to_modelfile(migrator, database)
    migrator.remove_model("model")


def recreate_modelfile_table(migrator: Migrator, database: pw.Database) -> None:
    """Issue raw DDL to recreate the ``modelfile`` table."""
    migrator.sql(
        """
        CREATE TABLE IF NOT EXISTS modelfile (
            user_id TEXT,
            tag_name TEXT,
            modelfile JSON,
            timestamp BIGINT
        )
        """
    )


def move_data_back_to_modelfile(migrator: Migrator, database: pw.Database) -> None:
    """Read each ``model`` row and reverse-transform it back to ``modelfile``."""
    Model = migrator.orm["model"]
    Modelfile = migrator.orm["modelfile"]

    models = Model.select()

    for model in models:
        meta: Dict[str, Any] = json.loads(model.meta)

        modelfile_data: Dict[str, Any] = {
            "title": model.name,
            "desc": meta.get("description"),
            "imageUrl": meta.get("profile_image_url"),
            "content": meta.get("ollama", {}).get("modelfile"),
            "suggestionPrompts": meta.get("suggestion_prompts"),
            "categories": meta.get("categories"),
            "user": {k: v for k, v in meta.get("user", {}).items() if k != "community"},
        }

        Modelfile.create(
            user_id=model.user_id,
            tag_name=model.id,
            modelfile=modelfile_data,
            timestamp=model.created_at,
        )
