from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.ai_inventory import (
    AIModelInventories,
    AIModelInventoryForm,
)
from bcgpt.utils.auth import get_admin_user

router = APIRouter()


class InventoryStatusForm(BaseModel):
    status: str


@router.post("")
async def create_inventory_item(
    request: Request,
    form_data: AIModelInventoryForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIModelInventories.insert(form_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create inventory item")
    return result.model_dump()


@router.get("")
async def list_inventory_items(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    items = AIModelInventories.get_all(status=status)
    return [item.model_dump() for item in items] if items else []


@router.get("/stats")
async def get_inventory_stats(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    items = AIModelInventories.get_all()
    by_risk_tier: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for item in items or []:
        risk_tier = item.risk_tier or "unknown"
        status = item.validation_status or "unknown"
        by_risk_tier[risk_tier] = by_risk_tier.get(risk_tier, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "total": len(items or []),
        "by_risk_tier": by_risk_tier,
        "by_status": by_status,
    }


@router.get("/{item_id}")
async def get_inventory_item(
    item_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIModelInventories.get_by_id(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return result.model_dump()


@router.put("/{item_id}")
async def update_inventory_item(
    item_id: str,
    request: Request,
    form_data: AIModelInventoryForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIModelInventories.update(item_id, form_data)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return result.model_dump()


@router.put("/{item_id}/status")
async def update_inventory_status(
    item_id: str,
    request: Request,
    form_data: InventoryStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIModelInventories.update_status(item_id, form_data.status)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return result.model_dump()


@router.delete("/{item_id}")
async def delete_inventory_item(
    item_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIModelInventories.delete_by_id(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return {"success": True}
