"""SCIM 2.0 provisioning server (open-moai adoption 3.4).

A minimal SCIM 2.0 implementation so identity providers (Okta, Entra/Azure AD)
can auto-provision users. SCIM ``User`` resources map to bcgpt ``User``/``Auth``
records; ``Group`` resources are read-only projections of bcgpt groups.

Authentication: the IdP sends ``Authorization: Bearer <SCIM_TOKEN>``. Gated by
``SCIM_ENABLED`` (default OFF). RFC 7643/7644.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Groups, Users
from bcgpt.models.auths import Auths
from bcgpt.utils.auth import get_password_hash

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
_BASE = "/api/v1/scim/v2"


# ---------------------------------------------------------------------------
# Auth + helpers
# ---------------------------------------------------------------------------


def _require_scim(request: Request) -> None:
    cfg = request.app.state.config
    if not getattr(cfg, "SCIM_ENABLED", False):
        raise HTTPException(status_code=404, detail="SCIM is not enabled")
    expected = getattr(cfg, "SCIM_TOKEN", "") or ""
    header = request.headers.get("authorization", "")
    provided = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")


def _iso(epoch_seconds: Optional[int]) -> str:
    try:
        return (
            datetime.fromtimestamp(int(epoch_seconds or 0), tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except Exception:
        return "1970-01-01T00:00:00Z"


def _user_to_scim(u) -> dict:
    return {
        "schemas": [USER_SCHEMA],
        "id": u.id,
        "userName": u.email,
        "name": {"formatted": u.name},
        "displayName": u.name,
        "emails": [{"value": u.email, "primary": True}],
        "active": u.role != "pending",
        "meta": {
            "resourceType": "User",
            "created": _iso(u.created_at),
            "lastModified": _iso(u.updated_at),
            "location": f"{_BASE}/Users/{u.id}",
        },
    }


def _group_to_scim(g) -> dict:
    members = []
    try:
        for uid in g.user_ids or []:
            members.append({"value": uid})
    except Exception:
        pass
    return {
        "schemas": [GROUP_SCHEMA],
        "id": g.id,
        "displayName": g.name,
        "members": members,
        "meta": {
            "resourceType": "Group",
            "created": _iso(getattr(g, "created_at", 0)),
            "lastModified": _iso(getattr(g, "updated_at", 0)),
            "location": f"{_BASE}/Groups/{g.id}",
        },
    }


def _scim_extract_user(body: dict) -> tuple[str, str, bool]:
    """Return (email, name, active) from a SCIM User payload."""
    email = body.get("userName") or ""
    emails = body.get("emails") or []
    if not email and emails:
        primary = next((e for e in emails if e.get("primary")), emails[0])
        email = primary.get("value", "")
    name_obj = body.get("name") or {}
    name = (
        body.get("displayName")
        or name_obj.get("formatted")
        or " ".join(
            x for x in [name_obj.get("givenName"), name_obj.get("familyName")] if x
        )
        or email
    )
    active = body.get("active", True)
    return email.lower().strip(), name.strip(), bool(active)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@router.get("/ServiceProviderConfig")
async def service_provider_config(request: Request):
    _require_scim(request)
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Authentication via the SCIM bearer token.",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/Users")
async def list_users(
    request: Request,
    filter: Optional[str] = Query(None),
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=0, le=200),
):
    _require_scim(request)
    resources: list = []
    total = 0

    if filter and "userName eq" in filter:
        # e.g. userName eq "user@example.com"
        try:
            value = filter.split("eq", 1)[1].strip().strip('"')
        except Exception:
            value = ""
        u = Users.get_user_by_email(value.lower()) if value else None
        if u:
            resources = [_user_to_scim(u)]
            total = 1
    else:
        total = Users.get_num_users() or 0
        page = Users.get_users(skip=max(startIndex - 1, 0), limit=count)
        resources = [_user_to_scim(u) for u in page]

    return {
        "schemas": [LIST_SCHEMA],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


@router.get("/Users/{user_id}")
async def get_user(request: Request, user_id: str):
    _require_scim(request)
    u = Users.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_scim(u)


class _ScimBody(BaseModel):
    model_config = {"extra": "allow"}


@router.post("/Users", status_code=201)
async def create_user(request: Request):
    _require_scim(request)
    body = await request.json()
    email, name, active = _scim_extract_user(body)
    if not email:
        raise HTTPException(status_code=400, detail="userName/email is required")
    if Users.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="User already exists")

    # SCIM-provisioned users authenticate via SSO/OAuth, not a password, so a
    # random unusable password hash is stored.
    random_pw = get_password_hash(secrets.token_urlsafe(32))
    role = "user" if active else "pending"
    u = Auths.insert_new_auth(email=email, password=random_pw, name=name, role=role)
    if not u:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return _user_to_scim(u)


def _apply_user_update(user_id: str, name: Optional[str], active: Optional[bool]):
    u = Users.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if name and name != u.name:
        Users.update_user_by_id(user_id, {"name": name})
    if active is not None:
        current_active = u.role != "pending"
        if active and not current_active:
            Users.update_user_role_by_id(user_id, "user")
        elif not active and current_active:
            Users.update_user_role_by_id(user_id, "pending")
    return Users.get_user_by_id(user_id)


@router.put("/Users/{user_id}")
async def replace_user(request: Request, user_id: str):
    _require_scim(request)
    body = await request.json()
    _, name, active = _scim_extract_user(body)
    u = _apply_user_update(user_id, name, active)
    return _user_to_scim(u)


@router.patch("/Users/{user_id}")
async def patch_user(request: Request, user_id: str):
    _require_scim(request)
    body = await request.json()
    name: Optional[str] = None
    active: Optional[bool] = None
    for op in body.get("Operations", []) or []:
        if (op.get("op") or "").lower() not in ("replace", "add"):
            continue
        path = (op.get("path") or "").lower()
        value = op.get("value")
        if path == "active":
            active = bool(value)
        elif path in ("displayname", "name.formatted"):
            name = str(value)
        elif isinstance(value, dict):
            if "active" in value:
                active = bool(value["active"])
            if "displayName" in value:
                name = str(value["displayName"])
    u = _apply_user_update(user_id, name, active)
    return _user_to_scim(u)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(request: Request, user_id: str):
    _require_scim(request)
    if not Users.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    Users.delete_user_by_id(user_id)
    try:
        Auths.delete_auth_by_id(user_id)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Groups (read-only)
# ---------------------------------------------------------------------------


@router.get("/Groups")
async def list_groups(request: Request):
    _require_scim(request)
    groups = Groups.get_groups()
    resources = [_group_to_scim(g) for g in groups]
    return {
        "schemas": [LIST_SCHEMA],
        "totalResults": len(resources),
        "startIndex": 1,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


@router.get("/Groups/{group_id}")
async def get_group(request: Request, group_id: str):
    _require_scim(request)
    g = Groups.get_group_by_id(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_scim(g)
