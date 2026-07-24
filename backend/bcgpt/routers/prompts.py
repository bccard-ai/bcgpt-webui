"""Prompt template management endpoints – CRUD for slash-command prompts."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models.prompts import (
    PromptForm,
    PromptModel,
    PromptUserResponse,
    Prompts,
)
from bcgpt.utils import get_admin_user, get_verified_user, has_access, has_permission

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[PromptModel])
async def get_prompts(user=Depends(get_verified_user)):
    """List prompts readable by the current user.

    Admins see all prompts; non-admins see those with read access.
    """
    if user.role == "admin":
        return Prompts.get_prompts()
    return Prompts.get_prompts_by_user_id(user.id, "read")


@router.get("/list", response_model=list[PromptUserResponse])
async def get_prompt_list(user=Depends(get_verified_user)):
    """List prompts the user can edit (write access filter)."""
    if user.role == "admin":
        return Prompts.get_prompts()
    return Prompts.get_prompts_by_user_id(user.id, "write")


@router.post("/create", response_model=Optional[PromptModel])
async def create_new_prompt(
    request: Request, form_data: PromptForm, user=Depends(get_verified_user)
):
    """Create a new prompt template.

    Non-admin users need the ``workspace.prompts`` permission.
    """
    if user.role != "admin" and not has_permission(
        user.id, "workspace.prompts", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    prompt = Prompts.get_prompt_by_command(form_data.command)
    if prompt is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.COMMAND_TAKEN,
        )

    prompt = Prompts.insert_new_prompt(user.id, form_data)
    if prompt:
        return prompt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.DEFAULT(),
    )


@router.get("/command/{command}", response_model=Optional[PromptModel])
async def get_prompt_by_command(command: str, user=Depends(get_verified_user)):
    """Retrieve a prompt by its slash-command identifier."""
    prompt = Prompts.get_prompt_by_command(f"/{command}")
    if prompt:
        if (
            user.role == "admin"
            or prompt.user_id == user.id
            or has_access(user.id, "read", prompt.access_control)
        ):
            return prompt
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


@router.post("/command/{command}/update", response_model=Optional[PromptModel])
async def update_prompt_by_command(
    command: str,
    form_data: PromptForm,
    user=Depends(get_verified_user),
):
    """Update an existing prompt by its slash-command.

    Requires write access, ownership, or admin role.
    """
    prompt = Prompts.get_prompt_by_command(f"/{command}")
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        prompt.user_id != user.id
        and not has_access(user.id, "write", prompt.access_control)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    prompt = Prompts.update_prompt_by_command(f"/{command}", form_data)
    if prompt:
        return prompt
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
    )


@router.delete("/command/{command}/delete", response_model=bool)
async def delete_prompt_by_command(command: str, user=Depends(get_verified_user)):
    """Delete a prompt by its slash-command.

    Requires write access, ownership, or admin role.
    """
    prompt = Prompts.get_prompt_by_command(f"/{command}")
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        prompt.user_id != user.id
        and not has_access(user.id, "write", prompt.access_control)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    return Prompts.delete_prompt_by_command(f"/{command}")
