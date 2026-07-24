from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from bcgpt.utils.auth import get_admin_user

from . import ApprovalGates
from .models import ApprovalTicketModel, ApprovalTickets
from .policy import ActionClass, RiskTier

router = APIRouter()


class ApprovalTicketListResponse(BaseModel):
    tickets: list[ApprovalTicketModel]
    total: int


class ApprovalReviewForm(BaseModel):
    review_notes: Optional[str] = None


class ApprovalRejectForm(BaseModel):
    reason: str


class HITLConfigForm(BaseModel):
    enabled: Optional[bool] = None
    sla_seconds: Optional[int] = Field(default=None, ge=1)
    matrix: Optional[dict[str, str]] = None


class HITLConfigResponse(BaseModel):
    enabled: bool
    sla_seconds: int


def _get_ticket_or_404(ticket_id: str) -> ApprovalTicketModel:
    ticket = ApprovalTickets.get_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Approval ticket not found")
    return ticket


def _is_admin(user) -> bool:
    return getattr(user, "role", None) == "admin"


def _require_reviewer_or_admin(ticket: ApprovalTicketModel, user) -> None:
    if _is_admin(user):
        return
    if ticket.reviewed_by and ticket.reviewed_by == getattr(user, "id", None):
        return
    raise HTTPException(status_code=403, detail="Not allowed to review this ticket")


def _coerce_matrix(
    matrix: Optional[dict[str, str]],
) -> Optional[dict[ActionClass, RiskTier]]:
    if not matrix:
        return None

    coerced: dict[ActionClass, RiskTier] = {}
    for action_class, risk_tier in matrix.items():
        try:
            coerced[ActionClass(action_class)] = RiskTier(risk_tier)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid HITL risk matrix entry: {action_class}={risk_tier}",
            ) from e
    return coerced


@router.get("/pending", response_model=ApprovalTicketListResponse)
async def get_pending_tickets(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(get_admin_user),
):
    tickets = ApprovalTickets.get_pending(user_id=user_id, limit=limit, offset=offset)
    return ApprovalTicketListResponse(
        tickets=tickets,
        total=ApprovalTickets.count_pending(user_id=user_id),
    )


@router.get("/stats")
async def get_approval_stats(
    user_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
):
    return ApprovalTickets.get_stats(user_id=user_id)


@router.post("/config", response_model=HITLConfigResponse)
async def update_hitl_config(form_data: HITLConfigForm, user=Depends(get_admin_user)):
    enabled = ApprovalGates.enabled if form_data.enabled is None else form_data.enabled
    sla_seconds = (
        ApprovalGates.sla_seconds
        if form_data.sla_seconds is None
        else form_data.sla_seconds
    )
    ApprovalGates.configure(
        enabled=enabled,
        sla_seconds=sla_seconds,
        matrix=_coerce_matrix(form_data.matrix),
    )
    return HITLConfigResponse(
        enabled=ApprovalGates.enabled, sla_seconds=ApprovalGates.sla_seconds
    )


@router.get("/{ticket_id}", response_model=ApprovalTicketModel)
async def get_approval_ticket(ticket_id: str, user=Depends(get_admin_user)):
    return _get_ticket_or_404(ticket_id)


@router.post("/{ticket_id}/approve", response_model=ApprovalTicketModel)
async def approve_ticket(
    ticket_id: str,
    form_data: ApprovalReviewForm = ApprovalReviewForm(),
    user=Depends(get_admin_user),
):
    ticket = _get_ticket_or_404(ticket_id)
    if ticket.status != "pending":
        raise HTTPException(
            status_code=409, detail="Only pending tickets can be approved"
        )

    updated = ApprovalTickets.approve(
        ticket_id,
        reviewed_by=user.id,
        review_notes=form_data.review_notes,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to approve ticket")
    return updated


@router.post("/{ticket_id}/reject", response_model=ApprovalTicketModel)
async def reject_ticket(
    ticket_id: str,
    form_data: ApprovalRejectForm,
    user=Depends(get_admin_user),
):
    ticket = _get_ticket_or_404(ticket_id)
    if ticket.status != "pending":
        raise HTTPException(
            status_code=409, detail="Only pending tickets can be rejected"
        )

    updated = ApprovalTickets.reject(
        ticket_id,
        reviewed_by=user.id,
        review_notes=form_data.reason,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to reject ticket")
    return updated
