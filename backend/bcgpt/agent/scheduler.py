"""Scheduled/background agent execution via APScheduler.

Wires APScheduler's AsyncIOScheduler into the application lifespan so that
agent definitions can be executed on cron schedules without manual invocation.

Schedule storage uses the existing AgentDefinition table's ``meta.schedule``
field (a cron expression string). When empty or absent the agent is not
scheduled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from fastapi import FastAPI

log = logging.getLogger(__name__)

_SCHEDULER: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Return the global scheduler instance, or ``None`` if not started."""
    return _SCHEDULER


async def start_scheduler(app: FastAPI) -> None:
    """Start the global AsyncIOScheduler and register all scheduled agents.

    Called from the FastAPI lifespan. Idempotent: if a scheduler is already
    running this is a no-op.
    """
    global _SCHEDULER

    if _SCHEDULER is not None and _SCHEDULER.running:
        log.debug("Agent scheduler already running")
        return

    _SCHEDULER = AsyncIOScheduler(timezone="UTC")
    _SCHEDULER.start()
    log.info("Agent scheduler started")

    await _register_all_scheduled_agents(app)


async def shutdown_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _SCHEDULER
    if _SCHEDULER is not None and _SCHEDULER.running:
        _SCHEDULER.shutdown(wait=False)
        log.info("Agent scheduler stopped")
    _SCHEDULER = None


async def _register_all_scheduled_agents(app: FastAPI) -> None:
    """Scan agent definitions for cron schedules and register them."""
    if _SCHEDULER is None:
        return

    try:
        from bcgpt.agent.definitions.agent_definition import (
            load_all_agent_definitions,
        )

        definitions = load_all_agent_definitions()
    except Exception as exc:
        log.warning("Could not load agent definitions for scheduling: %s", exc)
        return

    count = 0
    for definition in definitions:
        cron_expr = _extract_cron(definition)
        if not cron_expr:
            continue
        agent_id = getattr(definition, "id", None) or str(id(definition))
        _add_schedule(_SCHEDULER, agent_id, cron_expr)
        count += 1

    if count:
        log.info("Registered %d scheduled agent(s)", count)


def _extract_cron(definition: Any) -> str | None:
    """Extract a cron expression from an agent definition's meta."""
    meta = getattr(definition, "meta", None) or {}
    schedule = meta.get("schedule")
    if isinstance(schedule, str) and schedule.strip():
        return schedule.strip()
    return None


def _add_schedule(
    scheduler: AsyncIOScheduler, agent_id: str, cron_expr: str
) -> None:
    """Register a single agent execution job."""
    job_id = f"agent_schedule_{agent_id}"
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
    except ValueError as exc:
        log.warning("Invalid cron '%s' for agent %s: %s", cron_expr, agent_id, exc)
        return

    scheduler.add_job(
        _execute_scheduled_agent,
        trigger=trigger,
        args=[agent_id],
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Scheduled agent %s with cron '%s'", agent_id, cron_expr)


def schedule_agent(agent_id: str, cron_expr: str) -> bool:
    """Register or update a schedule for the given agent.

    Returns ``True`` on success, ``False`` if the scheduler is not running or
    the cron expression is invalid.
    """
    if _SCHEDULER is None or not _SCHEDULER.running:
        log.warning("Scheduler not running; cannot schedule agent %s", agent_id)
        return False
    _add_schedule(_SCHEDULER, agent_id, cron_expr)
    return True


def unschedule_agent(agent_id: str) -> None:
    """Remove an agent's schedule if it exists."""
    if _SCHEDULER is None:
        return
    job_id = f"agent_schedule_{agent_id}"
    try:
        _SCHEDULER.remove_job(job_id)
        log.info("Unscheduled agent %s", agent_id)
    except Exception:
        pass


async def _execute_scheduled_agent(agent_id: str) -> None:
    """Job body: load an agent definition and execute its workflow."""
    log.info("Executing scheduled agent: %s", agent_id)
    try:
        from bcgpt.agent.definitions.agent_definition import (
            load_agent_definition,
        )
        from bcgpt.agent.workflow.engine import WorkflowEngine

        definition = load_agent_definition(agent_id)
        if definition is None:
            log.warning("Scheduled agent %s not found, removing job", agent_id)
            unschedule_agent(agent_id)
            return

        workflow = getattr(definition, "workflow", None)
        if not workflow:
            log.warning("Scheduled agent %s has no workflow", agent_id)
            return

        engine = WorkflowEngine()
        await engine.execute(
            workflow=workflow,
            inputs={},
            context={"agent_id": agent_id, "scheduled": True},
        )
        log.info("Scheduled agent %s execution complete", agent_id)
    except Exception as exc:
        log.error("Scheduled agent %s execution failed: %s", agent_id, exc)
