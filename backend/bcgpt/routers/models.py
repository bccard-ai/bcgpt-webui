"""Model registry endpoints – CRUD for custom model definitions."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models.models import (
    ModelForm,
    ModelModel,
    ModelResponse,
    ModelUserResponse,
    Models,
)
from bcgpt.utils import get_admin_user, get_verified_user, has_access, has_permission

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ModelUserResponse])
async def get_models(id: Optional[str] = None, user=Depends(get_verified_user)):
    """List models visible to the current user.

    Admins see every model; non-admins see only their own.
    """
    if user.role == "admin":
        return Models.get_models()
    return Models.get_models_by_user_id(user.id)


@router.get("/base", response_model=list[ModelResponse])
async def get_base_models(user=Depends(get_admin_user)):
    """List all base (non-custom) models (admin-only)."""
    return Models.get_base_models()


def _assert_non_admin_model_form(form_data: ModelForm, user) -> None:
    """Limits on what a non-admin may put in a custom model definition.

    * A model without ``base_model_id`` overrides the matching base model for
      every user (see ``utils.models._apply_base_model_override``) -- admin only.
    * Knowledge attached to a model is injected for every chat with it without a
      per-user ACL check, so the author must be able to read all of it.
    """
    if user.role == "admin":
        return
    if not form_data.base_model_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can override base models",
        )

    from bcgpt.models.files import Files
    from bcgpt.retrieval.lifecycle import check_collection_access

    meta = form_data.meta.model_dump() if form_data.meta else {}
    for item in meta.get("knowledge") or []:
        if not isinstance(item, dict):
            continue
        names = list(item.get("collection_names") or [])
        if item.get("collection_name"):
            names.append(item["collection_name"])
        if item.get("type") == "collection" and item.get("id"):
            names.append(item["id"])
        for name in names:
            check_collection_access(str(name), user)
        if item.get("type") == "file" and item.get("id"):
            file = Files.get_file_by_id(item["id"])
            if file is None:
                continue
            if file.user_id != user.id:
                kb_id = (file.meta or {}).get("collection_name")
                if not kb_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
                    )
                check_collection_access(kb_id, user)


@router.post("/create", response_model=Optional[ModelModel])
async def create_new_model(
    request: Request,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    """Register a new custom model definition.

    Non-admin users need the ``workspace.models`` permission.
    """
    if user.role != "admin" and not has_permission(
        user.id, "workspace.models", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.get_model_by_id(form_data.id)
    if model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.MODEL_ID_TAKEN,
        )
    _assert_non_admin_model_form(form_data, user)

    model = Models.insert_new_model(form_data, user.id)
    if model:
        return model
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.DEFAULT(),
    )


@router.get("/model", response_model=Optional[ModelResponse])
async def get_model_by_id(id: str, user=Depends(get_verified_user)):
    """Fetch a single model by ID.

    The caller must be the owner, an admin, or have read access.
    """
    model = Models.get_model_by_id(id)
    if model:
        if (
            user.role == "admin"
            or model.user_id == user.id
            or has_access(user.id, "read", model.access_control)
        ):
            return model
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


@router.post("/model/toggle", response_model=Optional[ModelResponse])
async def toggle_model_by_id(id: str, user=Depends(get_verified_user)):
    """Toggle a model between enabled/disabled states.

    Requires write access or admin/owner status.
    """
    model = Models.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if not (
        user.role == "admin"
        or model.user_id == user.id
        or has_access(user.id, "write", model.access_control)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.toggle_model_by_id(id)
    if model:
        return model
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
    )


@router.post("/model/update", response_model=Optional[ModelModel])
async def update_model_by_id(
    id: str,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    """Update an existing model definition.

    Requires write access, ownership, or admin role.
    """
    model = Models.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    _assert_non_admin_model_form(form_data, user)

    model = Models.update_model_by_id(id, form_data)
    return model


@router.delete("/model/delete", response_model=bool)
async def delete_model_by_id(id: str, user=Depends(get_verified_user)):
    """Delete a custom model definition.

    Requires write access, ownership, or admin role.
    """
    model = Models.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        user.role != "admin"
        and model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    return Models.delete_model_by_id(id)


@router.delete("/delete/all", response_model=bool)
async def delete_all_models(user=Depends(get_admin_user)):
    """Delete **all** custom model definitions (admin-only)."""
    return Models.delete_all_models()
