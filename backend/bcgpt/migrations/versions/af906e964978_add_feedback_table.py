"""Add feedback table.

Revision ID: af906e964978
Revises: c29facfe716b
Create Date: 2024-10-20 17:02:35.241684

Creates the ``feedback`` table for storing user feedback on
conversations and model responses.
"""

import sqlalchemy as sa
from alembic import op

revision = "af906e964978"
down_revision = "c29facfe716b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the feedback table."""
    op.create_table(
        "feedback",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("version", sa.BigInteger(), default=0),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    """Drop the feedback table."""
    op.drop_table("feedback")
