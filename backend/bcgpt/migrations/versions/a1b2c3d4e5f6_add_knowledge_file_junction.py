"""add knowledge_file junction table

Revision ID: a1b2c3d4e5f6
Revises: f2b3c4d5e6f7
Create Date: 2026-07-05

Replaces the denormalized ``knowledge.data['file_ids']`` JSON list with a real
junction table (P2.1) for referential integrity and reference-counted orphan
detection. The JSON list is retained as a denormalized cache (the knowledge
router dual-writes during the transition); this migration creates the table and
backfills membership rows from the existing JSON.
"""

from __future__ import annotations

import json
import time

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_file",
        sa.Column(
            "knowledge_id",
            sa.Text(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            sa.Text(),
            sa.ForeignKey("file.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("added_at", sa.BigInteger(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("knowledge_id", "file_id"),
    )
    op.create_index(
        "ix_knowledge_file_file_id", "knowledge_file", ["file_id"], unique=False
    )

    # Backfill membership from knowledge.data['file_ids']. Portable across
    # SQLite (tests) and Postgres (prod): plain INSERT, deduped per KB so the
    # composite PK is never violated by a malformed JSON list.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, data FROM knowledge")).fetchall()
    now = int(time.time())
    insert_sql = sa.text(
        "INSERT INTO knowledge_file (knowledge_id, file_id, added_at, added_by) "
        "VALUES (:k, :f, :t, NULL)"
    )
    for kid, data in rows:
        parsed = data
        if isinstance(parsed, (str, bytes)):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = None
        if not isinstance(parsed, dict):
            continue
        file_ids = parsed.get("file_ids") or []
        seen: set[str] = set()
        for fid in file_ids:
            if not fid or fid in seen:
                continue
            seen.add(fid)
            conn.execute(insert_sql, {"k": kid, "f": fid, "t": now})


def downgrade() -> None:
    op.drop_index("ix_knowledge_file_file_id", table_name="knowledge_file")
    op.drop_table("knowledge_file")
