"""Add indexed chat search and durable generation admission/replay ledgers.

Revision ID: a3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-07-19 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a3c4d5e6f7a8"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


_MAX_SEARCH_MESSAGE_CHARS = 100_000
_MAX_SEARCH_MESSAGES_PER_CHAT = 20_000
_MAX_SEARCH_CHAT_CHARS = 2_000_000


def _searchable_content(content) -> str:
    if isinstance(content, str):
        return content.replace("\x00", "")[:_MAX_SEARCH_MESSAGE_CHARS]
    if not isinstance(content, list):
        return ""
    parts = []
    remaining = _MAX_SEARCH_MESSAGE_CHARS
    for block in content:
        value = ""
        if isinstance(block, str):
            value = block
        elif isinstance(block, dict) and block.get("type") in {
            "text",
            "input_text",
            "output_text",
        }:
            candidate = block.get("text", block.get("content", ""))
            if isinstance(candidate, str):
                value = candidate
        if value and remaining > 0:
            value = value.replace("\x00", "")[:remaining]
            parts.append(value)
            remaining -= len(value)
        if remaining <= 0:
            break
    return "\n".join(parts)[:_MAX_SEARCH_MESSAGE_CHARS]


def _projection_rows(chat_id, user_id, chat_data, updated_at):
    if not isinstance(chat_data, dict):
        return
    history = chat_data.get("history")
    messages = history.get("messages") if isinstance(history, dict) else None
    if not messages:
        messages = chat_data.get("messages")
    if isinstance(messages, dict):
        entries = messages.items()
        anchorable = True
    elif isinstance(messages, list):
        entries = enumerate(messages)
        anchorable = False
    else:
        return

    seen = set()
    remaining_chat_chars = _MAX_SEARCH_CHAT_CHARS
    for position, (key, message) in enumerate(entries):
        if position >= _MAX_SEARCH_MESSAGES_PER_CHAT or remaining_chat_chars <= 0:
            break
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        message_id = str(message.get("id") or key)
        content = _searchable_content(message.get("content"))
        if not message_id or len(message_id) > 255 or message_id in seen or not content:
            continue
        content = content[:remaining_chat_chars]
        remaining_chat_chars -= len(content)
        seen.add(message_id)
        yield {
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "position": position,
            "anchorable": anchorable,
            "updated_at": updated_at,
        }


def upgrade() -> None:
    op.create_table(
        "chat_search_message",
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("anchorable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_search_message_role",
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chat.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_id", "message_id"),
    )
    op.create_index(
        "ix_chat_search_message_user_chat",
        "chat_search_message",
        ["user_id", "chat_id"],
    )
    op.create_index(
        "ix_chat_search_message_user_updated",
        "chat_search_message",
        ["user_id", "updated_at"],
    )

    bind = op.get_bind()
    source_chat = sa.table(
        "chat",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("chat", sa.JSON()),
        sa.column("updated_at", sa.BigInteger()),
    )
    projection = sa.table(
        "chat_search_message",
        sa.column("chat_id", sa.String()),
        sa.column("message_id", sa.String(length=255)),
        sa.column("user_id", sa.String()),
        sa.column("role", sa.String()),
        sa.column("content", sa.Text()),
        sa.column("position", sa.Integer()),
        sa.column("anchorable", sa.Boolean()),
        sa.column("updated_at", sa.BigInteger()),
    )
    result = bind.execute(
        sa.select(
            source_chat.c.id,
            source_chat.c.user_id,
            source_chat.c.chat,
            source_chat.c.updated_at,
        ).execution_options(stream_results=True)
    ).mappings()
    while True:
        source_rows = result.fetchmany(250)
        if not source_rows:
            break
        batch = []
        for row in source_rows:
            if not row["id"] or not row["user_id"]:
                continue
            for projected in _projection_rows(
                row["id"], row["user_id"], row["chat"], row["updated_at"] or 0
            ):
                batch.append(projected)
                if len(batch) >= 500:
                    bind.execute(projection.insert(), batch)
                    batch.clear()
        if batch:
            bind.execute(projection.insert(), batch)

    op.create_table(
        "chat_generation",
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("turn_id", sa.String(), nullable=True),
        sa.Column("client_message_id", sa.String(), nullable=True),
        sa.Column("assistant_message_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("terminal_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("admitted_at", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.BigInteger(), nullable=True),
        sa.Column("terminal_at", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "status IN ('admitted', 'running', 'stop_requested', "
            "'completed', 'stopped', 'error', 'timed_out')",
            name="ck_chat_generation_status",
        ),
        sa.PrimaryKeyConstraint("generation_id"),
    )
    active_status_predicate = sa.text(
        "status IN ('admitted', 'running', 'stop_requested')"
    )
    op.create_index(
        "uq_chat_generation_active_assistant_authority",
        "chat_generation",
        ["user_id", "chat_id", "assistant_message_id"],
        unique=True,
        sqlite_where=active_status_predicate,
        postgresql_where=active_status_predicate,
    )
    op.create_index(
        "ix_chat_generation_user_chat_status",
        "chat_generation",
        ["user_id", "chat_id", "status"],
    )
    op.create_index("ix_chat_generation_task_id", "chat_generation", ["task_id"])
    op.create_index("ix_chat_generation_updated_at", "chat_generation", ["updated_at"])

    op.create_table(
        "chat_generation_replay",
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("assistant_message_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("terminal_at", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'stopped', 'error', 'timed_out')",
            name="ck_chat_generation_replay_status",
        ),
        sa.CheckConstraint(
            "last_sequence >= 0 AND event_count >= 0 AND total_bytes >= 0",
            name="ck_chat_generation_replay_counters",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["chat_generation.generation_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("generation_id"),
    )
    op.create_index(
        "ix_chat_generation_replay_user_chat",
        "chat_generation_replay",
        ["user_id", "chat_id"],
    )
    op.create_index(
        "ix_chat_generation_replay_expires_at",
        "chat_generation_replay",
        ["expires_at"],
    )

    op.create_table(
        "chat_generation_replay_event",
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("payload_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "payload_bytes >= 0",
            name="ck_chat_generation_replay_event_bytes",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["chat_generation_replay.generation_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("generation_id", "sequence"),
    )
    op.create_index(
        "ix_chat_generation_replay_event_expires_at",
        "chat_generation_replay_event",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_generation_replay_event_expires_at",
        table_name="chat_generation_replay_event",
    )
    op.drop_table("chat_generation_replay_event")
    op.drop_index(
        "ix_chat_generation_replay_expires_at",
        table_name="chat_generation_replay",
    )
    op.drop_index(
        "ix_chat_generation_replay_user_chat",
        table_name="chat_generation_replay",
    )
    op.drop_table("chat_generation_replay")
    op.drop_index(
        "uq_chat_generation_active_assistant_authority",
        table_name="chat_generation",
    )
    op.drop_index("ix_chat_generation_updated_at", table_name="chat_generation")
    op.drop_index("ix_chat_generation_task_id", table_name="chat_generation")
    op.drop_index("ix_chat_generation_user_chat_status", table_name="chat_generation")
    op.drop_table("chat_generation")
    op.drop_index(
        "ix_chat_search_message_user_updated",
        table_name="chat_search_message",
    )
    op.drop_index(
        "ix_chat_search_message_user_chat",
        table_name="chat_search_message",
    )
    op.drop_table("chat_search_message")
