"""Add security_event table

Revision ID: d4e5f6a7b8c9
Revises: b3f8a2c1d4e5
Create Date: 2026-05-31 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "b3f8a2c1d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "security_event",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("scanner_name", sa.String(), nullable=False),
        sa.Column("threat_types", sa.JSON(), nullable=True),
        sa.Column("threat_count", sa.Integer(), default=0),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), default=False),
        sa.Column("is_shadow", sa.Boolean(), default=True),
        sa.Column("text_hash", sa.String(), nullable=True),
        sa.Column("text_sample", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_security_event_timestamp", "security_event", ["timestamp"])
    op.create_index("ix_security_event_user_id", "security_event", ["user_id"])
    op.create_index("ix_security_event_chat_id", "security_event", ["chat_id"])


def downgrade():
    op.drop_index("ix_security_event_chat_id", table_name="security_event")
    op.drop_index("ix_security_event_user_id", table_name="security_event")
    op.drop_index("ix_security_event_timestamp", table_name="security_event")
    op.drop_table("security_event")
