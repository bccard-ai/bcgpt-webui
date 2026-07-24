"""Migration 001 — Initial database schema.

Creates the foundational tables inherited from the upstream Open WebUI
codebase:

- ``auth`` — Credential storage (email / password).
- ``chat`` — User conversation records.
- ``chatidtag`` — Many-to-many relationship between chats and tags.
- ``document`` — Uploaded / referenced documents with collection metadata.
- ``modelfile`` — Ollama modelfile definitions.
- ``prompt`` — Saved prompt templates.
- ``tag`` — User-created tags for organising chats.
- ``user`` — User accounts with role and profile information.

The migration is split into two code-paths:

- **SQLite** — Uses ``CharField`` / ``CharField(max_length=255)`` for string
  columns because SQLite does not enforce length constraints and the upstream
  schema was designed around these types.
- **External (PostgreSQL)** — Uses ``TextField`` for unbounded string columns
  to avoid length constraint violations that the SQLite schema would cause
  under strict SQL mode.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Dispatch to the appropriate backend-specific schema creator."""
    if isinstance(database, pw.SqliteDatabase):
        migrate_sqlite(migrator, database, fake=fake)
    else:
        migrate_external(migrator, database, fake=fake)


# ---------------------------------------------------------------------------
# SQLite variant
# ---------------------------------------------------------------------------


def migrate_sqlite(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create initial tables optimised for SQLite."""

    @migrator.create_model
    class Auth(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        email = pw.CharField(max_length=255)
        password = pw.CharField(max_length=255)
        active = pw.BooleanField()

        class Meta:
            table_name = "auth"

    @migrator.create_model
    class Chat(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.CharField()
        chat = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chat"

    @migrator.create_model
    class ChatIdTag(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        tag_name = pw.CharField(max_length=255)
        chat_id = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chatidtag"

    @migrator.create_model
    class Document(pw.Model):
        id = pw.AutoField()
        collection_name = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255, unique=True)
        title = pw.CharField()
        filename = pw.CharField()
        content = pw.TextField(null=True)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "document"

    @migrator.create_model
    class Modelfile(pw.Model):
        id = pw.AutoField()
        tag_name = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        modelfile = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "modelfile"

    @migrator.create_model
    class Prompt(pw.Model):
        id = pw.AutoField()
        command = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.CharField()
        content = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "prompt"

    @migrator.create_model
    class Tag(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        data = pw.TextField(null=True)

        class Meta:
            table_name = "tag"

    @migrator.create_model
    class User(pw.Model):
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        email = pw.CharField(max_length=255)
        role = pw.CharField(max_length=255)
        profile_image_url = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "user"


# ---------------------------------------------------------------------------
# External database (PostgreSQL) variant
# ---------------------------------------------------------------------------


def migrate_external(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Create initial tables for external databases (PostgreSQL).

    Uses ``TextField`` instead of ``CharField`` for columns that may contain
    arbitrarily long values, avoiding length-constraint errors under strict
    SQL modes.
    """

    @migrator.create_model
    class Auth(pw.Model):  # type: ignore[no-redef]
        id = pw.CharField(max_length=255, unique=True)
        email = pw.CharField(max_length=255)
        password = pw.TextField()
        active = pw.BooleanField()

        class Meta:
            table_name = "auth"

    @migrator.create_model
    class Chat(pw.Model):  # type: ignore[no-redef]
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.TextField()
        chat = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chat"

    @migrator.create_model
    class ChatIdTag(pw.Model):  # type: ignore[no-redef]
        id = pw.CharField(max_length=255, unique=True)
        tag_name = pw.CharField(max_length=255)
        chat_id = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chatidtag"

    @migrator.create_model
    class Document(pw.Model):  # type: ignore[no-redef]
        id = pw.AutoField()
        collection_name = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255, unique=True)
        title = pw.TextField()
        filename = pw.TextField()
        content = pw.TextField(null=True)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "document"

    @migrator.create_model
    class Modelfile(pw.Model):  # type: ignore[no-redef]
        id = pw.AutoField()
        tag_name = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        modelfile = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "modelfile"

    @migrator.create_model
    class Prompt(pw.Model):  # type: ignore[no-redef]
        id = pw.AutoField()
        command = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.TextField()
        content = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "prompt"

    @migrator.create_model
    class Tag(pw.Model):  # type: ignore[no-redef]
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        data = pw.TextField(null=True)

        class Meta:
            table_name = "tag"

    @migrator.create_model
    class User(pw.Model):  # type: ignore[no-redef]
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        email = pw.CharField(max_length=255)
        role = pw.CharField(max_length=255)
        profile_image_url = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "user"


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove all tables created by this migration in reverse dependency order."""
    migrator.remove_model("user")
    migrator.remove_model("tag")
    migrator.remove_model("prompt")
    migrator.remove_model("modelfile")
    migrator.remove_model("document")
    migrator.remove_model("chatidtag")
    migrator.remove_model("chat")
    migrator.remove_model("auth")
