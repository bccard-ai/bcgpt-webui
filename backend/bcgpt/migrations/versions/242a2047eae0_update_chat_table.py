"""Update chat table — convert chat column from Text to JSON.

Revision ID: 242a2047eae0
Revises: 6a39f3d8e55c
Create Date: 2024-10-09 21:02:35.241684

Renames the existing ``chat`` text column to ``old_chat``, adds a new
JSON-typed ``chat`` column, migrates the data, then drops ``old_chat``.
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import select, table, update

revision = "242a2047eae0"
down_revision = "6a39f3d8e55c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert the chat.chat column from Text to JSON."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    columns = inspector.get_columns("chat")
    column_dict = {col["name"]: col for col in columns}

    chat_column = column_dict.get("chat")
    old_chat_exists = "old_chat" in column_dict

    if chat_column:
        if isinstance(chat_column["type"], sa.Text):
            print("Converting 'chat' column to JSON")

            if old_chat_exists:
                print("Dropping old 'old_chat' column")
                op.drop_column("chat", "old_chat")

            # Rename current text column to old_chat.
            print("Renaming 'chat' column to 'old_chat'")
            op.alter_column(
                "chat", "chat", new_column_name="old_chat", existing_type=sa.Text()
            )

            # Add new JSON-typed chat column.
            print("Adding new 'chat' column of type JSON")
            op.add_column("chat", sa.Column("chat", sa.JSON(), nullable=True))

    # Migrate data from old_chat (text) to chat (JSON).
    chat_table = table(
        "chat",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("old_chat", sa.Text()),
        sa.Column("chat", sa.JSON()),
    )

    connection = op.get_bind()
    results = connection.execute(select(chat_table.c.id, chat_table.c.old_chat))
    for row in results:
        try:
            json_data = json.loads(row.old_chat)
        except json.JSONDecodeError:
            json_data = None

        connection.execute(
            sa.update(chat_table)
            .where(chat_table.c.id == row.id)
            .values(chat=json_data)
        )

    # Drop the temporary old_chat column.
    print("Dropping 'old_chat' column")
    op.drop_column("chat", "old_chat")


def downgrade() -> None:
    """Revert chat.chat from JSON back to Text."""
    # Restore old_chat as Text.
    op.add_column("chat", sa.Column("old_chat", sa.Text(), nullable=True))

    chat_table = table(
        "chat",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chat", sa.JSON()),
        sa.Column("old_chat", sa.Text()),
    )

    connection = op.get_bind()
    results = connection.execute(select(chat_table.c.id, chat_table.c.chat))
    for row in results:
        text_data = json.dumps(row.chat) if row.chat is not None else None
        connection.execute(
            sa.update(chat_table)
            .where(chat_table.c.id == row.id)
            .values(old_chat=text_data)
        )

    # Remove the JSON column and rename old_chat back.
    op.drop_column("chat", "chat")
    op.alter_column("chat", "old_chat", new_column_name="chat", existing_type=sa.Text())
