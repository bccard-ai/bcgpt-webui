"""Add knowledge_graph table (GraphRAG persistence)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-17 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_graph",
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("scope"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_graph")
