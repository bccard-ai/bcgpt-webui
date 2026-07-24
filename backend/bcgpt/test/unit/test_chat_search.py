"""Regression coverage for indexed chat-content search projections."""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bcgpt.models import chats as chats_module
from bcgpt.models.chats import (
    Chat,
    ChatForm,
    ChatSearchMessage,
    ChatTable,
)


@pytest.fixture()
def chat_table(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Chat.__table__.create(engine)
    ChatSearchMessage.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(chats_module, "get_db", test_db)
    return ChatTable(), session_factory


def _payload(title: str, messages: dict) -> dict:
    return {
        "title": title,
        "history": {"messages": messages, "currentId": next(reversed(messages), None)},
    }


def test_projection_keeps_only_bounded_visible_user_and_assistant_text(chat_table):
    table, session_factory = chat_table
    chat = table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat=_payload(
                "Projection",
                {
                    "system": {"id": "system", "role": "system", "content": "secret"},
                    "malformed": None,
                    "user": {"id": "user", "role": "user", "content": "hello"},
                    "assistant": {
                        "id": "assistant",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "visible"},
                            {"type": "tool_call", "content": "hidden tool arguments"},
                        ],
                    },
                },
            )
        ),
    )

    with session_factory() as db:
        rows = (
            db.query(ChatSearchMessage)
            .filter_by(chat_id=chat.id)
            .order_by(ChatSearchMessage.position)
            .all()
        )
        assert [(row.message_id, row.role, row.content) for row in rows] == [
            ("user", "user", "hello"),
            ("assistant", "assistant", "visible"),
        ]


def test_search_returns_latest_message_anchor_and_plain_snippet(chat_table):
    table, _ = chat_table
    chat = table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat=_payload(
                "Unrelated title",
                {
                    "user": {
                        "id": "user",
                        "role": "user",
                        "content": "An earlier needle appears here",
                    },
                    "assistant": {
                        "id": "assistant",
                        "role": "assistant",
                        "content": "The newest NEEDLE is the useful result",
                    },
                },
            )
        ),
    )

    results = table.get_chats_by_user_id_and_search_text("owner-a", "needle")

    assert len(results) == 1
    assert results[0].id == chat.id
    assert results[0].match_message_id == "assistant"
    assert results[0].match_role == "assistant"
    assert "NEEDLE" in results[0].match_snippet
    assert "<" not in results[0].match_snippet


def test_search_escapes_like_wildcards_and_isolates_owners(chat_table):
    table, _ = chat_table
    literal = table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat=_payload(
                "Literal",
                {"a": {"id": "a", "role": "user", "content": "100% complete"}},
            )
        ),
    )
    table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat=_payload(
                "Other",
                {"b": {"id": "b", "role": "user", "content": "ordinary text"}},
            )
        ),
    )
    table.insert_new_chat(
        "owner-b",
        ChatForm(
            chat=_payload(
                "Foreign",
                {"c": {"id": "c", "role": "user", "content": "100% private"}},
            )
        ),
    )

    results = table.get_chats_by_user_id_and_search_text("owner-a", "%")

    assert [result.id for result in results] == [literal.id]
    assert table.get_chats_by_user_id_and_search_text("owner-b", "ordinary") == []


def test_update_and_delete_replace_projection_without_stale_hits(chat_table):
    table, session_factory = chat_table
    chat = table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat=_payload(
                "Mutable",
                {"old": {"id": "old", "role": "user", "content": "stale needle"}},
            )
        ),
    )

    updated = table.update_chat_by_id(
        chat.id,
        _payload(
            "Mutable",
            {"new": {"id": "new", "role": "assistant", "content": "fresh value"}},
        ),
    )
    assert updated is not None
    assert table.get_chats_by_user_id_and_search_text("owner-a", "needle") == []
    fresh = table.get_chats_by_user_id_and_search_text("owner-a", "fresh")
    assert fresh[0].match_message_id == "new"

    assert table.delete_chat_by_id_and_user_id(chat.id, "owner-a") is True
    with session_factory() as db:
        assert db.query(ChatSearchMessage).count() == 0


def test_legacy_flat_messages_are_searchable_without_an_invalid_anchor(chat_table):
    table, _ = chat_table
    chat = table.insert_new_chat(
        "owner-a",
        ChatForm(
            chat={
                "title": "Legacy",
                "messages": [{"role": "user", "content": "legacy searchable phrase"}],
            }
        ),
    )

    results = table.get_chats_by_user_id_and_search_text("owner-a", "searchable")

    assert results[0].id == chat.id
    assert results[0].match_snippet == "legacy searchable phrase"
    assert results[0].match_message_id is None
