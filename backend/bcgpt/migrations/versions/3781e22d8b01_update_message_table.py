"""Update message & channel tables — add threads and reactions.

Revision ID: 3781e22d8b01
Revises: 7826ab40b532
Create Date: 2024-12-30 03:00:00.000000

* Adds ``type`` column to ``channel``.
* Adds ``parent_id`` column to ``message`` for threaded conversations.
* Creates ``message_reaction`` and ``channel_member`` tables.
"""

import sqlalchemy as sa
from alembic import op

revision = "3781e22d8b01"
down_revision = "7826ab40b532"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add channel type, message threading, reactions, and memberships."""
    op.add_column(
        "channel",
        sa.Column("type", sa.Text(), nullable=True),
    )

    op.add_column(
        "message",
        sa.Column("parent_id", sa.Text(), nullable=True),
    )

    op.create_table(
        "message_reaction",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True, unique=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
    )

    op.create_table(
        "channel_member",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True, unique=True),
        sa.Column("channel_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    """Revert channel type, message threading, reactions, and memberships."""
    op.drop_column("channel", "type")
    op.drop_column("message", "parent_id")
    op.drop_table("message_reaction")
    op.drop_table("channel_member")
