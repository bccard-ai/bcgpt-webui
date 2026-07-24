"""Add handoff_request table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-31 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "handoff_request",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("chat_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_handoff_request_chat_id", "handoff_request", ["chat_id"])
    op.create_index("ix_handoff_request_user_id", "handoff_request", ["user_id"])
    op.create_index("ix_handoff_request_status", "handoff_request", ["status"])


def downgrade():
    op.drop_index("ix_handoff_request_status", table_name="handoff_request")
    op.drop_index("ix_handoff_request_user_id", table_name="handoff_request")
    op.drop_index("ix_handoff_request_chat_id", table_name="handoff_request")
    op.drop_table("handoff_request")
