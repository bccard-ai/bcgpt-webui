"""Add token_version to auth table

Revision ID: b3f8a2c1d4e5
Revises: 3781e22d8b01
Create Date: 2026-05-31 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "b3f8a2c1d4e5"
down_revision = "3781e22d8b01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "auth",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("auth", "token_version")
