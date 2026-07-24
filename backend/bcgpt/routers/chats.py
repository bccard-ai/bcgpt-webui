"""Chat CRUD router — conversation lifecycle, sharing, tags, and archival.

Provides endpoints for creating, reading, updating, and deleting user chats,
along with sharing, cloning, pinning, archival, tag management, and
real-time event broadcasting via WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from bcgpt.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Folders, TagModel, Tags
from bcgpt.models.chats import (
    ChatForm,
    ChatImportForm,
    ChatResponse,
    ChatSearchResult,
    Chats,
    ChatTitleIdResponse,
)
from bcgpt.socket import get_event_emitter
from bcgpt.utils import get_admin_user, get_verified_user, has_permission

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class TagForm(BaseModel):
    """Payload for tag operations that only require a name."""

    name: str


class TagFilterForm(TagForm):
    """Tag lookup with pagination."""

    skip: Optional[int] = 0
    limit: Optional[int] = 50


class MessageForm(BaseModel):
    """Payload for updating a single message's content."""

    content: str


class EventForm(BaseModel):
    """Payload for broadcasting a real-time event to chat participants."""

    type: str
    data: dict


class CloneForm(BaseModel):
    """Payload for cloning a chat with an optional custom title."""

    title: Optional[str] = None


class ChatFolderIdForm(BaseModel):
    """Payload for moving a chat into (or out of) a folder."""

    folder_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Pagination defaults
# ---------------------------------------------------------------------------

_PAGE_SIZE: int = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_chat_response(chat) -> ChatResponse:
    """Convert a chat ORM/model object to a ChatResponse."""
    return ChatResponse(**chat.model_dump())


def _to_chat_response_list(chats) -> list[ChatResponse]:
    """Convert a sequence of chat objects to ChatResponse list."""
    return [_to_chat_response(c) for c in chats]


def _to_title_response_list(chats) -> list[ChatTitleIdResponse]:
    """Convert a sequence of chat objects to ChatTitleIdResponse list."""
    return [ChatTitleIdResponse(**c.model_dump()) for c in chats]


async def _get_user_chat_or_error(chat_id: str, user_id: str) -> ChatResponse:
    """Fetch a chat owned by *user_id* or raise 404.

    Used by endpoints where the user must own the chat. A missing-or-foreign
    chat is reported as 404 (not 401): 401 is reserved for authentication
    failures, and returning it here would make the frontend's global
    unauthorized-interceptor force-log-out a perfectly valid session.
    """
    chat = await asyncio.to_thread(Chats.get_chat_by_id_and_user_id, chat_id, user_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return chat


async def _get_chat_by_id_or_error(chat_id: str):
    """Fetch any chat by id or raise 404.

    Used by admin-level or ownership-verified endpoints.
    """
    chat = await asyncio.to_thread(Chats.get_chat_by_id, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return chat


def _require_chat_owner_or_admin(chat, user) -> None:
    """Raise 403 if *user* does not own *chat* and is not admin."""
    if chat.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


async def _require_delete_permission(request: Request, user) -> None:
    """Raise 403 if a non-admin user lacks the ``chat.delete`` permission."""
    if user.role == "user" and not has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


def _require_admin_feature(enabled: bool) -> None:
    """Raise 403 when an admin-only feature flag is disabled."""
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


async def _cleanup_orphan_tags(tag_ids: list[str], user_id: str) -> None:
    """Delete tags that are no longer referenced by any chat.

    Runs in a thread to avoid blocking the event loop.
    """
    for tag_id in tag_ids:
        count = await asyncio.to_thread(
            Chats.count_chats_by_tag_name_and_user_id, tag_id, user_id
        )
        if count == 0:
            log.debug("Deleting orphan tag: %s", tag_id)
            await asyncio.to_thread(
                Tags.delete_tag_by_name_and_user_id, tag_id, user_id
            )


async def _emit_chat_event(
    user_id: str, chat_id: str, message_id: str, event: dict
) -> bool:
    """Broadcast a real-time event via WebSocket.

    Returns ``True`` if the event was sent successfully, ``False`` otherwise.
    """
    emitter = get_event_emitter(
        {"user_id": user_id, "chat_id": chat_id, "message_id": message_id},
        False,
    )
    if not emitter:
        return False
    try:
        await emitter(event)
        return True
    except Exception:
        log.debug("Failed to emit chat event for %s/%s", chat_id, message_id)
        return False


# ---------------------------------------------------------------------------
# List / search endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ChatTitleIdResponse])
@router.get("/list", response_model=list[ChatTitleIdResponse])
async def get_session_user_chat_list(
    user=Depends(get_verified_user), page: Optional[int] = None
):
    """Return the current user's chats, optionally paginated.

    When *page* is provided, returns ``_PAGE_SIZE`` chats starting at the
    appropriate offset.  Without pagination the full list is returned.
    """
    if page is not None:
        skip = (page - 1) * _PAGE_SIZE
        chats = await asyncio.to_thread(
            Chats.get_chat_title_id_list_by_user_id,
            user.id,
            skip=skip,
            limit=_PAGE_SIZE,
        )
    else:
        chats = await asyncio.to_thread(
            Chats.get_chat_title_id_list_by_user_id, user.id
        )
    return chats


@router.get("/search", response_model=list[ChatSearchResult])
async def search_user_chats(
    text: str = Query(min_length=1, max_length=200),
    page: Optional[int] = Query(default=None, ge=1),
    user=Depends(get_verified_user),
):
    """Full-text search across the user's chats.

    If the query is a single word prefixed with ``tag:``, and no results
    are found, the corresponding tag is automatically cleaned up.
    """
    if page is None:
        page = 1

    skip = (page - 1) * _PAGE_SIZE
    chats = await asyncio.to_thread(
        Chats.get_chats_by_user_id_and_search_text,
        user.id,
        text,
        skip=skip,
        limit=_PAGE_SIZE,
    )
    chat_list = chats

    # Auto-delete tag when searching yields no results on first page
    words = text.strip().split(" ")
    if page == 1 and len(words) == 1 and words[0].startswith("tag:"):
        tag_id = words[0].replace("tag:", "")
        if not chat_list:
            tag_exists = await asyncio.to_thread(
                Tags.get_tag_by_name_and_user_id, tag_id, user.id
            )
            if tag_exists:
                log.debug("Deleting empty tag from search: %s", tag_id)
                await asyncio.to_thread(
                    Tags.delete_tag_by_name_and_user_id, tag_id, user.id
                )

    return chat_list


@router.get("/list/user/{user_id}", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_user_id(
    user_id: str,
    user=Depends(get_admin_user),
    skip: int = 0,
    limit: int = 50,
):
    """Admin endpoint: list any user's chats including archived ones."""
    _require_admin_feature(ENABLE_ADMIN_CHAT_ACCESS)
    return await asyncio.to_thread(
        Chats.get_chat_list_by_user_id,
        user_id,
        include_archived=True,
        skip=skip,
        limit=limit,
    )


@router.get("/all", response_model=list[ChatResponse])
async def get_user_chats(user=Depends(get_verified_user)):
    """Return all of the current user's chats (non-archived)."""
    chats = await asyncio.to_thread(Chats.get_chats_by_user_id, user.id)
    return _to_chat_response_list(chats)


@router.get("/all/archived", response_model=list[ChatResponse])
async def get_user_archived_chats(user=Depends(get_verified_user)):
    """Return all archived chats for the current user."""
    chats = await asyncio.to_thread(Chats.get_archived_chats_by_user_id, user.id)
    return _to_chat_response_list(chats)


@router.get("/all/db", response_model=list[ChatResponse])
async def get_all_user_chats_in_db(user=Depends(get_admin_user)):
    """Admin export: return every chat in the database."""
    _require_admin_feature(ENABLE_ADMIN_EXPORT)
    chats = await asyncio.to_thread(Chats.get_chats)
    return _to_chat_response_list(chats)


@router.get("/archived", response_model=list[ChatTitleIdResponse])
async def get_archived_session_user_chat_list(
    user=Depends(get_verified_user), skip: int = 0, limit: int = 50
):
    """Paginated list of the current user's archived chats."""
    return await asyncio.to_thread(
        Chats.get_archived_chat_list_by_user_id, user.id, skip, limit
    )


@router.get("/folder/{folder_id}", response_model=list[ChatResponse])
async def get_chats_by_folder_id(folder_id: str, user=Depends(get_verified_user)):
    """Return chats inside a folder and all its descendant folders."""
    folder_ids = [folder_id]
    children = await asyncio.to_thread(
        Folders.get_children_folders_by_id_and_user_id, folder_id, user.id
    )
    if children:
        folder_ids.extend(child.id for child in children)

    chats = await asyncio.to_thread(
        Chats.get_chats_by_folder_ids_and_user_id, folder_ids, user.id
    )
    return _to_chat_response_list(chats)


@router.get("/pinned", response_model=list[ChatResponse])
async def get_user_pinned_chats(user=Depends(get_verified_user)):
    """Return all chats the user has pinned."""
    chats = await asyncio.to_thread(Chats.get_pinned_chats_by_user_id, user.id)
    return _to_chat_response_list(chats)


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------


@router.get("/all/tags", response_model=list[TagModel])
async def get_all_user_tags(user=Depends(get_verified_user)):
    """Return all tags belonging to the current user."""
    try:
        return await asyncio.to_thread(Tags.get_tags_by_user_id, user.id)
    except Exception as exc:
        log.exception("Failed to fetch tags for user %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.post("/tags", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_tag_name(
    form_data: TagFilterForm, user=Depends(get_verified_user)
):
    """Return chats associated with a specific tag.

    If no chats remain for the tag, the tag is deleted automatically.
    """
    chats = await asyncio.to_thread(
        Chats.get_chat_list_by_user_id_and_tag_name,
        user.id,
        form_data.name,
        form_data.skip,
        form_data.limit,
    )
    if not chats:
        await asyncio.to_thread(
            Tags.delete_tag_by_name_and_user_id, form_data.name, user.id
        )
    return chats


# ---------------------------------------------------------------------------
# Create / import
# ---------------------------------------------------------------------------


@router.post("/new", response_model=Optional[ChatResponse])
async def create_new_chat(form_data: ChatForm, user=Depends(get_verified_user)):
    """Create a new chat for the current user."""
    try:
        chat = await asyncio.to_thread(Chats.insert_new_chat, user.id, form_data)
        return _to_chat_response(chat)
    except Exception as exc:
        log.exception("Failed to create chat for user %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.post("/import", response_model=Optional[ChatResponse])
async def import_chat(form_data: ChatImportForm, user=Depends(get_verified_user)):
    """Import a chat from external data, preserving tags.

    Tags present in the imported chat's metadata are created if they
    don't already exist for the user.
    """
    try:
        chat = await asyncio.to_thread(Chats.import_chat, user.id, form_data)
        if chat:
            tags = chat.meta.get("tags", [])
            await _import_tags(tags, user.id)
        return _to_chat_response(chat)
    except Exception as exc:
        log.exception("Failed to import chat for user %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


async def _import_tags(tag_ids: list[str], user_id: str) -> None:
    """Create missing tags from an imported chat's metadata."""
    for tag_id in tag_ids:
        normalized = tag_id.replace(" ", "_").lower()
        if normalized == "none":
            continue
        display_name = " ".join(word.capitalize() for word in normalized.split("_"))
        existing = await asyncio.to_thread(
            Tags.get_tag_by_name_and_user_id, display_name, user_id
        )
        if existing is None:
            await asyncio.to_thread(Tags.insert_new_tag, display_name, user_id)


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


@router.delete("/", response_model=bool)
async def delete_all_user_chats(request: Request, user=Depends(get_verified_user)):
    """Delete every chat owned by the current user.

    Non-admin users must have the ``chat.delete`` permission.
    """
    await _require_delete_permission(request, user)
    return await asyncio.to_thread(Chats.delete_chats_by_user_id, user.id)


@router.post("/archive/all", response_model=bool)
async def archive_all_chats(user=Depends(get_verified_user)):
    """Archive all chats for the current user."""
    return await asyncio.to_thread(Chats.archive_all_chats_by_user_id, user.id)


# ---------------------------------------------------------------------------
# Single chat CRUD
# ---------------------------------------------------------------------------


@router.get("/{id}", response_model=Optional[ChatResponse])
async def get_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Retrieve a single chat owned by the current user."""
    chat = await _get_user_chat_or_error(id, user.id)
    return _to_chat_response(chat)


@router.post("/{id}", response_model=Optional[ChatResponse])
async def update_chat_by_id(
    id: str, form_data: ChatForm, user=Depends(get_verified_user)
):
    """Merge new chat data into an existing chat."""
    chat = await _get_user_chat_or_error(id, user.id)
    merged = {**chat.chat, **form_data.chat}
    updated = await asyncio.to_thread(Chats.update_chat_by_id, id, merged)
    return _to_chat_response(updated)


@router.delete("/{id}", response_model=bool)
async def delete_chat_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    """Delete a chat by id.

    Admins can delete any chat. Regular users must own the chat and have
    the ``chat.delete`` permission.  Orphan tags are cleaned up.
    """
    chat = await _get_chat_by_id_or_error(id)

    if user.role == "admin":
        await _cleanup_orphan_tags(chat.meta.get("tags", []), user.id)
        return await asyncio.to_thread(Chats.delete_chat_by_id, id)

    await _require_delete_permission(request, user)
    if chat.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    await _cleanup_orphan_tags(chat.meta.get("tags", []), user.id)
    return await asyncio.to_thread(Chats.delete_chat_by_id_and_user_id, id, user.id)


# ---------------------------------------------------------------------------
# Message-level operations
# ---------------------------------------------------------------------------


@router.post("/{id}/messages/{message_id}", response_model=Optional[ChatResponse])
async def update_chat_message_by_id(
    id: str, message_id: str, form_data: MessageForm, user=Depends(get_verified_user)
):
    """Update the content of a specific message within a chat.

    Broadcasts a ``chat:message`` event so connected clients see the
    update in real time.
    """
    chat = await _get_chat_by_id_or_error(id)
    _require_chat_owner_or_admin(chat, user)

    updated = await asyncio.to_thread(
        Chats.upsert_message_to_chat_by_id_and_message_id,
        id,
        message_id,
        {"content": form_data.content},
    )

    await _emit_chat_event(
        user.id,
        id,
        message_id,
        {
            "type": "chat:message",
            "data": {
                "chat_id": id,
                "message_id": message_id,
                "content": form_data.content,
            },
        },
    )

    return _to_chat_response(updated)


@router.post("/{id}/messages/{message_id}/event", response_model=Optional[bool])
async def send_chat_message_event_by_id(
    id: str, message_id: str, form_data: EventForm, user=Depends(get_verified_user)
):
    """Broadcast a custom real-time event for a chat message."""
    chat = await _get_chat_by_id_or_error(id)
    _require_chat_owner_or_admin(chat, user)

    emitter = get_event_emitter(
        {"user_id": user.id, "chat_id": id, "message_id": message_id}
    )
    try:
        if emitter:
            await emitter(form_data.model_dump())
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pinning
# ---------------------------------------------------------------------------


@router.get("/{id}/pinned", response_model=Optional[bool])
async def get_pinned_status_by_id(id: str, user=Depends(get_verified_user)):
    """Return whether a chat is pinned."""
    chat = await _get_user_chat_or_error(id, user.id)
    return chat.pinned


@router.post("/{id}/pin", response_model=Optional[ChatResponse])
async def pin_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Toggle the pinned state of a chat."""
    await _get_user_chat_or_error(id, user.id)
    chat = await asyncio.to_thread(Chats.toggle_chat_pinned_by_id, id)
    return chat


# ---------------------------------------------------------------------------
# Cloning
# ---------------------------------------------------------------------------


@router.post("/{id}/clone", response_model=Optional[ChatResponse])
async def clone_chat_by_id(
    form_data: CloneForm, id: str, user=Depends(get_verified_user)
):
    """Clone a chat owned by the current user.

    The clone preserves the original chat id and branch point in its
    metadata.  An optional custom title can be provided.
    """
    chat = await _get_user_chat_or_error(id, user.id)
    title = form_data.title if form_data.title else "Clone of %s" % chat.title
    cloned_data = {
        **chat.chat,
        "originalChatId": chat.id,
        "branchPointMessageId": chat.chat["history"]["currentId"],
        "title": title,
    }
    new_chat = await asyncio.to_thread(
        Chats.insert_new_chat, user.id, ChatForm(**{"chat": cloned_data})
    )
    return _to_chat_response(new_chat)


@router.post("/{id}/clone/shared", response_model=Optional[ChatResponse])
async def clone_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Clone a shared chat into the current user's chat list."""
    chat = await asyncio.to_thread(Chats.get_chat_by_share_id, id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    cloned_data = {
        **chat.chat,
        "originalChatId": chat.id,
        "branchPointMessageId": chat.chat["history"]["currentId"],
        "title": "Clone of %s" % chat.title,
    }
    new_chat = await asyncio.to_thread(
        Chats.insert_new_chat, user.id, ChatForm(**{"chat": cloned_data})
    )
    return _to_chat_response(new_chat)


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


@router.get("/share/{share_id}", response_model=Optional[ChatResponse])
async def get_shared_chat_by_id(share_id: str, user=Depends(get_verified_user)):
    """Retrieve a shared chat by its share id.

    Pending users are denied access.  Regular users and admins without
    ``ENABLE_ADMIN_CHAT_ACCESS`` see the shared version; admins with the
    feature enabled see the full chat.
    """
    if user.role == "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if user.role == "user" or (user.role == "admin" and not ENABLE_ADMIN_CHAT_ACCESS):
        chat = await asyncio.to_thread(Chats.get_chat_by_share_id, share_id)
    elif user.role == "admin" and ENABLE_ADMIN_CHAT_ACCESS:
        chat = await asyncio.to_thread(Chats.get_chat_by_id, share_id)
    else:
        chat = None

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return _to_chat_response(chat)


@router.post("/{id}/share", response_model=Optional[ChatResponse])
async def share_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Create or update a shared link for a chat."""
    chat = await _get_user_chat_or_error(id, user.id)

    if chat.share_id:
        shared = await asyncio.to_thread(Chats.update_shared_chat_by_chat_id, chat.id)
        return _to_chat_response(shared)

    shared = await asyncio.to_thread(Chats.insert_shared_chat_by_chat_id, chat.id)
    if not shared:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )
    return _to_chat_response(shared)


@router.delete("/{id}/share", response_model=Optional[bool])
async def delete_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Remove the shared link from a chat."""
    chat = await _get_user_chat_or_error(id, user.id)
    if not chat.share_id:
        return False

    deleted = await asyncio.to_thread(Chats.delete_shared_chat_by_chat_id, id)
    updated = await asyncio.to_thread(Chats.update_chat_share_id_by_id, id, None)
    return deleted and updated is not None


# ---------------------------------------------------------------------------
# Archival
# ---------------------------------------------------------------------------


@router.post("/{id}/archive", response_model=Optional[ChatResponse])
async def archive_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Toggle the archival state of a chat.

    Archiving a chat removes its tags; unarchiving restores any tags
    that still exist in the user's tag list.
    """
    chat = await _get_user_chat_or_error(id, user.id)
    chat = await asyncio.to_thread(Chats.toggle_chat_archive_by_id, id)

    if chat.archived:
        await _cleanup_orphan_tags(chat.meta.get("tags", []), user.id)
    else:
        await _restore_tags_on_unarchive(chat.meta.get("tags", []), user.id)

    return _to_chat_response(chat)


async def _restore_tags_on_unarchive(tag_ids: list[str], user_id: str) -> None:
    """Re-create tags that were removed during archival if they no longer exist."""
    for tag_id in tag_ids:
        existing = await asyncio.to_thread(
            Tags.get_tag_by_name_and_user_id, tag_id, user_id
        )
        if existing is None:
            log.debug("Restoring tag on unarchive: %s", tag_id)
            await asyncio.to_thread(Tags.insert_new_tag, tag_id, user_id)


# ---------------------------------------------------------------------------
# Folder assignment
# ---------------------------------------------------------------------------


@router.post("/{id}/folder", response_model=Optional[ChatResponse])
async def update_chat_folder_id_by_id(
    id: str, form_data: ChatFolderIdForm, user=Depends(get_verified_user)
):
    """Move a chat into or out of a folder."""
    await _get_user_chat_or_error(id, user.id)
    chat = await asyncio.to_thread(
        Chats.update_chat_folder_id_by_id_and_user_id, id, user.id, form_data.folder_id
    )
    return _to_chat_response(chat)


# ---------------------------------------------------------------------------
# Per-chat tag operations
# ---------------------------------------------------------------------------


@router.get("/{id}/tags", response_model=list[TagModel])
async def get_chat_tags_by_id(id: str, user=Depends(get_verified_user)):
    """Return all tags attached to a chat."""
    chat = await _get_user_chat_or_error(id, user.id)
    tag_ids = chat.meta.get("tags", [])
    return await asyncio.to_thread(Tags.get_tags_by_ids_and_user_id, tag_ids, user.id)


@router.post("/{id}/tags", response_model=list[TagModel])
async def add_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """Attach a tag to a chat, creating the tag if necessary."""
    await _get_user_chat_or_error(id, user.id)

    normalized = form_data.name.replace(" ", "_").lower()
    if normalized == "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Tag name cannot be 'None'"),
        )

    await asyncio.to_thread(
        Chats.add_chat_tag_by_id_and_user_id_and_tag_name,
        id,
        user.id,
        form_data.name,
    )

    chat = await asyncio.to_thread(Chats.get_chat_by_id_and_user_id, id, user.id)
    tag_ids = chat.meta.get("tags", [])
    return await asyncio.to_thread(Tags.get_tags_by_ids_and_user_id, tag_ids, user.id)


@router.delete("/{id}/tags", response_model=list[TagModel])
async def delete_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """Remove a tag from a chat and delete the tag if unused elsewhere."""
    await _get_user_chat_or_error(id, user.id)

    await asyncio.to_thread(
        Chats.delete_tag_by_id_and_user_id_and_tag_name, id, user.id, form_data.name
    )

    count = await asyncio.to_thread(
        Chats.count_chats_by_tag_name_and_user_id, form_data.name, user.id
    )
    if count == 0:
        await asyncio.to_thread(
            Tags.delete_tag_by_name_and_user_id, form_data.name, user.id
        )

    chat = await asyncio.to_thread(Chats.get_chat_by_id_and_user_id, id, user.id)
    tag_ids = chat.meta.get("tags", [])
    return await asyncio.to_thread(Tags.get_tags_by_ids_and_user_id, tag_ids, user.id)


@router.delete("/{id}/tags/all", response_model=Optional[bool])
async def delete_all_tags_by_id(id: str, user=Depends(get_verified_user)):
    """Remove all tags from a chat and clean up orphan tags."""
    chat = await _get_user_chat_or_error(id, user.id)

    await asyncio.to_thread(Chats.delete_all_tags_by_id_and_user_id, id, user.id)
    await _cleanup_orphan_tags(chat.meta.get("tags", []), user.id)
    return True
