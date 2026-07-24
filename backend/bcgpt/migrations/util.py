"""Alembic migration utility helpers.

Provides convenience functions for inspecting the database schema
and generating revision identifiers during migrations.
"""

import uuid
from typing import Set

from alembic import op
from sqlalchemy import Inspector


def get_existing_tables() -> Set[str]:
    """Return the set of table names currently present in the database.

    Uses SQLAlchemy's :class:`Inspector` to reflect the live schema.
    """
    con = op.get_bind()
    inspector = Inspector.from_engine(con)
    return set(inspector.get_table_names())


def get_revision_id() -> str:
    """Generate a random 12-character hex string suitable as an Alembic revision ID."""
    return str(uuid.uuid4()).replace("-", "")[:12]
