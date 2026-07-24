from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.aiia import AIIARecordForm, AIIARecords
from bcgpt.utils.auth import get_admin_user

router = APIRouter()


class AIIAStatusForm(BaseModel):
    status: str


@router.post("")
async def create_aiia_record(
    request: Request,
    form_data: AIIARecordForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIARecords.insert(form_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create AIIA record")
    return result.model_dump()


@router.get("")
async def list_aiia_records(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    records = AIIARecords.get_all(status=status)
    return [record.model_dump() for record in records] if records else []


@router.get("/inventory/{inventory_id}")
async def get_aiia_for_inventory(
    inventory_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    records = AIIARecords.get_by_inventory_id(inventory_id)
    return [record.model_dump() for record in records] if records else []


@router.get("/expired")
async def get_expired_aiias(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    records = AIIARecords.get_expired()
    return [record.model_dump() for record in records] if records else []


@router.get("/{record_id}")
async def get_aiia_record(
    record_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIARecords.get_by_id(record_id)
    if not result:
        raise HTTPException(status_code=404, detail="AIIA record not found")
    return result.model_dump()


@router.put("/{record_id}/status")
async def update_aiia_status(
    record_id: str,
    request: Request,
    form_data: AIIAStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    approved_by = user.id if form_data.status == "approved" else None
    result = AIIARecords.update_status(
        record_id, form_data.status, approved_by=approved_by
    )
    if not result:
        raise HTTPException(status_code=404, detail="AIIA record not found")
    return result.model_dump()


@router.delete("/{record_id}")
async def delete_aiia_record(
    record_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIIARecords.delete_by_id(record_id)
    if not result:
        raise HTTPException(status_code=404, detail="AIIA record not found")
    return {"success": True}
