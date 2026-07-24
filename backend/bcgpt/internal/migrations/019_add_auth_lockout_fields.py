"""Peewee migrations -- 019_add_auth_lockout_fields.py.

Adds failed login attempt tracking and account lockout fields to the auth table.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator

with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    migrator.add_fields(
        "auth",
        failed_attempts=pw.IntegerField(default=0),
        locked_until=pw.BigIntegerField(null=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_fields("auth", "failed_attempts", "locked_until")
