from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.dsar import AIDSARRequestForm, AIDSARRequests
from bcgpt.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


class DSARActionForm(BaseModel):
    details: Optional[dict[str, object]] = None


class DSARStatusForm(BaseModel):
    status: str


def _create_dsar_request(request_type: str, form_data: DSARActionForm, user):
    dsar_form = AIDSARRequestForm(
        request_type=request_type,
        user_id=user.id,
        details=form_data.details,
    )
    result = AIDSARRequests.insert(dsar_form)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create DSAR request")
    return result.model_dump()


@router.post("/export")
async def request_data_export(
    request: Request,
    form_data: DSARActionForm,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return _create_dsar_request("export", form_data, user)


@router.post("/erase")
async def request_data_erasure(
    request: Request,
    form_data: DSARActionForm,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return _create_dsar_request("erase", form_data, user)


@router.post("/explain")
async def request_automated_decision_explanation(
    request: Request,
    form_data: DSARActionForm,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return _create_dsar_request("explain", form_data, user)


@router.post("/object")
async def object_to_automated_decision(
    request: Request,
    form_data: DSARActionForm,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return _create_dsar_request("object", form_data, user)


@router.get("/my-requests")
async def get_my_dsar_requests(
    request: Request,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    requests = AIDSARRequests.get_by_user_id(user.id)
    return [dsar_request.model_dump() for dsar_request in requests] if requests else []


@router.get("")
async def list_dsar_requests(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    requests = AIDSARRequests.get_all(status=status)
    return [dsar_request.model_dump() for dsar_request in requests] if requests else []


@router.get("/{request_id}")
async def get_dsar_request(
    request_id: str,
    request: Request,
    user=Depends(get_verified_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIDSARRequests.get_by_id(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    if user.role != "admin" and result.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access DSAR request",
        )
    return result.model_dump()


@router.put("/{request_id}/status")
async def update_dsar_request_status(
    request_id: str,
    request: Request,
    form_data: DSARStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIDSARRequests.update_status(request_id, form_data.status)
    if not result:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    return result.model_dump()


@router.delete("/{request_id}")
async def delete_dsar_request(
    request_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIDSARRequests.delete_by_id(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    return {"success": True}
