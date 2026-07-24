"""Regression tests for streaming generation task binding."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.responses import StreamingResponse

from bcgpt.utils import middleware


async def _empty_stream():
    if False:
        yield b""


def test_streaming_task_binding_uses_generation_owner_and_terminalizes_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A binding failure must not mask itself with a NameError."""

    bind_calls: list[tuple[str, str, str]] = []
    terminal_calls: list[tuple[str, str]] = []

    def fail_bind(generation_id: str, user_id: str, task_id: str):
        bind_calls.append((generation_id, user_id, task_id))
        raise RuntimeError("database unavailable")

    def create_pending_task(coro, **_kwargs):
        coro.close()
        return "task-123", asyncio.create_task(asyncio.Event().wait())

    async def terminalize(status: str, reason: str) -> None:
        terminal_calls.append((status, reason))

    monkeypatch.setattr(middleware.ChatGenerations, "bind_task", fail_bind)
    monkeypatch.setattr(middleware, "create_task", create_pending_task)
    monkeypatch.setattr(
        middleware.Chats,
        "upsert_message_to_chat_by_id_and_message_id",
        lambda *_args, **_kwargs: None,
    )

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="database unavailable"):
            await middleware._handle_streaming_response(
                request=object(),
                response=StreamingResponse(
                    _empty_stream(), media_type="text/event-stream"
                ),
                form_data={"model": "test-model"},
                user=None,
                metadata={
                    "generation_id": "generation-1",
                    "user_id": "user-1",
                    "chat_id": "chat-1",
                    "message_id": "message-1",
                },
                model={},
                events=[],
                tasks=set(),
                event_emitter=lambda _event: None,
                event_caller=lambda _event: None,
                extra_params={},
                filter_functions=[],
                background_tasks_handler=lambda: None,
                terminalize_generation=terminalize,
            )

    asyncio.run(scenario())

    assert bind_calls == [("generation-1", "user-1", "task-123")]
    assert terminal_calls == [("error", "task_binding_error")]


def test_streaming_delivery_precedes_title_and_tag_background_tasks() -> None:
    """The UI must receive ``done`` before optional LLM follow-up work."""

    source = Path(middleware.__file__).read_text()
    streaming_start = source.index("async def _handle_streaming_response")
    finalisation_start = source.index("# --- Finalise ---", streaming_start)
    delivery = source.index("await _emit_completion(", finalisation_start)
    terminalize = source.index(
        'await terminalize_generation("completed", "provider_completed")', delivery
    )
    background = source.index("await background_tasks_handler()", finalisation_start)

    assert delivery < terminalize < background
