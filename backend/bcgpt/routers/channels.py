"""Channel management router — CRUD, messaging, reactions, and real-time events.

Provides endpoints for creating and managing chat channels, posting and
retrieving messages (with threaded replies), and toggling emoji reactions.
All mutations broadcast socket.io events so connected clients stay in sync.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Users, UserNameResponse
from bcgpt.models import Channels, ChannelForm, ChannelModel
from bcgpt.models.messages import (
    MessageForm,
    MessageModel,
    MessageResponse,
    Messages,
)
from bcgpt.socket import get_user_ids_from_room, sio
from bcgpt.utils import (
    get_admin_user,
    get_users_with_access,
    get_verified_user,
    has_access,
    post_webhook,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class MessageUserResponse(MessageResponse):
    """A message enriched with its author's public profile."""

    user: UserNameResponse


class ReactionForm(BaseModel):
    """Payload for adding or removing an emoji reaction."""

    name: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_channel_or_404(channel_id: str):
    """Fetch a channel by id, raising 404 if it does not exist."""
    channel = Channels.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return channel


def _require_channel_read(channel, user) -> None:
    """Raise 403 if *user* lacks read access to *channel*.

    Admins always pass; non-admin users must have explicit read access
    via the channel's ``access_control`` policy.
    """
    if user.role == "admin":
        return
    if has_access(user.id, type="read", access_control=channel.access_control):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.DEFAULT(),
    )


def _get_message_or_404(message_id: str):
    """Fetch a message by id, raising 404 if it does not exist."""
    message = Messages.get_message_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return message


def _require_message_in_channel(message, channel_id: str) -> None:
    """Raise 400 if *message* does not belong to *channel_id*."""
    if message.channel_id != channel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


def _require_message_owner_or_admin(message, user) -> None:
    """Raise 403 if *user* is neither the message author nor an admin."""
    if message.user_id == user.id or user.role == "admin":
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
    )


def _build_message_user_response(message, user_cache: dict) -> MessageUserResponse:
    """Build a ``MessageUserResponse`` from a raw message, caching user lookups.

    Parameters
    ----------
    message:
        The ORM-level message object.
    user_cache:
        A ``{user_id: user_object}`` mapping that is populated on first lookup
        and reused across messages from the same author.
    """
    if message.user_id not in user_cache:
        user_cache[message.user_id] = Users.get_user_by_id(message.user_id)

    return MessageUserResponse(
        **message.model_dump(),
        user=UserNameResponse(**user_cache[message.user_id].model_dump()),
    )


def _build_enriched_message(message, user_cache: dict) -> MessageUserResponse:
    """Build a ``MessageUserResponse`` including reply metadata and reactions.

    Extends ``_build_message_user_response`` with ``reply_count``,
    ``latest_reply_at``, and ``reactions`` fields.
    """
    replies = Messages.get_replies_by_message_id(message.id)
    latest_reply_at = replies[0].created_at if replies else None

    return MessageUserResponse(
        **message.model_dump(),
        reply_count=len(replies),
        latest_reply_at=latest_reply_at,
        reactions=Messages.get_reactions_by_message_id(message.id),
        user=UserNameResponse(
            **user_cache[message.user_id].model_dump()
        ),
    )


def _user_name_response(user) -> UserNameResponse:
    """Shorthand to build a ``UserNameResponse`` from a user object."""
    return UserNameResponse(**user.model_dump())


async def _emit_channel_event(event_type: str, channel, message, user) -> None:
    """Broadcast a ``channel-events`` socket.io event to all room members."""
    await sio.emit(
        "channel-events",
        {
            "channel_id": channel.id,
            "message_id": message.id,
            "data": {
                "type": event_type,
                "data": MessageUserResponse(
                    **message.model_dump(),
                    user=_user_name_response(user),
                ).model_dump(),
            },
            "user": _user_name_response(user).model_dump(),
            "channel": channel.model_dump(),
        },
        to=f"channel:{channel.id}",
    )


async def _emit_reply_event(channel, parent_message, acting_user) -> None:
    """Emit a ``message:reply`` refresh event for a parent message.

    When a reply is posted (or deleted) the parent message needs to be
    re-broadcast so that connected clients can update the reply count.
    """
    parent_user = Users.get_user_by_id(parent_message.user_id)
    await sio.emit(
        "channel-events",
        {
            "channel_id": channel.id,
            "message_id": parent_message.id,
            "data": {
                "type": "message:reply",
                "data": MessageUserResponse(
                    **parent_message.model_dump(),
                    user=UserNameResponse(**parent_user.model_dump()),
                ).model_dump(),
            },
            "user": _user_name_response(acting_user).model_dump(),
            "channel": channel.model_dump(),
        },
        to=f"channel:{channel.id}",
    )


async def _emit_reaction_event(
    event_type: str, channel, message, acting_user, reaction_name: str
) -> None:
    """Broadcast an ``add`` or ``remove`` reaction event."""
    message_user = Users.get_user_by_id(message.user_id)
    await sio.emit(
        "channel-events",
        {
            "channel_id": channel.id,
            "message_id": message.id,
            "data": {
                "type": event_type,
                "data": {
                    **message.model_dump(),
                    "user": UserNameResponse(
                        **message_user.model_dump()
                    ).model_dump(),
                    "name": reaction_name,
                },
            },
            "user": _user_name_response(acting_user).model_dump(),
            "channel": channel.model_dump(),
        },
        to=f"channel:{channel.id}",
    )


async def send_notification(
    app_name: str,
    bcgpt_url: str,
    channel,
    message,
    active_user_ids: list[str],
) -> None:
    """Push webhook notifications to offline channel members.

    Only users who have configured a notification webhook URL and are *not*
    currently in the channel room will receive a notification.
    """
    eligible_users = get_users_with_access("read", channel.access_control)

    for member in eligible_users:
        if member.id in active_user_ids:
            continue

        if not member.settings:
            continue

        webhook_url = (
            member.settings.ui.get("notifications", {}).get("webhook_url")
        )
        if not webhook_url:
            continue

        post_webhook(
            app_name,
            webhook_url,
            f"#{channel.name} - {bcgpt_url}/channels/{channel.id}\n\n{message.content}",
            {
                "action": "channel",
                "message": message.content,
                "title": channel.name,
                "url": f"{bcgpt_url}/channels/{channel.id}",
            },
        )


# ---------------------------------------------------------------------------
# Channel CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ChannelModel])
async def get_channels(user=Depends(get_verified_user)):
    """Return all channels visible to the current user.

    Admins see every channel; other users see only channels they have
    been granted access to.
    """
    if user.role == "admin":
        return Channels.get_channels()
    return Channels.get_channels_by_user_id(user.id)


@router.post("/create", response_model=Optional[ChannelModel])
async def create_new_channel(form_data: ChannelForm, user=Depends(get_admin_user)):
    """Create a new channel.  Restricted to admin users."""
    try:
        channel = Channels.insert_new_channel(None, form_data, user.id)
        return ChannelModel(**channel.model_dump())
    except Exception as exc:
        log.exception("Failed to create channel: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.get("/{id}", response_model=Optional[ChannelModel])
async def get_channel_by_id(id: str, user=Depends(get_verified_user)):
    """Retrieve a single channel by id, enforcing read access."""
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)
    return ChannelModel(**channel.model_dump())


@router.post("/{id}/update", response_model=Optional[ChannelModel])
async def update_channel_by_id(
    id: str, form_data: ChannelForm, user=Depends(get_admin_user)
):
    """Update channel metadata (name, description, access_control).  Admin only."""
    _get_channel_or_404(id)

    try:
        channel = Channels.update_channel_by_id(id, form_data)
        return ChannelModel(**channel.model_dump())
    except Exception as exc:
        log.exception("Failed to update channel %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.delete("/{id}/delete", response_model=bool)
async def delete_channel_by_id(id: str, user=Depends(get_admin_user)):
    """Delete a channel and all associated data.  Admin only."""
    _get_channel_or_404(id)

    try:
        Channels.delete_channel_by_id(id)
        return True
    except Exception as exc:
        log.exception("Failed to delete channel %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


# ---------------------------------------------------------------------------
# Message listing & retrieval
# ---------------------------------------------------------------------------


@router.get("/{id}/messages", response_model=list[MessageUserResponse])
async def get_channel_messages(
    id: str, skip: int = 0, limit: int = 50, user=Depends(get_verified_user)
):
    """List messages in a channel with reply counts, reactions, and author info.

    Results are paginated via ``skip`` / ``limit`` query parameters.
    """
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message_list = Messages.get_messages_by_channel_id(id, skip, limit)
    user_cache: dict = {}

    return [_build_enriched_message(msg, user_cache) for msg in message_list]


@router.get("/{id}/messages/{message_id}", response_model=Optional[MessageUserResponse])
async def get_channel_message(
    id: str, message_id: str, user=Depends(get_verified_user)
):
    """Retrieve a single message from a channel."""
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message = _get_message_or_404(message_id)
    _require_message_in_channel(message, id)

    user_cache: dict = {}
    return _build_message_user_response(message, user_cache)


@router.get(
    "/{id}/messages/{message_id}/thread", response_model=list[MessageUserResponse]
)
async def get_channel_thread_messages(
    id: str,
    message_id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
):
    """List threaded replies to a specific message.

    Results are paginated via ``skip`` / ``limit`` query parameters.
    """
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message_list = Messages.get_messages_by_parent_id(id, message_id, skip, limit)
    user_cache: dict = {}

    return [
        MessageUserResponse(
            **msg.model_dump(),
            reply_count=0,
            latest_reply_at=None,
            reactions=Messages.get_reactions_by_message_id(msg.id),
            user=UserNameResponse(**user_cache.setdefault(
                msg.user_id, Users.get_user_by_id(msg.user_id)
            ).model_dump()),
        )
        for msg in message_list
    ]


# ---------------------------------------------------------------------------
# Message mutations
# ---------------------------------------------------------------------------


@router.post("/{id}/messages/post", response_model=Optional[MessageModel])
async def post_new_message(
    request: Request,
    id: str,
    form_data: MessageForm,
    background_tasks: BackgroundTasks,
    user=Depends(get_verified_user),
):
    """Post a new message (or reply) to a channel.

    On success the message is broadcast to all room members via socket.io.
    If the message is a reply, the parent is also refreshed.  A background
    task pushes webhook notifications to offline members.
    """
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    try:
        message = Messages.insert_new_message(form_data, channel.id, user.id)

        if message:
            # Broadcast the new message
            replies = []
            enriched = MessageUserResponse(
                **message.model_dump(),
                reply_count=0,
                latest_reply_at=None,
                reactions=Messages.get_reactions_by_message_id(message.id),
                user=_user_name_response(user),
            )
            await sio.emit(
                "channel-events",
                {
                    "channel_id": channel.id,
                    "message_id": message.id,
                    "data": {
                        "type": "message",
                        "data": enriched.model_dump(),
                    },
                    "user": _user_name_response(user).model_dump(),
                    "channel": channel.model_dump(),
                },
                to=f"channel:{channel.id}",
            )

            # Refresh parent if this is a reply
            if message.parent_id:
                parent_message = Messages.get_message_by_id(message.parent_id)
                if parent_message:
                    await _emit_reply_event(channel, parent_message, user)

            # Schedule webhook notifications for offline members
            active_user_ids = get_user_ids_from_room(f"channel:{channel.id}")
            background_tasks.add_task(
                send_notification,
                request.app.state.BCGPT_APP_NAME,
                request.app.state.config.BCGPT_URL,
                channel,
                message,
                active_user_ids,
            )

        return MessageModel(**message.model_dump())
    except Exception as exc:
        log.exception("Failed to post message to channel %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.post(
    "/{id}/messages/{message_id}/update", response_model=Optional[MessageModel]
)
async def update_message_by_id(
    id: str, message_id: str, form_data: MessageForm, user=Depends(get_verified_user)
):
    """Update the content of an existing message.

    Only the message author (or an admin) may edit.
    """
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message = _get_message_or_404(message_id)
    _require_message_in_channel(message, id)
    _require_message_owner_or_admin(message, user)

    try:
        Messages.update_message_by_id(message_id, form_data)
        message = Messages.get_message_by_id(message_id)

        if message:
            await _emit_channel_event("message:update", channel, message, user)

        return MessageModel(**message.model_dump())
    except Exception as exc:
        log.exception("Failed to update message %s: %s", message_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.delete("/{id}/messages/{message_id}/delete", response_model=bool)
async def delete_message_by_id(
    id: str, message_id: str, user=Depends(get_verified_user)
):
    """Delete a message.  Only the author (or an admin) may delete."""
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message = _get_message_or_404(message_id)
    _require_message_in_channel(message, id)
    _require_message_owner_or_admin(message, user)

    try:
        Messages.delete_message_by_id(message_id)

        # Broadcast the deletion
        await sio.emit(
            "channel-events",
            {
                "channel_id": channel.id,
                "message_id": message.id,
                "data": {
                    "type": "message:delete",
                    "data": {
                        **message.model_dump(),
                        "user": _user_name_response(user).model_dump(),
                    },
                },
                "user": _user_name_response(user).model_dump(),
                "channel": channel.model_dump(),
            },
            to=f"channel:{channel.id}",
        )

        # Refresh parent if the deleted message was a reply
        if message.parent_id:
            parent_message = Messages.get_message_by_id(message.parent_id)
            if parent_message:
                await _emit_reply_event(channel, parent_message, user)

        return True
    except Exception as exc:
        log.exception("Failed to delete message %s: %s", message_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------


@router.post("/{id}/messages/{message_id}/reactions/add", response_model=bool)
async def add_reaction_to_message(
    id: str, message_id: str, form_data: ReactionForm, user=Depends(get_verified_user)
):
    """Add an emoji reaction to a message."""
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message = _get_message_or_404(message_id)
    _require_message_in_channel(message, id)

    try:
        Messages.add_reaction_to_message(message_id, user.id, form_data.name)
        message = Messages.get_message_by_id(message_id)

        await _emit_reaction_event(
            "message:reaction:add", channel, message, user, form_data.name
        )

        return True
    except Exception as exc:
        log.exception("Failed to add reaction to message %s: %s", message_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@router.post("/{id}/messages/{message_id}/reactions/remove", response_model=bool)
async def remove_reaction_by_id_and_user_id_and_name(
    id: str, message_id: str, form_data: ReactionForm, user=Depends(get_verified_user)
):
    """Remove an emoji reaction from a message."""
    channel = _get_channel_or_404(id)
    _require_channel_read(channel, user)

    message = _get_message_or_404(message_id)
    _require_message_in_channel(message, id)

    try:
        Messages.remove_reaction_by_id_and_user_id_and_name(
            message_id, user.id, form_data.name
        )
        message = Messages.get_message_by_id(message_id)

        await _emit_reaction_event(
            "message:reaction:remove", channel, message, user, form_data.name
        )

        return True
    except Exception as exc:
        log.exception("Failed to remove reaction from message %s: %s", message_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )
