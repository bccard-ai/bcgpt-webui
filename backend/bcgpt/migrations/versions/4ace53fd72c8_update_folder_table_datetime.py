"""Update folder table — convert DateTime columns to BigInteger timestamps.

Revision ID: 4ace53fd72c8
Revises: af906e964978
Create Date: 2024-10-23 03:00:00.000000

Changes ``folder.created_at`` and ``folder.updated_at`` from
``DateTime`` to ``BigInteger`` (epoch seconds).  Includes PostgreSQL-
specific conversion expressions.
"""

import sqlalchemy as sa
from alembic import op

revision = "4ace53fd72c8"
down_revision = "af906e964978"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert folder timestamp columns from DateTime to BigInteger."""
    with op.batch_alter_table("folder", schema=None) as batch_op:
        # Remove server defaults before type change.
        batch_op.alter_column("created_at", server_default=None)
        batch_op.alter_column("updated_at", server_default=None)

        batch_op.alter_column(
            "created_at",
            type_=sa.BigInteger(),
            existing_type=sa.DateTime(),
            existing_nullable=False,
            postgresql_using="extract(epoch from created_at)::bigint",
        )

        batch_op.alter_column(
            "updated_at",
            type_=sa.BigInteger(),
            existing_type=sa.DateTime(),
            existing_nullable=False,
            postgresql_using="extract(epoch from updated_at)::bigint",
        )


def downgrade() -> None:
    """Revert folder timestamp columns back to DateTime with server defaults."""
    with op.batch_alter_table("folder", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at",
            type_=sa.DateTime(),
            existing_type=sa.BigInteger(),
            existing_nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            "updated_at",
            type_=sa.DateTime(),
            existing_type=sa.BigInteger(),
            existing_nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        )
