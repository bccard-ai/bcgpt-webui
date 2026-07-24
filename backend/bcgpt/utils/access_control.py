"""Access-control helpers for permission resolution and resource gating.

Provides utilities for computing effective permissions from group memberships,
checking hierarchical permission keys, and determining which users can access
a given resource based on its access-control metadata.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from bcgpt.config import DEFAULT_USER_PERMISSIONS
from bcgpt.models import Groups, Users, UserModel


# ---------------------------------------------------------------------------
# Permission merging
# ---------------------------------------------------------------------------


def fill_missing_permissions(
    permissions: Dict[str, Any],
    default_permissions: Dict[str, Any],
) -> Dict[str, Any]:
    """Recursively fill missing keys in *permissions* from *default_permissions*.

    Walks the nested dict structure and inserts any key present in
    *default_permissions* but absent from *permissions*.  Existing values
    in *permissions* are never overwritten.

    Args:
        permissions: Target dict to fill (mutated in-place).
        default_permissions: Template dict supplying default values.

    Returns:
        The same *permissions* dict, now guaranteed to contain every key
        present in *default_permissions*.
    """
    for key, value in default_permissions.items():
        if key not in permissions:
            permissions[key] = value
        elif isinstance(value, dict) and isinstance(permissions[key], dict):
            permissions[key] = fill_missing_permissions(permissions[key], value)
    return permissions


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------


def get_permissions(
    user_id: str,
    default_permissions: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute effective permissions for *user_id* by merging group permissions.

    Iterates over every group the user belongs to and combines their
    permission dicts using a "most-permissive wins" strategy (``True > False``).

    Args:
        user_id: Unique identifier of the target user.
        default_permissions: Base permission set used as the starting point
            and as the fallback for any keys not covered by groups.

    Returns:
        A deep-copied permission dict with all group overrides applied and
        any missing fields back-filled from *default_permissions*.
    """

    def combine_permissions(
        permissions: Dict[str, Any],
        group_permissions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge *group_permissions* into *permissions*, preferring True."""
        for key, value in group_permissions.items():
            if isinstance(value, dict):
                if key not in permissions:
                    permissions[key] = {}
                permissions[key] = combine_permissions(permissions[key], value)
            else:
                if key not in permissions:
                    permissions[key] = value
                else:
                    permissions[key] = permissions[key] or value
        return permissions

    user_groups = Groups.get_groups_by_member_id(user_id)
    permissions: Dict[str, Any] = json.loads(json.dumps(default_permissions))

    for group in user_groups:
        permissions = combine_permissions(permissions, group.permissions)

    permissions = fill_missing_permissions(permissions, default_permissions)
    return permissions


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


def has_permission(
    user_id: str,
    permission_key: str,
    default_permissions: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check whether *user_id* holds a specific permission.

    Permission keys are hierarchical and dot-separated (e.g.
    ``"chat.completion"``).  The check first evaluates group permissions
    (any group granting the key is sufficient) and falls back to
    *default_permissions* merged with :data:`DEFAULT_USER_PERMISSIONS`.

    Args:
        user_id: Unique identifier of the user.
        permission_key: Dot-separated permission path to evaluate.
        default_permissions: Base permission dict (defaults to empty).

    Returns:
        ``True`` if the permission is granted, ``False`` otherwise.
    """
    if default_permissions is None:
        default_permissions = {}

    def get_permission(permissions: Dict[str, Any], keys: List[str]) -> bool:
        """Walk *permissions* following *keys* and return the leaf value."""
        for key in keys:
            if key not in permissions:
                return False
            permissions = permissions[key]
        return bool(permissions)

    hierarchy = permission_key.split(".")
    user_groups = Groups.get_groups_by_member_id(user_id)

    for group in user_groups:
        if get_permission(group.permissions, hierarchy):
            return True

    merged = fill_missing_permissions(default_permissions, DEFAULT_USER_PERMISSIONS)
    return get_permission(merged, hierarchy)


# ---------------------------------------------------------------------------
# Resource-level access
# ---------------------------------------------------------------------------


def has_access(
    user_id: str,
    type: str = "write",
    access_control: Optional[dict] = None,
) -> bool:
    """Determine whether *user_id* may access a resource.

    Resources without explicit *access_control* are publicly readable but
    **not** writable (backward-compatible default).

    Args:
        user_id: Unique identifier of the user.
        type: Access type — ``"read"`` or ``"write"``.
        access_control: Resource-level ACL mapping types to dicts with
            ``group_ids`` and ``user_ids`` lists.

    Returns:
        ``True`` if access is allowed.
    """
    if access_control is None:
        return type == "read"

    user_groups = Groups.get_groups_by_member_id(user_id)
    user_group_ids = [group.id for group in user_groups]
    permission_access = access_control.get(type, {})
    permitted_group_ids = permission_access.get("group_ids", [])
    permitted_user_ids = permission_access.get("user_ids", [])

    return user_id in permitted_user_ids or any(
        gid in permitted_group_ids for gid in user_group_ids
    )


def get_users_with_access(
    type: str = "write",
    access_control: Optional[dict] = None,
) -> List[UserModel]:
    """Return all user models that satisfy the given *access_control*.

    When *access_control* is ``None`` every user is considered to have
    access.

    Args:
        type: Access type — ``"read"`` or ``"write"``.
        access_control: Resource-level ACL (see :func:`has_access`).

    Returns:
        List of :class:`UserModel` instances with the requested access.
    """
    if access_control is None:
        return Users.get_users()

    permission_access = access_control.get(type, {})
    permitted_group_ids = permission_access.get("group_ids", [])
    permitted_user_ids = permission_access.get("user_ids", [])

    user_ids_with_access = set(permitted_user_ids)

    for group_id in permitted_group_ids:
        group_user_ids = Groups.get_group_user_ids_by_id(group_id)
        if group_user_ids:
            user_ids_with_access.update(group_user_ids)

    return Users.get_users_by_user_ids(list(user_ids_with_access))
