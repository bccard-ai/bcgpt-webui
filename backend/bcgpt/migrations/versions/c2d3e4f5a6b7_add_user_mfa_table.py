"""Add user_mfa table (TOTP multi-factor authentication)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-17 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_mfa",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("backup_codes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_mfa")
