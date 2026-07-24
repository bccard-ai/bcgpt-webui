"""OAuth2 authentication manager for BCGPT WebUI.

Supports Google, Microsoft, GitHub, and generic OIDC providers via authlib.
Handles login redirects, callback processing, user provisioning, role/group
management, and JWT cookie issuance.

Public exports:
    OAuthManager       -- main class registered in main.py
    auth_manager_config -- AppConfig instance holding all OAuth-related settings
    log                -- module-level logger
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import sys
import uuid
from typing import Any

import aiohttp
from authlib.integrations.starlette_client import OAuth
from authlib.oidc.core import UserInfo
from fastapi import HTTPException, status
from starlette.responses import RedirectResponse

from bcgpt.config import (
    DEFAULT_USER_ROLE,
    ENABLE_OAUTH_GROUP_MANAGEMENT,
    ENABLE_OAUTH_ROLE_MANAGEMENT,
    ENABLE_OAUTH_SIGNUP,
    JWT_EXPIRES_IN,
    OAUTH_ADMIN_ROLES,
    OAUTH_ALLOWED_DOMAINS,
    OAUTH_ALLOWED_ROLES,
    OAUTH_EMAIL_CLAIM,
    OAUTH_GROUPS_CLAIM,
    OAUTH_MERGE_ACCOUNTS_BY_EMAIL,
    OAUTH_PICTURE_CLAIM,
    OAUTH_PROVIDERS,
    OAUTH_ROLES_CLAIM,
    OAUTH_USERNAME_CLAIM,
    WEBHOOK_URL,
    AppConfig,
)
from bcgpt.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from bcgpt.env import (
    GLOBAL_LOG_LEVEL,
    SRC_LOG_LEVELS,
    BCGPT_AUTH_COOKIE_SAME_SITE,
    BCGPT_AUTH_COOKIE_SECURE,
    BCGPT_APP_NAME,
)
from bcgpt.models import Auths, Groups, GroupModel, GroupUpdateForm, Users
from bcgpt.retrieval.web.utils import validate_url
from bcgpt.utils import create_token, get_password_hash, parse_duration, post_webhook

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OAUTH"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

auth_manager_config = AppConfig()
auth_manager_config.DEFAULT_USER_ROLE = DEFAULT_USER_ROLE
auth_manager_config.ENABLE_OAUTH_SIGNUP = ENABLE_OAUTH_SIGNUP
auth_manager_config.OAUTH_MERGE_ACCOUNTS_BY_EMAIL = OAUTH_MERGE_ACCOUNTS_BY_EMAIL
auth_manager_config.ENABLE_OAUTH_ROLE_MANAGEMENT = ENABLE_OAUTH_ROLE_MANAGEMENT
auth_manager_config.ENABLE_OAUTH_GROUP_MANAGEMENT = ENABLE_OAUTH_GROUP_MANAGEMENT
auth_manager_config.OAUTH_ROLES_CLAIM = OAUTH_ROLES_CLAIM
auth_manager_config.OAUTH_GROUPS_CLAIM = OAUTH_GROUPS_CLAIM
auth_manager_config.OAUTH_EMAIL_CLAIM = OAUTH_EMAIL_CLAIM
auth_manager_config.OAUTH_PICTURE_CLAIM = OAUTH_PICTURE_CLAIM
auth_manager_config.OAUTH_USERNAME_CLAIM = OAUTH_USERNAME_CLAIM
auth_manager_config.OAUTH_ALLOWED_ROLES = OAUTH_ALLOWED_ROLES
auth_manager_config.OAUTH_ADMIN_ROLES = OAUTH_ADMIN_ROLES
auth_manager_config.OAUTH_ALLOWED_DOMAINS = OAUTH_ALLOWED_DOMAINS
auth_manager_config.WEBHOOK_URL = WEBHOOK_URL
auth_manager_config.JWT_EXPIRES_IN = JWT_EXPIRES_IN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_nested_claim(data: dict, claim_path: str) -> list:
    """Traverse *claim_path* (dot-separated) inside *data* and return a list.

    Returns an empty list when the path is missing or the leaf value is not a
    list.
    """
    if not claim_path:
        return []
    node = data
    for key in claim_path.split("."):
        node = node.get(key, {})
    return node if isinstance(node, list) else []


def _is_email_verified(user_data: UserInfo, provider: str) -> bool:
    """Determine whether the IdP asserts the email as verified.

    GitHub always returns verified emails, so it is treated as verified by
    default.
    """
    if provider == "github":
        return True
    return user_data.get("email_verified") in (True, "true", "True", 1, "1")


async def _fetch_github_email(token: dict) -> str:
    """Fetch the primary verified email from the GitHub API.

    Raises ``HTTPException(400)`` on any failure.
    """
    access_token = token.get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/user/emails", headers=headers
            ) as resp:
                if not resp.ok:
                    log.warning("Failed to fetch GitHub email (status %d)", resp.status)
                    raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
                emails = await resp.json()
                primary = next(
                    (
                        e["email"]
                        for e in emails
                        if e.get("primary") and e.get("verified")
                    ),
                    None,
                )
                if not primary:
                    log.warning("No primary verified email found in GitHub response")
                    raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
                return primary
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("Error fetching GitHub email: %s", exc)
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED) from exc


async def _download_profile_picture(picture_url: str, token: dict) -> str:
    """Download a profile picture and return a data-URI string.

    Returns ``"/user.png"`` on any error.
    """
    try:
        validate_url(picture_url)
    except (ValueError, Exception):
        picture_url = None
    if not picture_url:
        return "/user.png"

    access_token = token.get("access_token")
    get_kwargs: dict[str, Any] = {}
    if access_token:
        get_kwargs["headers"] = {"Authorization": f"Bearer {access_token}"}

    try:
        async with aiohttp.ClientSession() as session:
            # SSRF mitigation: do not follow redirects -- the picture_url
            # originates from an IdP claim and could 3xx to an internal host.
            async with session.get(
                picture_url, allow_redirects=False, **get_kwargs
            ) as resp:
                if not resp.ok:
                    return "/user.png"
                picture_bytes = await resp.read()
                encoded = base64.b64encode(picture_bytes).decode("utf-8")
                mime = mimetypes.guess_type(picture_url)[0] or "image/jpeg"
                return f"data:{mime};base64,{encoded}"
    except Exception as exc:
        log.error("Error downloading profile image '%s': %s", picture_url, exc)
        return "/user.png"


def _update_group_membership(
    group_model: GroupModel,
    user_ids: list[str],
    default_permissions: dict,
) -> None:
    """Persist updated *user_ids* for a group, initialising permissions if needed."""
    permissions = group_model.permissions or default_permissions
    update_form = GroupUpdateForm(
        name=group_model.name,
        description=group_model.description,
        permissions=permissions,
        user_ids=user_ids,
    )
    Groups.update_group_by_id(id=group_model.id, form_data=update_form, overwrite=False)


# ---------------------------------------------------------------------------
# OAuthManager
# ---------------------------------------------------------------------------


class OAuthManager:
    """Registers OAuth providers and handles the full login/callback lifecycle."""

    def __init__(self, app: Any) -> None:
        self.oauth = OAuth()
        self.app = app
        for _name, provider_config in OAUTH_PROVIDERS.items():
            provider_config["register"](self.oauth)

    def get_client(self, provider_name: str):
        """Return the authlib OAuth client for *provider_name*, or ``None``."""
        return self.oauth.create_client(provider_name)

    # ------------------------------------------------------------------
    # Role resolution
    # ------------------------------------------------------------------

    def get_user_role(self, user: Any, user_data: dict) -> str:
        """Determine the role to assign for a given *user* and *user_data*.

        Logic order:
        1. First/only user always gets ``"admin"``.
        2. If OAuth role management is enabled, roles are extracted from
           *user_data* and mapped against configured allowed/admin roles.
        3. Otherwise the default role (new users) or existing role is kept.
        """
        if user and Users.get_num_users() == 1:
            log.debug("Only user on instance -- assigning admin role")
            return "admin"
        if not user and Users.get_num_users() == 0:
            log.debug("First user on instance -- assigning admin role")
            return "admin"

        if auth_manager_config.ENABLE_OAUTH_ROLE_MANAGEMENT:
            return self._resolve_role_from_claims(user, user_data)

        # Role management disabled
        if not user:
            return auth_manager_config.DEFAULT_USER_ROLE
        return user.role

    def _resolve_role_from_claims(self, user: Any, user_data: dict) -> str:
        """Map OAuth role claims to a BCGPT role string."""
        claim_path = auth_manager_config.OAUTH_ROLES_CLAIM
        allowed_roles = auth_manager_config.OAUTH_ALLOWED_ROLES
        admin_roles = auth_manager_config.OAUTH_ADMIN_ROLES
        role = auth_manager_config.DEFAULT_USER_ROLE

        oauth_roles: list[str] = []
        if claim_path and allowed_roles and admin_roles:
            oauth_roles = _resolve_nested_claim(user_data, claim_path)

        log.debug("OAuth roles claim: %s", claim_path)
        log.debug("User roles from OAuth: %s", oauth_roles)
        log.debug("Allowed user roles: %s", allowed_roles)
        log.debug("Allowed admin roles: %s", admin_roles)

        if oauth_roles:
            for allowed in allowed_roles:
                if allowed in oauth_roles:
                    log.debug("Matched allowed user role")
                    role = "user"
                    break
            for admin in admin_roles:
                if admin in oauth_roles:
                    log.debug("Matched admin role")
                    role = "admin"
                    break

        return role

    # ------------------------------------------------------------------
    # Group synchronisation
    # ------------------------------------------------------------------

    def update_user_groups(
        self, user: Any, user_data: dict, default_permissions: dict
    ) -> None:
        """Synchronise the user's group memberships with their OAuth groups claim.

        Removes the user from groups no longer present in the claim and adds
        them to newly matching groups.  Admin users are exempt.
        """
        log.debug("Running OAuth group management")
        claim_path = auth_manager_config.OAUTH_GROUPS_CLAIM
        oauth_group_names = _resolve_nested_claim(user_data, claim_path)

        current_groups: list[GroupModel] = Groups.get_groups_by_member_id(user.id)
        all_groups: list[GroupModel] = Groups.get_groups()

        log.debug("OAuth groups claim: %s", claim_path)
        log.debug("User OAuth groups: %s", oauth_group_names)
        log.debug("Current groups: %s", [g.name for g in current_groups])
        log.debug("All available groups: %s", [g.name for g in all_groups])

        # Remove from groups no longer in the claim
        for group in current_groups:
            if oauth_group_names and group.name not in oauth_group_names:
                log.debug("Removing user from group '%s'", group.name)
                remaining = [uid for uid in group.user_ids if uid != user.id]
                _update_group_membership(group, remaining, default_permissions)

        # Add to new groups
        current_names = {g.name for g in current_groups}
        for group in all_groups:
            if (
                oauth_group_names
                and group.name in oauth_group_names
                and group.name not in current_names
            ):
                log.debug("Adding user to group '%s'", group.name)
                _update_group_membership(
                    group, group.user_ids + [user.id], default_permissions
                )

    # ------------------------------------------------------------------
    # Login redirect
    # ------------------------------------------------------------------

    async def handle_login(self, request, provider: str):
        """Redirect the user to the OAuth provider's authorisation endpoint."""
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(404)

        redirect_uri = OAUTH_PROVIDERS[provider].get("redirect_uri") or request.url_for(
            "oauth_callback", provider=provider
        )
        client = self.get_client(provider)
        if client is None:
            raise HTTPException(404)
        return await client.authorize_redirect(request, redirect_uri)

    # ------------------------------------------------------------------
    # Callback processing
    # ------------------------------------------------------------------

    async def handle_callback(self, request, provider: str, response):
        """Process the OAuth callback and issue a JWT cookie.

        Flow:
        1. Exchange the authorisation code for tokens.
        2. Extract user info (sub, email, etc.).
        3. Optionally merge with an existing local account.
        4. Create a new user when signup is enabled.
        5. Apply role and group management.
        6. Set JWT cookie and redirect to the frontend.
        """
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(404)

        client = self.get_client(provider)

        # -- token exchange --------------------------------------------------
        try:
            token = await client.authorize_access_token(request)
        except Exception as exc:
            log.warning("OAuth callback error: %s", exc)
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED) from exc

        # -- user info -------------------------------------------------------
        user_data: UserInfo = token.get("userinfo")
        email_claim = auth_manager_config.OAUTH_EMAIL_CLAIM
        if not user_data or email_claim not in user_data:
            user_data = await client.userinfo(token=token)
        if not user_data:
            keys = list(token.keys()) if isinstance(token, dict) else "n/a"
            log.warning("OAuth callback failed -- missing user data (token keys: %s)", keys)
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        # -- sub claim --------------------------------------------------------
        sub = user_data.get(OAUTH_PROVIDERS[provider].get("sub_claim", "sub"))
        if not sub:
            keys = list(user_data.keys()) if isinstance(user_data, dict) else "n/a"
            log.warning("OAuth callback failed -- missing sub (keys: %s)", keys)
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        provider_sub = f"{provider}@{sub}"

        # -- email ------------------------------------------------------------
        email = user_data.get(email_claim, "")
        if not email:
            if provider == "github":
                email = await _fetch_github_email(token)
            else:
                log.warning("OAuth callback failed -- missing email: %s", user_data)
                raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        email = email.lower()

        # -- domain allowlist -------------------------------------------------
        allowed_domains = auth_manager_config.OAUTH_ALLOWED_DOMAINS
        if "*" not in allowed_domains and email.split("@")[-1] not in allowed_domains:
            log.warning("OAuth callback failed -- domain not allowed: %s", email)
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        # -- existing user lookup ---------------------------------------------
        user = Users.get_user_by_oauth_sub(provider_sub)

        if not user and auth_manager_config.OAUTH_MERGE_ACCOUNTS_BY_EMAIL:
            if not _is_email_verified(user_data, provider):
                log.warning(
                    "OAuth merge-by-email skipped for %s: email not verified by provider",
                    email,
                )
            else:
                user = Users.get_user_by_email(email)
                if user:
                    Users.update_user_oauth_sub_by_id(user.id, provider_sub)

        # -- role sync for returning users ------------------------------------
        if user:
            determined_role = self.get_user_role(user, user_data)
            if user.role != determined_role:
                Users.update_user_role_by_id(user.id, determined_role)

        # -- new user creation ------------------------------------------------
        if not user:
            user = await self._provision_new_user(
                request, provider, token, user_data, email, provider_sub
            )

        # -- JWT issuance -----------------------------------------------------
        auth = Auths.get_auth_by_user_id(user.id)
        jwt_token = create_token(
            data={"id": user.id, "tv": auth.token_version if auth else 0},
            expires_delta=parse_duration(auth_manager_config.JWT_EXPIRES_IN),
        )

        # -- group sync -------------------------------------------------------
        if auth_manager_config.ENABLE_OAUTH_GROUP_MANAGEMENT and user.role != "admin":
            self.update_user_groups(
                user=user,
                user_data=user_data,
                default_permissions=request.app.state.config.USER_PERMISSIONS,
            )

        # -- cookie & redirect ------------------------------------------------
        response.set_cookie(
            key="token",
            value=jwt_token,
            httponly=True,
            samesite=BCGPT_AUTH_COOKIE_SAME_SITE,
            secure=BCGPT_AUTH_COOKIE_SECURE,
        )

        if ENABLE_OAUTH_SIGNUP.value:
            response.set_cookie(
                key="oauth_id_token",
                value=token.get("id_token"),
                httponly=True,
                samesite=BCGPT_AUTH_COOKIE_SAME_SITE,
                secure=BCGPT_AUTH_COOKIE_SECURE,
            )

        redirect_url = f"{request.base_url}auth"
        return RedirectResponse(url=redirect_url, headers=response.headers)

    # ------------------------------------------------------------------
    # User provisioning (private)
    # ------------------------------------------------------------------

    async def _provision_new_user(
        self,
        request,
        provider: str,
        token: dict,
        user_data: dict,
        email: str,
        provider_sub: str,
    ):
        """Create a new user from OAuth data.

        Raises ``HTTPException(403)`` when signups are disabled or
        ``HTTPException(400)`` when the email is already taken.
        """
        if not auth_manager_config.ENABLE_OAUTH_SIGNUP:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )

        if Users.get_user_by_email(email):
            raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

        # -- profile picture --------------------------------------------------
        picture_claim = auth_manager_config.OAUTH_PICTURE_CLAIM
        picture_url: str | None = user_data.get(
            picture_claim, OAUTH_PROVIDERS[provider].get("picture_url", "")
        )
        if picture_url:
            picture_url = await _download_profile_picture(picture_url, token)
        if not picture_url:
            picture_url = "/user.png"

        # -- username ---------------------------------------------------------
        username_claim = auth_manager_config.OAUTH_USERNAME_CLAIM
        name = user_data.get(username_claim)
        if not name:
            log.warning("Username claim missing -- using email as name")
            name = email

        # -- role -------------------------------------------------------------
        role = self.get_user_role(None, user_data)

        # -- persist ----------------------------------------------------------
        user = Auths.insert_new_auth(
            email=email,
            password=get_password_hash(str(uuid.uuid4())),
            name=name,
            profile_image_url=picture_url,
            role=role,
            oauth_sub=provider_sub,
        )

        # -- webhook notification ---------------------------------------------
        if auth_manager_config.WEBHOOK_URL:
            post_webhook(
                BCGPT_APP_NAME,
                auth_manager_config.WEBHOOK_URL,
                WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                {
                    "action": "signup",
                    "message": WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                    "user": user.model_dump_json(exclude_none=True),
                },
            )

        return user
