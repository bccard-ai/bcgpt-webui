"""Add HITL approval ticket table

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-17 00:00:04.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "f2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hitl_approval_ticket",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("action_class", sa.String(), nullable=True),
        sa.Column("risk_tier", sa.String(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("node_type", sa.String(), nullable=True),
        sa.Column("arguments", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workflow_run_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.BigInteger(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("sla_deadline", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hitl_approval_ticket_user_id",
        "hitl_approval_ticket",
        ["user_id"],
    )
    op.create_index(
        "ix_hitl_approval_ticket_status",
        "hitl_approval_ticket",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_hitl_approval_ticket_status", table_name="hitl_approval_ticket")
    op.drop_index("ix_hitl_approval_ticket_user_id", table_name="hitl_approval_ticket")
    op.drop_table("hitl_approval_ticket")
