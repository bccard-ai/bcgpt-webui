"""User group management endpoints (admin-only for mutations)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Users
from bcgpt.models.groups import GroupForm, GroupResponse, GroupUpdateForm, Groups
from bcgpt.utils import get_admin_user, get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[GroupResponse])
async def get_groups(user=Depends(get_verified_user)):
    """List groups visible to the current user.

    Admins see all groups; regular users see only groups they belong to.
    """
    if user.role == "admin":
        return Groups.get_groups()
    return Groups.get_groups_by_member_id(user.id)


@router.post("/create", response_model=Optional[GroupResponse])
async def create_new_group(form_data: GroupForm, user=Depends(get_admin_user)):
    """Create a new user group (admin-only)."""
    try:
        group = Groups.insert_new_group(user.id, form_data)
        if group:
            return group
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error creating group"),
        )
    except Exception as exc:
        log.exception("Error creating a new group: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.get("/id/{id}", response_model=Optional[GroupResponse])
async def get_group_by_id(id: str, user=Depends(get_admin_user)):
    """Retrieve a single group by its ID (admin-only)."""
    group = Groups.get_group_by_id(id)
    if group:
        return group
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


@router.post("/id/{id}/update", response_model=Optional[GroupResponse])
async def update_group_by_id(
    id: str, form_data: GroupUpdateForm, user=Depends(get_admin_user)
):
    """Update group membership and settings (admin-only)."""
    try:
        if form_data.user_ids:
            form_data.user_ids = Users.get_valid_user_ids(form_data.user_ids)

        group = Groups.update_group_by_id(id, form_data)
        if group:
            return group
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating group"),
        )
    except Exception as exc:
        log.exception("Error updating group %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.delete("/id/{id}/delete", response_model=bool)
async def delete_group_by_id(id: str, user=Depends(get_admin_user)):
    """Permanently delete a group (admin-only)."""
    try:
        result = Groups.delete_group_by_id(id)
        if result:
            return result
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting group"),
        )
    except Exception as exc:
        log.exception("Error deleting group %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )
