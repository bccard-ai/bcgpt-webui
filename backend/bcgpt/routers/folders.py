"""Folder management endpoints – CRUD operations on user chat folders."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.config import UPLOAD_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Chats
from bcgpt.models.folders import FolderForm, FolderModel, Folders
from bcgpt.utils import get_verified_user, has_permission

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas (local to this router)
# ---------------------------------------------------------------------------


class FolderParentIdForm(BaseModel):
    """Payload for moving a folder under a new parent."""

    parent_id: Optional[str] = None


class FolderIsExpandedForm(BaseModel):
    """Payload for toggling a folder's expanded UI state."""

    is_expanded: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[FolderModel])
async def get_folders(user=Depends(get_verified_user)):
    """List all folders for the authenticated user, including their child chats."""
    folders = Folders.get_folders_by_user_id(user.id)
    return [
        {
            **folder.model_dump(),
            "items": {
                "chats": [
                    {"title": chat.title, "id": chat.id}
                    for chat in Chats.get_chats_by_folder_id_and_user_id(
                        folder.id, user.id
                    )
                ]
            },
        }
        for folder in folders
    ]


@router.post("/")
async def create_folder(form_data: FolderForm, user=Depends(get_verified_user)):
    """Create a new top-level folder for the authenticated user."""
    folder = await asyncio.to_thread(
        Folders.get_folder_by_parent_id_and_user_id_and_name,
        None,
        user.id,
        form_data.name,
    )
    if folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
        )

    try:
        folder = await asyncio.to_thread(
            Folders.insert_new_folder, user.id, form_data.name
        )
        return folder
    except Exception as exc:
        log.exception("%s", exc)
        log.error("Error creating folder")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error creating folder"),
        )


@router.get("/{id}", response_model=Optional[FolderModel])
async def get_folder_by_id(id: str, user=Depends(get_verified_user)):
    """Retrieve a single folder by its ID (must belong to the user)."""
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        return folder
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


@router.post("/{id}/update")
async def update_folder_name_by_id(
    id: str, form_data: FolderForm, user=Depends(get_verified_user)
):
    """Rename an existing folder (must belong to the user)."""
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    existing_folder = Folders.get_folder_by_parent_id_and_user_id_and_name(
        folder.parent_id, user.id, form_data.name
    )
    if existing_folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
        )

    try:
        folder = Folders.update_folder_name_by_id_and_user_id(
            id, user.id, form_data.name
        )
        return folder
    except Exception as exc:
        log.exception("%s", exc)
        log.error("Error updating folder: %s", id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
        )


@router.post("/{id}/update/parent")
async def update_folder_parent_id_by_id(
    id: str, form_data: FolderParentIdForm, user=Depends(get_verified_user)
):
    """Move a folder under a different parent folder."""
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    existing_folder = Folders.get_folder_by_parent_id_and_user_id_and_name(
        form_data.parent_id, user.id, folder.name
    )
    if existing_folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
        )

    try:
        folder = Folders.update_folder_parent_id_by_id_and_user_id(
            id, user.id, form_data.parent_id
        )
        return folder
    except Exception as exc:
        log.exception("%s", exc)
        log.error("Error updating folder: %s", id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
        )


@router.post("/{id}/update/expanded")
async def update_folder_is_expanded_by_id(
    id: str, form_data: FolderIsExpandedForm, user=Depends(get_verified_user)
):
    """Toggle whether a folder appears expanded or collapsed in the UI."""
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        folder = Folders.update_folder_is_expanded_by_id_and_user_id(
            id, user.id, form_data.is_expanded
        )
        return folder
    except Exception as exc:
        log.exception("%s", exc)
        log.error("Error updating folder: %s", id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
        )


@router.delete("/{id}")
async def delete_folder_by_id(
    request: Request, id: str, user=Depends(get_verified_user)
):
    """Delete a folder and disassociate its chats.

    Requires the ``chat.delete`` user permission.
    """
    chat_delete_permission = has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    )
    if not chat_delete_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        result = Folders.delete_folder_by_id_and_user_id(id, user.id)
        if result:
            return result
        raise Exception("Error deleting folder")
    except Exception as exc:
        log.exception("%s", exc)
        log.error("Error deleting folder: %s", id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting folder"),
        )
