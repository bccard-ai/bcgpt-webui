"""Add llm_token_usage + model_pricing tables (FinOps token/cost persistence)

Revision ID: b1c2d3e4f5a6
Revises: f0a1b2c3d4e5
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_token_usage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_token_usage_user_id", "llm_token_usage", ["user_id"])
    op.create_index("ix_llm_token_usage_model", "llm_token_usage", ["model"])
    op.create_index("ix_llm_token_usage_agent_id", "llm_token_usage", ["agent_id"])
    op.create_index("ix_llm_token_usage_created_at", "llm_token_usage", ["created_at"])

    op.create_table(
        "model_pricing",
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_per_1k", sa.Float(), nullable=True),
        sa.Column("output_per_1k", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("model"),
    )


def downgrade() -> None:
    op.drop_table("model_pricing")
    op.drop_index("ix_llm_token_usage_created_at", table_name="llm_token_usage")
    op.drop_index("ix_llm_token_usage_agent_id", table_name="llm_token_usage")
    op.drop_index("ix_llm_token_usage_model", table_name="llm_token_usage")
    op.drop_index("ix_llm_token_usage_user_id", table_name="llm_token_usage")
    op.drop_table("llm_token_usage")
