"""Security and generation-fencing tests for the chat task registry."""

from __future__ import annotations

import asyncio

import pytest

from bcgpt.tasks import (
    TaskNotFoundError,
    cleanup_task,
    create_task,
    get_task,
    get_task_id_by_generation,
    list_tasks,
    stop_generation,
    stop_task,
)


async def _wait_forever() -> None:
    await asyncio.Event().wait()


def test_task_owner_and_generation_bindings_are_enforced() -> None:
    async def scenario() -> None:
        task_id, task = create_task(
            _wait_forever(),
            owner_id="owner-a",
            chat_id="chat-a",
            message_id="message-a",
            generation_id="generation-a",
        )
        try:
            assert list_tasks("owner-a") == [task_id]
            assert list_tasks("owner-b") == []
            assert get_task(task_id, owner_id="owner-a") is task
            assert get_task(task_id, owner_id="owner-b") is None
            assert (
                get_task_id_by_generation("generation-a", owner_id="owner-a") == task_id
            )
            assert get_task_id_by_generation("generation-a", owner_id="owner-b") is None

            with pytest.raises(TaskNotFoundError):
                await stop_task(task_id, owner_id="owner-b")
            assert not task.done()

            mismatch = await stop_task(
                task_id,
                owner_id="owner-a",
                chat_id="chat-a",
                message_id="message-b",
            )
            assert mismatch["status"] == "different_generation"
            assert mismatch["accepted"] is False
            assert not task.done()

            receipt = await stop_generation(
                "generation-a",
                owner_id="owner-a",
                chat_id="chat-a",
                message_id="message-a",
            )
            assert receipt is not None
            assert receipt["status"] == "observed"
            assert receipt["stopped"] is True
            assert receipt["terminal"] is True
            assert receipt["durable"] is False
            assert get_task_id_by_generation("generation-a") is None

            replayed = await stop_task(task_id, owner_id="owner-a")
            assert replayed["status"] == "already_terminal"
            assert replayed["stopped"] is True
        finally:
            cleanup_task(task_id, task)

    asyncio.run(scenario())


def test_completed_task_retains_a_bounded_terminal_receipt() -> None:
    async def scenario() -> None:
        async def complete() -> str:
            return "done"

        task_id, task = create_task(
            complete(),
            owner_id="owner-a",
            chat_id="chat-a",
            message_id="message-a",
        )
        try:
            assert await task == "done"
            # Let asyncio run the registry's done callback.
            await asyncio.sleep(0)

            assert list_tasks("owner-a") == []
            receipt = await stop_task(
                task_id,
                owner_id="owner-a",
                chat_id="chat-a",
                message_id="message-a",
            )
            assert receipt["status"] == "already_completed"
            assert receipt["terminal"] is True
            assert receipt["stopped"] is False
        finally:
            cleanup_task(task_id, task)

    asyncio.run(scenario())


def test_stop_is_observed_when_handler_consumes_cancellation() -> None:
    async def scenario() -> None:
        async def consume_cancellation() -> str:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "terminal event emitted"

        task_id, task = create_task(
            consume_cancellation(),
            owner_id="owner-a",
            chat_id="chat-a",
            message_id="message-a",
        )
        try:
            receipt = await stop_task(
                task_id,
                owner_id="owner-a",
                chat_id="chat-a",
                message_id="message-a",
            )
            assert receipt["status"] == "observed"
            assert receipt["stopped"] is True

            replayed = await stop_task(task_id, owner_id="owner-a")
            assert replayed["status"] == "already_terminal"
        finally:
            cleanup_task(task_id, task)

    asyncio.run(scenario())
