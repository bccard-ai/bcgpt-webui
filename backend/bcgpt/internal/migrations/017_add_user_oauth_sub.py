"""Migration 017 — Add OAuth subject identifier to users.

Adds an ``oauth_sub`` column to the ``user`` table to store the subject
identifier returned by external OAuth/OIDC providers.  This enables linking a
BCGPT user account to an upstream identity provider (e.g. Keycloak, Google).

Forward:  ``user.oauth_sub`` — ``TextField``, nullable, unique.
Rollback: removes ``oauth_sub``.
"""

from __future__ import annotations

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Add ``oauth_sub`` column to the ``user`` table."""
    migrator.add_fields(
        "user",
        oauth_sub=pw.TextField(null=True, unique=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False) -> None:
    """Remove the ``oauth_sub`` column from ``user``."""
    migrator.remove_fields("user", "oauth_sub")
