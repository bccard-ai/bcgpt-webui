from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from .models import ApprovalTicketForm, ApprovalTickets
from .policy import RiskPolicy

log = logging.getLogger(__name__)


class ApprovalDecision(dict):
    """Dict subclass with .approved and .reason properties."""

    @property
    def approved(self) -> bool:
        return self.get("approved", False)

    @property
    def reason(self) -> str:
        return self.get("reason", "")


class ApprovalGate:
    """
    Async-compatible approval gate for the DAG workflow engine and tool loop.

    When HITL is disabled (default), all actions are auto-approved.
    When enabled, high/critical-risk actions create an ApprovalTicket and
    wait for human review (with SLA timeout).
    """

    def __init__(self):
        self.policy = RiskPolicy()
        self._enabled = False
        self._sla_seconds = 300  # 5 minutes default SLA
        self._poll_interval = 2.0  # poll every 2 seconds

    def configure(self, enabled: bool = False, sla_seconds: int = 300, matrix=None):
        self._enabled = enabled
        self._sla_seconds = sla_seconds
        if matrix:
            self.policy = RiskPolicy(matrix=matrix)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def sla_seconds(self) -> int:
        return self._sla_seconds

    async def __call__(self, payload: dict) -> dict:
        """Callable adapter for use as ExecutionContext.approval_gate."""
        return await self.check(
            user_id=payload.get("user_id", ""),
            scope=payload.get("scope", "unknown"),
            tool_name=payload.get("tool_name", ""),
            node_type=payload.get("node_type", ""),
            arguments=payload.get("arguments"),
            workflow_run_id=payload.get("workflow_run_id", ""),
        )

    async def check(
        self,
        *,
        user_id: str,
        scope: str,
        tool_name: str = "",
        node_id: str = "",
        node_type: str = "",
        arguments: Optional[dict] = None,
        workflow_run_id: str = "",
    ) -> ApprovalDecision:
        if not self._enabled:
            return ApprovalDecision(approved=True, reason="HITL disabled")

        action_class = self.policy.guess_action_class(tool_name, node_type)
        decision = self.policy.evaluate(action_class)

        if not decision.requires_approval:
            return ApprovalDecision(
                approved=True,
                reason=decision.reason,
                tier=decision.tier.value,
            )

        # Create approval ticket
        sla_deadline = int((time.time() + self._sla_seconds) * 1000)
        ticket = ApprovalTickets.insert(
            ApprovalTicketForm(
                scope=scope,
                action_class=action_class.value,
                risk_tier=decision.tier.value,
                tool_name=tool_name or None,
                node_id=node_id or None,
                arguments=arguments or {},
                user_id=user_id,
                workflow_run_id=workflow_run_id or None,
                sla_deadline=sla_deadline,
            )
        )

        if not ticket:
            # DB failure — fail-safe: deny
            return ApprovalDecision(
                approved=False,
                reason="Failed to create approval ticket (fail-safe deny)",
            )

        # Wait for approval (poll-based; production should use WebSocket/SSE)
        deadline = time.monotonic() + self._sla_seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            await asyncio.sleep(min(self._poll_interval, remaining))

            updated = ApprovalTickets.get_by_id(ticket.id)
            if not updated:
                return ApprovalDecision(
                    approved=False,
                    reason="Approval ticket disappeared",
                    ticket_id=ticket.id,
                )

            if updated.status == "approved":
                return ApprovalDecision(
                    approved=True,
                    reason="Approved by reviewer",
                    ticket_id=ticket.id,
                    reviewer=updated.reviewed_by,
                )
            if updated.status == "rejected":
                return ApprovalDecision(
                    approved=False,
                    reason=f"Rejected: {updated.review_notes or 'no reason given'}",
                    ticket_id=ticket.id,
                    reviewer=updated.reviewed_by,
                )
            if updated.status == "expired":
                return ApprovalDecision(
                    approved=False,
                    reason="SLA expired",
                    ticket_id=ticket.id,
                )

        # SLA expired — mark ticket expired
        try:
            ApprovalTickets.expire(ticket.id)
        except Exception as e:  # noqa: BLE001
            log.exception("Failed to expire approval ticket %s: %s", ticket.id, e)
        return ApprovalDecision(
            approved=False,
            reason="SLA timeout — ticket expired",
            ticket_id=ticket.id,
        )
