"""Update file table — add hash, data, and updated_at columns.

Revision ID: c0fbf31ca0db
Revises: ca81bd47c050
Create Date: 2024-09-20 15:26:35.241684
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0fbf31ca0db"
down_revision: Union[str, None] = "ca81bd47c050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hash, data (JSON), and updated_at columns to the file table."""
    op.add_column("file", sa.Column("hash", sa.Text(), nullable=True))
    op.add_column("file", sa.Column("data", sa.JSON(), nullable=True))
    op.add_column("file", sa.Column("updated_at", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Remove hash, data, and updated_at columns from the file table."""
    op.drop_column("file", "updated_at")
    op.drop_column("file", "data")
    op.drop_column("file", "hash")
