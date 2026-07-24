"""Owned background-task lifecycle management.

Chat streaming tasks are process-local, but they still need an authorization
boundary.  Each task is therefore bound to the authenticated user and, when
available, to the exact chat and assistant message that created it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Any, Dict, Literal, Optional, Tuple
from uuid import uuid4

TaskStatus = Literal["running", "completed", "stopped", "error"]

# Keep a short terminal receipt so a Stop request racing normal completion can
# distinguish "already completed" from an unknown or unauthorized task.
TERMINAL_TASK_TTL_SECONDS = 60.0


class TaskNotFoundError(ValueError):
    """Raised for both unknown tasks and tasks owned by another user."""


@dataclass
class TaskRecord:
    task: asyncio.Task
    owner_id: str
    chat_id: str | None
    message_id: str | None
    generation_id: str | None = None
    status: TaskStatus = "running"
    stop_requested: bool = False
    created_at: float = 0.0
    terminal_at: float | None = None


# Global dictionary mapping task IDs to owned task records.  Access remains on
# the application's asyncio event loop, so mutations are atomic between awaits.
tasks: Dict[str, TaskRecord] = {}
_generation_task_ids: Dict[str, str] = {}
_cleanup_handles: Dict[str, asyncio.TimerHandle] = {}


def cleanup_task(task_id: str, expected_task: asyncio.Task | None = None) -> None:
    """Remove a task record, optionally only when it still wraps *expected_task*."""

    record = tasks.get(task_id)
    if record is None or (
        expected_task is not None and record.task is not expected_task
    ):
        return

    tasks.pop(task_id, None)
    if (
        record.generation_id is not None
        and _generation_task_ids.get(record.generation_id) == task_id
    ):
        _generation_task_ids.pop(record.generation_id, None)
    handle = _cleanup_handles.pop(task_id, None)
    if handle is not None and not handle.cancelled():
        handle.cancel()


def _schedule_terminal_cleanup(task_id: str, task: asyncio.Task) -> None:
    old_handle = _cleanup_handles.pop(task_id, None)
    if old_handle is not None and not old_handle.cancelled():
        old_handle.cancel()

    loop = task.get_loop()
    if loop.is_closed():
        cleanup_task(task_id, task)
        return

    _cleanup_handles[task_id] = loop.call_later(
        TERMINAL_TASK_TTL_SECONDS,
        cleanup_task,
        task_id,
        task,
    )


def _mark_task_terminal(task_id: str, task: asyncio.Task) -> None:
    record = tasks.get(task_id)
    if record is None or record.task is not task:
        return

    if record.status == "running":
        if task.cancelled() or record.stop_requested:
            record.status = "stopped"
        else:
            # Calling exception() also retrieves it, avoiding an unobserved-task
            # warning for registry users whose coroutine does not catch errors.
            record.status = "error" if task.exception() is not None else "completed"
        record.terminal_at = monotonic()

    _schedule_terminal_cleanup(task_id, task)


def create_task(
    coroutine: Any,
    *,
    owner_id: str,
    chat_id: str | None = None,
    message_id: str | None = None,
    generation_id: str | None = None,
) -> Tuple[str, asyncio.Task]:
    """Create and register an authenticated, generation-specific task."""

    normalized_generation_id = str(generation_id) if generation_id is not None else None
    if normalized_generation_id is not None:
        existing_task_id = _generation_task_ids.get(normalized_generation_id)
        existing = tasks.get(existing_task_id) if existing_task_id else None
        if existing and existing.status == "running":
            close = getattr(coroutine, "close", None)
            if callable(close):
                close()
            raise ValueError(
                f"Generation {normalized_generation_id} already has a running task."
            )

    task_id = str(uuid4())
    task = asyncio.create_task(coroutine)
    tasks[task_id] = TaskRecord(
        task=task,
        owner_id=str(owner_id),
        chat_id=str(chat_id) if chat_id is not None else None,
        message_id=str(message_id) if message_id is not None else None,
        generation_id=normalized_generation_id,
        created_at=monotonic(),
    )
    if normalized_generation_id is not None:
        _generation_task_ids[normalized_generation_id] = task_id
    task.add_done_callback(lambda finished: _mark_task_terminal(task_id, finished))
    return task_id, task


def _get_owned_record(task_id: str, owner_id: str) -> TaskRecord:
    record = tasks.get(task_id)
    # Deliberately use the same error for missing and foreign-owned IDs so the
    # endpoint never becomes a task-existence oracle.
    if record is None or record.owner_id != str(owner_id):
        raise TaskNotFoundError(f"Task with ID {task_id} not found.")
    return record


def get_task(task_id: str, *, owner_id: str | None = None) -> Optional[asyncio.Task]:
    """Retrieve a task, optionally enforcing its owner boundary."""

    record = tasks.get(task_id)
    if record is None or (owner_id is not None and record.owner_id != str(owner_id)):
        return None
    return record.task


def list_tasks(owner_id: str) -> list[str]:
    """Return only running task IDs owned by the authenticated user."""

    normalized_owner_id = str(owner_id)
    return [
        task_id
        for task_id, record in tasks.items()
        if record.owner_id == normalized_owner_id and record.status == "running"
    ]


def get_task_id_by_generation(
    generation_id: str, *, owner_id: str | None = None
) -> str | None:
    """Resolve a live process-local task from its durable generation ID."""

    task_id = _generation_task_ids.get(str(generation_id))
    record = tasks.get(task_id) if task_id else None
    if record is None or record.status != "running":
        return None
    if owner_id is not None and record.owner_id != str(owner_id):
        return None
    return task_id


async def stop_generation(
    generation_id: str,
    *,
    owner_id: str,
    chat_id: str | None = None,
    message_id: str | None = None,
) -> Dict[str, Any] | None:
    """Stop the same-replica execution for an exact durable generation."""

    task_id = get_task_id_by_generation(generation_id, owner_id=owner_id)
    if task_id is None:
        return None
    return await stop_task(
        task_id,
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message_id,
    )


def _stop_receipt(
    task_id: str,
    record: TaskRecord,
    *,
    status: str,
    accepted: bool,
    observed: bool,
    terminal: bool,
    stopped: bool,
) -> Dict[str, Any]:
    return {
        "status": status,
        "accepted": accepted,
        "observed": observed,
        "terminal": terminal,
        "stopped": stopped,
        # This registry is process-local.  Never overstate its receipt as a
        # fleet-wide durable stop.
        "durable": False,
        "task_id": task_id,
        "generation_id": task_id,
        "chat_id": record.chat_id,
        "message_id": record.message_id,
    }


async def stop_task(
    task_id: str,
    *,
    owner_id: str,
    chat_id: str | None = None,
    message_id: str | None = None,
) -> Dict[str, Any]:
    """Stop an owned task only when any supplied generation bindings match."""

    record = _get_owned_record(task_id, owner_id)

    if (chat_id is not None and record.chat_id != str(chat_id)) or (
        message_id is not None and record.message_id != str(message_id)
    ):
        return _stop_receipt(
            task_id,
            record,
            status="different_generation",
            accepted=False,
            observed=False,
            terminal=False,
            stopped=False,
        )

    if record.status == "stopped":
        return _stop_receipt(
            task_id,
            record,
            status="already_terminal",
            accepted=True,
            observed=True,
            terminal=True,
            stopped=True,
        )

    if record.status != "running" or record.task.done():
        if record.status == "running":
            _mark_task_terminal(task_id, record.task)
        return _stop_receipt(
            task_id,
            record,
            status="already_completed",
            accepted=False,
            observed=False,
            terminal=True,
            stopped=False,
        )

    if not record.task.cancel():
        _mark_task_terminal(task_id, record.task)
        return _stop_receipt(
            task_id,
            record,
            status="already_completed",
            accepted=False,
            observed=False,
            terminal=True,
            stopped=False,
        )

    record.stop_requested = True
    try:
        await record.task
    except asyncio.CancelledError:
        record.status = "stopped"
        record.terminal_at = monotonic()
        _schedule_terminal_cleanup(task_id, record.task)
        return _stop_receipt(
            task_id,
            record,
            status="observed",
            accepted=True,
            observed=True,
            terminal=True,
            stopped=True,
        )
    except Exception:
        record.status = "error"
        record.terminal_at = monotonic()
        _schedule_terminal_cleanup(task_id, record.task)

    if record.stop_requested:
        record.status = "stopped"
        record.terminal_at = monotonic()
        _schedule_terminal_cleanup(task_id, record.task)
        return _stop_receipt(
            task_id,
            record,
            status="observed",
            accepted=True,
            observed=True,
            terminal=True,
            stopped=True,
        )

    return _stop_receipt(
        task_id,
        record,
        status="already_completed",
        accepted=False,
        observed=False,
        terminal=True,
        stopped=False,
    )
