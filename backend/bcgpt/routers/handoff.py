import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from bcgpt.models import HandoffRequests, HandoffRequestForm, HandoffStatusUpdateForm
from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.utils.handoff_notifications import HandoffNotifier
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


def _get_config_value(val):
    from bcgpt.config import PersistentConfig

    if isinstance(val, PersistentConfig):
        return val.value
    return val


class HandoffCreateForm(BaseModel):
    chat_id: str
    message_id: str
    reason: Optional[str] = None
    chat_snapshot: Optional[dict] = None


class HandoffConfigForm(BaseModel):
    enabled: bool
    email_enabled: bool
    email_recipients: str
    webhook_enabled: bool
    webhook_url: str


@router.post("")
async def create_handoff_request(
    request: Request, form_data: HandoffCreateForm, user=Depends(get_verified_user)
):
    config = request.app.state.config

    if not _get_config_value(config.HANDOFF_ENABLED):
        raise HTTPException(status_code=403, detail="Handoff feature is disabled")

    handoff_form = HandoffRequestForm(
        chat_id=form_data.chat_id,
        message_id=form_data.message_id,
        reason=form_data.reason,
        chat_snapshot=form_data.chat_snapshot,
    )

    result = HandoffRequests.insert_new_request(user.id, handoff_form)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create handoff request")

    notifier = HandoffNotifier(config)
    request_data = result.model_dump()

    try:
        await notifier.notify(request_data)
    except Exception as e:
        log.error(f"Handoff notification error: {e}")

    try:
        from bcgpt.socket.main import sio

        await sio.emit(
            "handoff:request",
            request_data,
        )
    except Exception as e:
        log.error(f"Handoff socket notification error: {e}")

    return result.model_dump()


@router.get("")
async def list_handoff_requests(
    request: Request,
    user=Depends(get_verified_user),
    limit: int = 50,
    offset: int = 0,
):
    if user.role == "admin":
        results = HandoffRequests.get_all_requests(limit=limit, offset=offset)
    else:
        results = HandoffRequests.get_requests_by_user_id(
            user.id, limit=limit, offset=offset
        )
    return [r.model_dump() for r in results]


@router.get("/pending")
async def list_pending_requests(
    request: Request, user=Depends(get_admin_user), limit: int = 50, offset: int = 0
):
    results = HandoffRequests.get_pending_requests(limit=limit, offset=offset)
    return [r.model_dump() for r in results]


@router.get("/stats")
async def get_handoff_stats(request: Request, user=Depends(get_admin_user)):
    return HandoffRequests.get_handoff_stats()


@router.get("/config")
async def get_handoff_config(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    return {
        "enabled": _get_config_value(config.HANDOFF_ENABLED),
        "email_enabled": _get_config_value(config.HANDOFF_EMAIL_ENABLED),
        "email_recipients": _get_config_value(config.HANDOFF_EMAIL_RECIPIENTS),
        "webhook_enabled": _get_config_value(config.HANDOFF_WEBHOOK_ENABLED),
        "webhook_url": _get_config_value(config.HANDOFF_WEBHOOK_URL),
    }


@router.post("/config/update")
async def update_handoff_config(
    request: Request, form_data: HandoffConfigForm, user=Depends(get_admin_user)
):
    config = request.app.state.config

    config.HANDOFF_ENABLED = form_data.enabled
    config.HANDOFF_EMAIL_ENABLED = form_data.email_enabled
    config.HANDOFF_EMAIL_RECIPIENTS = form_data.email_recipients
    config.HANDOFF_WEBHOOK_ENABLED = form_data.webhook_enabled
    config.HANDOFF_WEBHOOK_URL = form_data.webhook_url

    return {
        "enabled": _get_config_value(config.HANDOFF_ENABLED),
        "email_enabled": _get_config_value(config.HANDOFF_EMAIL_ENABLED),
        "email_recipients": _get_config_value(config.HANDOFF_EMAIL_RECIPIENTS),
        "webhook_enabled": _get_config_value(config.HANDOFF_WEBHOOK_ENABLED),
        "webhook_url": _get_config_value(config.HANDOFF_WEBHOOK_URL),
    }


@router.post("/{request_id}/accept")
async def accept_handoff_request(
    request: Request, request_id: str, user=Depends(get_admin_user)
):
    result = HandoffRequests.update_request_status(
        request_id, "accepted", assigned_to=user.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Handoff request not found")
    return result.model_dump()


@router.post("/{request_id}/resolve")
async def resolve_handoff_request(
    request: Request, request_id: str, user=Depends(get_admin_user)
):
    result = HandoffRequests.update_request_status(request_id, "resolved")
    if not result:
        raise HTTPException(status_code=404, detail="Handoff request not found")
    return result.model_dump()


@router.post("/{request_id}/dismiss")
async def dismiss_handoff_request(
    request: Request, request_id: str, user=Depends(get_admin_user)
):
    result = HandoffRequests.update_request_status(request_id, "dismissed")
    if not result:
        raise HTTPException(status_code=404, detail="Handoff request not found")
    return result.model_dump()
