"""User management router.

Provides endpoints for listing users, managing roles, settings, profile
information, lockout status, and default permission configuration.  All
 mutating operations require admin privileges; read operations for the
 session user's own data require only authentication.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Auths, Chats, Groups
from bcgpt.models.users import (
    UserModel,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
)
from bcgpt.socket import get_active_status_by_user_id
from bcgpt.utils import get_admin_user, get_password_hash, get_permissions, get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class WorkspacePermissions(BaseModel):
    """Permissions controlling which workspace resources a user can manage."""

    models: bool = False
    knowledge: bool = False
    prompts: bool = False
    tools: bool = False


class SharingPermissions(BaseModel):
    """Permissions controlling public sharing of workspace items."""

    public_models: bool = True
    public_knowledge: bool = True
    public_prompts: bool = True
    public_tools: bool = True


class ChatPermissions(BaseModel):
    """Permissions for chat-related features."""

    controls: bool = True
    file_upload: bool = True
    delete: bool = True
    edit: bool = True
    temporary: bool = True
    temporary_enforced: bool = False


class FeaturesPermissions(BaseModel):
    """Permissions for optional platform features."""

    web_search: bool = True
    image_generation: bool = True


class UserPermissions(BaseModel):
    """Aggregated default permissions applied to non-admin users."""

    workspace: WorkspacePermissions
    sharing: SharingPermissions
    chat: ChatPermissions
    features: FeaturesPermissions


class UserResponse(BaseModel):
    """Public profile snippet returned for user look-ups."""

    name: str
    profile_image_url: str
    active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _forbid_self_action(actor_id: str, target_id: str) -> None:
    """Raise 403 when *actor_id* equals *target_id* (self-targeting guard)."""
    if actor_id == target_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )


def _resolve_user_or_404(user_id: str):
    """Fetch a user by id, raising 400 if not found."""
    user = Users.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )
    return user


def _user_permissions_config(request: Request) -> dict:
    """Return the global user-permissions mapping from app state."""
    return request.app.state.config.USER_PERMISSIONS


# ---------------------------------------------------------------------------
# User listing
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[UserModel])
async def get_users(
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    user=Depends(get_admin_user),
):
    """Return a paginated list of all users (admin-only)."""
    return Users.get_users(skip, limit)


@router.get("/lockout-statuses")
async def get_user_lockout_statuses(user=Depends(get_admin_user)):
    """Return lockout status for every account (admin-only)."""
    return Auths.get_all_lockout_statuses()


# ---------------------------------------------------------------------------
# Groups & Permissions
# ---------------------------------------------------------------------------


@router.get("/groups")
async def get_user_groups(user=Depends(get_verified_user)):
    """Return groups the session user belongs to."""
    return Groups.get_groups_by_member_id(user.id)


@router.get("/permissions")
async def get_user_permissisions(request: Request, user=Depends(get_verified_user)):
    """Return effective permissions for the session user.

    Merges the global default permissions with any group-level overrides
    applicable to the user.
    """
    return get_permissions(user.id, _user_permissions_config(request))


# ---------------------------------------------------------------------------
# Default permissions (admin-only)
# ---------------------------------------------------------------------------


def _build_permissions_from_config(config: dict) -> dict:
    """Construct a UserPermissions dict from the raw app-state config."""
    return {
        "workspace": WorkspacePermissions(**config.get("workspace", {})),
        "sharing": SharingPermissions(**config.get("sharing", {})),
        "chat": ChatPermissions(**config.get("chat", {})),
        "features": FeaturesPermissions(**config.get("features", {})),
    }


@router.get("/default/permissions", response_model=UserPermissions)
async def get_default_user_permissions(request: Request, user=Depends(get_admin_user)):
    """Return the system-wide default permissions for non-admin users."""
    return _build_permissions_from_config(_user_permissions_config(request))


@router.post("/default/permissions")
async def update_default_user_permissions(
    request: Request, form_data: UserPermissions, user=Depends(get_admin_user)
):
    """Overwrite the system-wide default permissions (admin-only)."""
    request.app.state.config.USER_PERMISSIONS = form_data.model_dump()
    return request.app.state.config.USER_PERMISSIONS


# ---------------------------------------------------------------------------
# Role management
# ---------------------------------------------------------------------------


@router.post("/update/role", response_model=Optional[UserModel])
async def update_user_role(form_data: UserRoleUpdateForm, user=Depends(get_admin_user)):
    """Change another user's role.

    The admin cannot change their own role, nor the role of the first
    (primary) user on the system.
    """
    first_user = Users.get_first_user()
    if user.id == form_data.id or form_data.id == first_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )

    return Users.update_user_role_by_id(form_data.id, form_data.role)


# ---------------------------------------------------------------------------
# Session-user settings
# ---------------------------------------------------------------------------


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    """Return the session user's application settings."""
    full_user = _resolve_user_or_404(user.id)
    return full_user.settings


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    form_data: UserSettings, user=Depends(get_verified_user)
):
    """Replace the session user's application settings."""
    updated = Users.update_user_settings_by_id(user.id, form_data.model_dump())
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )
    return updated.settings


# ---------------------------------------------------------------------------
# Session-user info
# ---------------------------------------------------------------------------


@router.get("/user/info", response_model=Optional[dict])
async def get_user_info_by_session_user(user=Depends(get_verified_user)):
    """Return the session user's info dict."""
    full_user = _resolve_user_or_404(user.id)
    return full_user.info


@router.post("/user/info/update", response_model=Optional[dict])
async def update_user_info_by_session_user(
    form_data: dict, user=Depends(get_verified_user)
):
    """Merge *form_data* into the session user's info dict."""
    full_user = _resolve_user_or_404(user.id)

    current_info = full_user.info if full_user.info is not None else {}
    merged = {**current_info, **form_data}

    updated = Users.update_user_by_id(user.id, {"info": merged})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )
    return updated.info


# ---------------------------------------------------------------------------
# User look-up by id (with shared-chat resolution)
# ---------------------------------------------------------------------------


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, user=Depends(get_verified_user)):
    """Return public profile data for a user.

    Supports ``shared-<chat_id>`` identifiers — the chat owner's profile
    is returned instead.
    """
    resolved_id = _resolve_shared_chat_user(user_id)
    target = _resolve_user_or_404(resolved_id)
    return UserResponse(
        name=target.name,
        profile_image_url=target.profile_image_url,
        active=get_active_status_by_user_id(resolved_id),
    )


def _resolve_shared_chat_user(user_id: str) -> str:
    """If *user_id* is a ``shared-<chat_id>`` reference, return the chat owner's id.

    Returns the original *user_id* unchanged when it is not a shared-chat prefix.
    Raises 400 when the shared chat does not exist.
    """
    if not user_id.startswith("shared-"):
        return user_id

    chat_id = user_id.removeprefix("shared-")
    chat = Chats.get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )
    return chat.user_id


# ---------------------------------------------------------------------------
# Admin user mutation
# ---------------------------------------------------------------------------


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
):
    """Update another user's profile (admin-only).

    Handles email uniqueness validation and optional password rotation.
    """
    target = _resolve_user_or_404(user_id)
    normalized_email = form_data.email.lower()

    # Prevent email collision with a different account
    if normalized_email != target.email:
        existing = Users.get_user_by_email(normalized_email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.EMAIL_TAKEN,
            )

    # Rotate password when a new one is provided
    if form_data.password:
        hashed = get_password_hash(form_data.password)
        log.debug("Password hash generated for user %s", user_id)
        Auths.update_user_password_by_id(user_id, hashed)

    Auths.update_email_by_id(user_id, normalized_email)

    updated = Users.update_user_by_id(
        user_id,
        {
            "name": form_data.name,
            "email": normalized_email,
            "profile_image_url": form_data.profile_image_url,
        },
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )
    return updated


# ---------------------------------------------------------------------------
# Admin destructive actions
# ---------------------------------------------------------------------------


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    """Permanently remove a user account (admin-only).

    An admin cannot delete their own account.
    """
    _forbid_self_action(user.id, user_id)

    if Auths.delete_auth_by_id(user_id):
        return True

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ERROR_MESSAGES.DELETE_USER_ERROR,
    )


@router.post("/{user_id}/unlock", response_model=bool)
async def unlock_user_by_id(user_id: str, user=Depends(get_admin_user)):
    """Clear lockout state for a user account (admin-only).

    An admin cannot unlock their own account.
    """
    _forbid_self_action(user.id, user_id)

    if Auths.unlock_account_by_id(user_id):
        return True

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ERROR_MESSAGES.DEFAULT("Failed to unlock account"),
    )
