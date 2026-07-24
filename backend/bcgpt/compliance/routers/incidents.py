from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.incident import AIIncidentForm, AIIncidents
from bcgpt.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


class IncidentStatusForm(BaseModel):
    status: str


class TimelineEventForm(BaseModel):
    event: str
    actor: Optional[str] = None


@router.post("")
async def create_incident(
    request: Request,
    form_data: AIIncidentForm,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIncidents.insert(form_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create AI incident")
    return result.model_dump()


@router.get("")
async def list_incidents(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
    severity: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    incidents = AIIncidents.get_all(status=status, severity=severity)
    return [incident.model_dump() for incident in incidents] if incidents else []


@router.get("/overdue")
async def get_overdue_incidents(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    incidents = AIIncidents.get_overdue()
    return [incident.model_dump() for incident in incidents] if incidents else []


@router.get("/stats")
async def get_incident_stats(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return AIIncidents.get_stats()


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIncidents.get_by_id(incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI incident not found")
    return result.model_dump()


@router.put("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: Request,
    form_data: IncidentStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIncidents.update_status(incident_id, form_data.status)
    if not result:
        raise HTTPException(status_code=404, detail="AI incident not found")
    return result.model_dump()


@router.post("/{incident_id}/timeline")
async def add_incident_timeline_event(
    incident_id: str,
    request: Request,
    form_data: TimelineEventForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIncidents.add_timeline_event(
        incident_id,
        event=form_data.event,
        actor=form_data.actor,
    )
    if not result:
        raise HTTPException(status_code=404, detail="AI incident not found")
    return result.model_dump()


@router.delete("/{incident_id}")
async def delete_incident(
    incident_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIncidents.delete_by_id(incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI incident not found")
    return {"success": True}
