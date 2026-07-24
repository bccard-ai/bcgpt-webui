"""Durable chat generation admission, fencing, and terminal CAS tests."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import bcgpt.models.chat_generations as generation_module
from bcgpt.models.chat_generations import (
    ChatGeneration,
    ChatGenerationReplay,
    ChatGenerationReplayEvent,
    ChatGenerationTable,
)


@pytest.fixture
def generations(monkeypatch) -> ChatGenerationTable:
    engine = create_engine("sqlite:///:memory:")
    ChatGeneration.__table__.create(engine)
    ChatGenerationReplay.__table__.create(engine)
    ChatGenerationReplayEvent.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(generation_module, "get_db", test_db)
    return ChatGenerationTable()


def admission_input(**overrides):
    return {
        "generation_id": "generation-a",
        "turn_id": "turn-a",
        "client_message_id": "user-message-a",
        "assistant_message_id": "assistant-message-a",
        "user_id": "owner-a",
        "chat_id": "chat-a",
        "model_id": "model-a",
        **overrides,
    }


def test_admission_is_idempotent_and_rejects_identity_reuse(generations) -> None:
    accepted = generations.admit(**admission_input())
    assert accepted.kind == "accepted"
    assert accepted.generation.status == "admitted"

    duplicate = generations.admit(**admission_input())
    assert duplicate.kind == "duplicate"
    assert duplicate.generation.generation_id == "generation-a"

    changed_model = generations.admit(**admission_input(model_id="model-b"))
    assert changed_model.kind == "conflict"

    reused_assistant = generations.admit(
        **admission_input(generation_id="generation-b")
    )
    assert reused_assistant.kind == "conflict"


def test_pre_admission_stop_tombstone_fences_late_provider_dispatch(
    generations,
) -> None:
    stop = generations.request_stop(
        generation_id="generation-a",
        user_id="owner-a",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert stop.kind == "already_terminal"
    assert stop.generation.status == "stopped"

    late_admission = generations.admit(**admission_input())
    assert late_admission.kind == "stopped"
    assert late_admission.generation.status == "stopped"
    assert late_admission.generation.request_fingerprint is not None
    assert late_admission.generation.turn_id == "turn-a"


def test_running_generation_stop_wins_terminal_race(generations) -> None:
    generations.admit(**admission_input())
    running = generations.bind_task("generation-a", "owner-a", "task-a")
    assert running is not None
    assert running.status == "running"
    assert running.task_id == "task-a"

    stop = generations.request_stop(
        generation_id="generation-a",
        user_id="owner-a",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert stop.kind == "accepted"
    assert stop.generation.status == "stop_requested"
    assert generations.is_stop_requested("generation-a", "owner-a") is True

    terminal = generations.terminalize(
        "generation-a", "owner-a", "completed", "provider_completed"
    )
    assert terminal is not None
    assert terminal.status == "stopped"
    assert terminal.terminal_reason == "user_requested"

    replayed = generations.request_stop(
        generation_id="generation-a",
        user_id="owner-a",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert replayed.kind == "already_terminal"


def test_completed_terminal_cannot_be_relabelled_stopped(generations) -> None:
    generations.admit(**admission_input())
    completed = generations.terminalize(
        "generation-a", "owner-a", "completed", "provider_completed"
    )
    assert completed is not None
    assert completed.status == "completed"

    stop = generations.request_stop(
        generation_id="generation-a",
        user_id="owner-a",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert stop.kind == "already_completed"

    repeated = generations.terminalize(
        "generation-a", "owner-a", "stopped", "late_stop"
    )
    assert repeated is not None
    assert repeated.status == "completed"
    assert repeated.terminal_reason == "provider_completed"


def test_terminal_generation_allows_a_new_generation_for_continuation(
    generations,
) -> None:
    generations.admit(**admission_input())
    generations.terminalize(
        "generation-a", "owner-a", "completed", "provider_completed"
    )

    continuation = generations.admit(
        **admission_input(
            generation_id="generation-b",
        )
    )
    assert continuation.kind == "accepted"
    assert continuation.generation.status == "admitted"
    assert continuation.generation.assistant_message_id == "assistant-message-a"


def test_owner_and_chat_queries_are_isolated(generations) -> None:
    generations.admit(**admission_input())
    generations.admit(
        **admission_input(
            generation_id="generation-b",
            turn_id="turn-b",
            client_message_id="user-message-b",
            assistant_message_id="assistant-message-b",
            user_id="owner-b",
            chat_id="chat-b",
        )
    )

    assert generations.get_owned("generation-a", "owner-b") is None
    assert [
        row.generation_id
        for row in generations.list_active_by_chat("owner-a", "chat-a")
    ] == ["generation-a"]
    assert generations.list_active_by_chat("owner-a", "chat-b") == []

    mismatch = generations.request_stop(
        generation_id="generation-a",
        user_id="owner-b",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert mismatch.kind == "different_generation"


def test_replay_snapshot_has_monotonic_tail_and_terminal_event(generations) -> None:
    generations.admit(**admission_input())
    generations.bind_task("generation-a", "owner-a", "task-a")

    first = generations.append_replay_snapshot("generation-a", "owner-a", "Hello")
    second = generations.append_replay_snapshot(
        "generation-a", "owner-a", "Hello world"
    )
    assert first is not None and first.last_sequence == 1
    assert second is not None and second.last_sequence == 2
    assert second.content == "Hello world"

    tail = generations.get_replay_tail("generation-a", "owner-a", after_sequence=0)
    assert tail is not None
    assert [event["sequence"] for event in tail["events"]] == [1, 2]
    assert tail["events"][0]["payload"] == {
        "content": "Hello",
        "replace": False,
        "type": "content",
    }
    assert tail["events"][1]["payload"]["content"] == " world"

    generations.terminalize(
        "generation-a", "owner-a", "completed", "provider_completed"
    )
    terminal_tail = generations.get_replay_tail(
        "generation-a", "owner-a", after_sequence=2
    )
    assert terminal_tail is not None
    assert terminal_tail["status"] == "completed"
    assert terminal_tail["events"] == [
        {
            "sequence": 3,
            "type": "terminal",
            "payload": {"status": "completed", "type": "terminal"},
        }
    ]


def test_replay_is_owner_scoped_and_rejects_stale_worker_append(generations) -> None:
    generations.admit(**admission_input())
    generations.bind_task("generation-a", "owner-a", "task-a")
    assert (
        generations.append_replay_snapshot("generation-a", "owner-b", "secret") is None
    )

    generations.request_stop(
        generation_id="generation-a",
        user_id="owner-a",
        chat_id="chat-a",
        assistant_message_id="assistant-message-a",
    )
    assert generations.append_replay_snapshot("generation-a", "owner-a", "late") is None


def test_replay_rewrites_are_explicit_and_tampered_rows_are_quarantined(
    generations, monkeypatch
) -> None:
    generations.admit(**admission_input())
    generations.bind_task("generation-a", "owner-a", "task-a")
    generations.append_replay_snapshot("generation-a", "owner-a", "unsafe")
    generations.append_replay_snapshot("generation-a", "owner-a", "safe")

    tail = generations.get_replay_tail("generation-a", "owner-a", after_sequence=0)
    assert tail is not None
    assert tail["events"][1]["payload"] == {
        "content": "safe",
        "replace": True,
        "type": "content",
    }

    with generation_module.get_db() as db:
        row = db.get(ChatGenerationReplayEvent, ("generation-a", 2))
        row.payload_digest = "0" * 64
        db.commit()

    quarantined = generations.get_replay_tail(
        "generation-a", "owner-a", after_sequence=1
    )
    assert quarantined is not None
    assert quarantined["events"][0]["payload"] == {"type": "invalid"}

    monkeypatch.setattr(generation_module, "REPLAY_MAX_CONTENT_CHARS", 3)
    degraded = generations.append_replay_snapshot("generation-a", "owner-a", "four")
    assert degraded is not None and degraded.degraded is True
