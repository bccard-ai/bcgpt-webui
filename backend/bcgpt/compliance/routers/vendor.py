from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.vendor import AIVendorForm, AIVendors
from bcgpt.utils.auth import get_admin_user

router = APIRouter()


class VendorStatusForm(BaseModel):
    status: str


@router.post("")
async def create_vendor(
    request: Request,
    form_data: AIVendorForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIVendors.insert(form_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create AI vendor")
    return result.model_dump()


@router.get("")
async def list_vendors(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    vendors = AIVendors.get_all(status=status)
    return [vendor.model_dump() for vendor in vendors] if vendors else []


@router.get("/{vendor_id}")
async def get_vendor(
    vendor_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIVendors.get_by_id(vendor_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI vendor not found")
    return result.model_dump()


@router.put("/{vendor_id}")
async def update_vendor(
    vendor_id: str,
    request: Request,
    form_data: AIVendorForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIVendors.update(vendor_id, form_data)
    if not result:
        raise HTTPException(status_code=404, detail="AI vendor not found")
    return result.model_dump()


@router.put("/{vendor_id}/status")
async def update_vendor_status(
    vendor_id: str,
    request: Request,
    form_data: VendorStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIVendors.update_status(vendor_id, form_data.status)
    if not result:
        raise HTTPException(status_code=404, detail="AI vendor not found")
    return result.model_dump()


@router.delete("/{vendor_id}")
async def delete_vendor(
    vendor_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIVendors.delete_by_id(vendor_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI vendor not found")
    return {"success": True}
