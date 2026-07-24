from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, String, Text, func

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class ApprovalTicket(Base):
    __tablename__ = "hitl_approval_ticket"

    id = Column(String, primary_key=True)
    scope = Column(String, nullable=False)
    action_class = Column(String, nullable=False)
    risk_tier = Column(String, nullable=False)
    tool_name = Column(String, nullable=True)
    node_id = Column(String, nullable=True)
    arguments = Column(JSON, nullable=True)
    user_id = Column(String, nullable=False, index=True)
    workflow_run_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(BigInteger, nullable=True)
    review_notes = Column(Text, nullable=True)
    sla_deadline = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class ApprovalTicketModel(BaseModel):
    id: str
    scope: str
    action_class: str
    risk_tier: str
    tool_name: Optional[str] = None
    node_id: Optional[str] = None
    arguments: Optional[dict] = None
    user_id: str
    workflow_run_id: Optional[str] = None
    status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[int] = None
    review_notes: Optional[str] = None
    sla_deadline: Optional[int] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequest(BaseModel):
    scope: str
    action_class: str
    risk_tier: str
    tool_name: Optional[str] = None
    node_id: Optional[str] = None
    arguments: Optional[dict] = None
    user_id: str
    workflow_run_id: Optional[str] = None
    sla_deadline: Optional[int] = None


class ApprovalTicketForm(ApprovalRequest):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


class ApprovalTicketsTable:
    def insert(self, form_data: ApprovalTicketForm) -> Optional[ApprovalTicketModel]:
        with get_db() as db:
            now = _now_ms()
            ticket = ApprovalTicketModel(
                **{
                    "id": str(uuid.uuid4()),
                    **form_data.model_dump(),
                    "status": "pending",
                    "created_at": now,
                }
            )
            try:
                result = ApprovalTicket(**ticket.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return ApprovalTicketModel.model_validate(result) if result else None
            except Exception as e:
                log.exception(f"Error creating approval ticket: {e}")
                return None

    def get_by_id(self, id: str) -> Optional[ApprovalTicketModel]:
        try:
            with get_db() as db:
                ticket = db.query(ApprovalTicket).filter_by(id=id).first()
                if not ticket:
                    return None
                return ApprovalTicketModel.model_validate(ticket)
        except Exception:
            return None

    def get_pending(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalTicketModel]:
        with get_db() as db:
            query = db.query(ApprovalTicket).filter_by(status="pending")
            if user_id:
                query = query.filter(ApprovalTicket.user_id == user_id)

            return [
                ApprovalTicketModel.model_validate(ticket)
                for ticket in query.order_by(ApprovalTicket.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def approve(
        self,
        id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[ApprovalTicketModel]:
        return self._review(id, "approved", reviewed_by, review_notes)

    def reject(
        self,
        id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[ApprovalTicketModel]:
        return self._review(id, "rejected", reviewed_by, review_notes)

    def expire(self, id: str) -> Optional[ApprovalTicketModel]:
        with get_db() as db:
            ticket = db.query(ApprovalTicket).filter_by(id=id).first()
            if not ticket:
                return None
            now = _now_ms()
            ticket.status = "expired"
            ticket.updated_at = now
            db.commit()
            db.refresh(ticket)
            return ApprovalTicketModel.model_validate(ticket)

    def get_expired(
        self,
        now_ms: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalTicketModel]:
        deadline = now_ms if now_ms is not None else _now_ms()
        with get_db() as db:
            return [
                ApprovalTicketModel.model_validate(ticket)
                for ticket in db.query(ApprovalTicket)
                .filter(
                    ApprovalTicket.status == "pending",
                    ApprovalTicket.sla_deadline.isnot(None),
                    ApprovalTicket.sla_deadline <= deadline,
                )
                .order_by(ApprovalTicket.sla_deadline.asc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def get_stats(self, user_id: Optional[str] = None) -> dict:
        with get_db() as db:
            query = db.query(ApprovalTicket)
            if user_id:
                query = query.filter(ApprovalTicket.user_id == user_id)

            tickets = query.all()
            by_status: dict[str, int] = {}
            by_risk_tier: dict[str, int] = {}
            total_review_time_ms = 0
            reviewed_count = 0

            for ticket in tickets:
                by_status[ticket.status] = by_status.get(ticket.status, 0) + 1
                by_risk_tier[ticket.risk_tier] = (
                    by_risk_tier.get(ticket.risk_tier, 0) + 1
                )
                if ticket.reviewed_at and ticket.created_at:
                    total_review_time_ms += ticket.reviewed_at - ticket.created_at
                    reviewed_count += 1

            return {
                "total": len(tickets),
                "pending": by_status.get("pending", 0),
                "approved": by_status.get("approved", 0),
                "rejected": by_status.get("rejected", 0),
                "expired": by_status.get("expired", 0),
                "cancelled": by_status.get("cancelled", 0),
                "by_status": by_status,
                "by_risk_tier": by_risk_tier,
                "avg_review_time_ms": (
                    total_review_time_ms / reviewed_count if reviewed_count else 0
                ),
            }

    def count_pending(self, user_id: Optional[str] = None) -> int:
        with get_db() as db:
            query = db.query(func.count(ApprovalTicket.id)).filter(
                ApprovalTicket.status == "pending"
            )
            if user_id:
                query = query.filter(ApprovalTicket.user_id == user_id)
            return query.scalar() or 0

    def _review(
        self,
        id: str,
        status: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[ApprovalTicketModel]:
        with get_db() as db:
            ticket = db.query(ApprovalTicket).filter_by(id=id).first()
            if not ticket:
                return None

            now = _now_ms()
            ticket.status = status
            ticket.reviewed_by = reviewed_by
            ticket.reviewed_at = now
            ticket.review_notes = review_notes
            ticket.updated_at = now
            db.commit()
            db.refresh(ticket)
            return ApprovalTicketModel.model_validate(ticket)


ApprovalTickets = ApprovalTicketsTable()
