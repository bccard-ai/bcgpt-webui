"""Authentication and authorization router.

Handles session management, credential-based sign-in/sign-up, LDAP
authentication, API-key lifecycle, and administrative configuration
(logo uploads, LDAP settings, feature toggles).
"""

from __future__ import annotations

import datetime
import ipaddress
import logging
import os
import re
import shutil
import time
import uuid
from ssl import CERT_REQUIRED, PROTOCOL_TLS
from typing import Optional

from aiohttp import ClientSession
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from bcgpt.config import (
    ENABLE_LDAP,
    ENABLE_OAUTH_SIGNUP,
    OPENID_PROVIDER_URL,
    BCGPT_LOGO_URL,
    BCGPT_APP_NAME_PERSISTENT,
)
from bcgpt.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from bcgpt.env import (
    SRC_LOG_LEVELS,
    BCGPT_AUTH,
    BCGPT_AUTH_COOKIE_SAME_SITE,
    BCGPT_AUTH_COOKIE_SECURE,
    BCGPT_AUTH_TRUSTED_EMAIL_HEADER,
    BCGPT_AUTH_TRUSTED_NAME_HEADER,
    BCGPT_AUTH_TRUSTED_PROXY_IPS,
)
from bcgpt.models import Users
from bcgpt.models.auths import (
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_DURATION,
    AddUserForm,
    ApiKey,
    Auths,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    Token,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from bcgpt.utils import get_permissions, parse_duration, post_webhook
from bcgpt.utils import validate_email_format
from bcgpt.utils.auth import (
    create_api_key,
    create_token,
    decode_token,
    get_admin_user,
    get_current_user,
    get_password_hash,
    get_verified_user,
)

if ENABLE_LDAP.value:
    from ldap3 import NONE, Connection, Server, Tls
    from ldap3.utils.conv import escape_filter_chars

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "123456",
        "12345678",
        "qwerty",
        "abc123",
        "monkey",
        "1234567",
        "letmein",
        "trustno1",
        "dragon",
        "baseball",
        "iloveyou",
        "master",
        "sunshine",
        "ashley",
        "bailey",
        "passw0rd",
        "shadow",
        "123123",
        "654321",
        "superman",
        "qazwsx",
        "michael",
        "football",
        "password1",
        "password123",
        "batman",
        "admin",
        "admin123",
        "welcome",
        "hello",
        "charlie",
        "donald",
        "login",
        "qwerty123",
        "mustang",
        "access",
        "secret",
        "p@ssw0rd",
        "p@ssword",
    }
)


def validate_password_strength(password: str) -> str:
    """Reject passwords that are too short, too long, or commonly used.

    Returns *password* unchanged when acceptable.
    """
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {PASSWORD_MIN_LENGTH} characters",
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {PASSWORD_MAX_LENGTH} characters",
        )
    if password.lower() in _COMMON_PASSWORDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too common. Please choose a stronger password.",
        )
    return password


# ---------------------------------------------------------------------------
# Response / config models
# ---------------------------------------------------------------------------


class SessionUserResponse(Token, UserResponse):
    """Combined token + user payload returned by sign-in / sign-up flows."""

    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


class AdminConfig(BaseModel):
    """Full admin configuration form."""

    SHOW_ADMIN_DETAILS: bool
    BCGPT_URL: str
    ENABLE_SIGNUP: bool
    ENABLE_API_KEY: bool
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS: bool
    API_KEY_ALLOWED_ENDPOINTS: str
    DEFAULT_USER_ROLE: str
    JWT_EXPIRES_IN: str
    ENABLE_COMMUNITY_SHARING: bool
    ENABLE_MESSAGE_RATING: bool
    ENABLE_CHANNELS: bool
    ENABLE_USER_WEBHOOKS: bool
    logo_url: str
    name: str


class LdapServerConfig(BaseModel):
    """LDAP server connection settings."""

    label: str
    host: str
    port: Optional[int] = None
    attribute_for_mail: str = "mail"
    attribute_for_username: str = "uid"
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ""
    use_tls: bool = True
    certificate_path: Optional[str] = None
    ciphers: Optional[str] = "ALL"


class LdapConfigForm(BaseModel):
    """Toggle LDAP on/off."""

    enable_ldap: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers — trusted proxy
# ---------------------------------------------------------------------------


def _is_trusted_proxy(request: Request) -> bool:
    """Return True when the direct peer IP is allowed to set trusted auth headers.

    If no allowlist is configured the check is not enforced (relies on network
    isolation; a startup warning is emitted elsewhere).
    """
    if not BCGPT_AUTH_TRUSTED_PROXY_IPS:
        return True
    client_host = request.client.host if request.client else None
    if not client_host:
        return False
    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    for entry in BCGPT_AUTH_TRUSTED_PROXY_IPS:
        try:
            if "/" in entry:
                if client_ip in ipaddress.ip_network(entry, strict=False):
                    return True
            elif client_ip == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# Helpers — token & cookie creation
# ---------------------------------------------------------------------------


def _build_session_payload(
    user,
    token: str,
    expires_at: int | None,
    permissions: dict | None,
) -> dict:
    """Construct the dict returned by every sign-in / sign-up / session endpoint."""
    payload: dict = {
        "token": token,
        "token_type": "Bearer",
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at
    if permissions is not None:
        payload["permissions"] = permissions
    return payload


def _issue_token(
    user, jwt_expires_in: str | None
) -> tuple[str, int | None, datetime.datetime | None]:
    """Create a JWT for *user* and derive the cookie expiry.

    Returns ``(token, expires_at_epoch, datetime_expires_at)``.
    """
    expires_delta = parse_duration(jwt_expires_in) if jwt_expires_in else None
    expires_at: int | None = None
    datetime_expires_at: datetime.datetime | None = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())
        datetime_expires_at = datetime.datetime.fromtimestamp(
            expires_at, datetime.timezone.utc
        )

    auth = Auths.get_auth_by_user_id(user.id)
    token = create_token(
        data={"id": user.id, "tv": auth.token_version if auth else 0},
        expires_delta=expires_delta,
    )
    return token, expires_at, datetime_expires_at


def _set_token_cookie(
    response: Response,
    token: str,
    datetime_expires_at: datetime.datetime | None,
) -> None:
    """Write the httponly session cookie."""
    response.set_cookie(
        key="token",
        value=token,
        expires=datetime_expires_at,
        httponly=True,
        samesite=BCGPT_AUTH_COOKIE_SAME_SITE,
        secure=BCGPT_AUTH_COOKIE_SECURE,
    )


def _get_permissions_for(user, config) -> dict:
    """Resolve the permissions dict for *user* from app config."""
    return get_permissions(user.id, config.USER_PERMISSIONS)


# ---------------------------------------------------------------------------
# Helpers — user creation
# ---------------------------------------------------------------------------


def _determine_role(user_count: int, default_role: str) -> str:
    """First user becomes admin; later users get *default_role*."""
    return "admin" if user_count == 0 else default_role


def _validate_new_email(email: str) -> None:
    """Raise 400 if *email* is malformed or already registered."""
    if not validate_email_format(email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT,
        )
    if Users.get_user_by_email(email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
):
    """Return the current session user, refreshing the JWT cookie."""
    token, expires_at, dt_expires = _issue_token(
        user, request.app.state.config.JWT_EXPIRES_IN
    )
    _set_token_cookie(response, token, dt_expires)

    permissions = _get_permissions_for(user, request.app.state.config)
    return _build_session_payload(user, token, expires_at, permissions)


# ---------------------------------------------------------------------------
# Profile / password updates
# ---------------------------------------------------------------------------


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm,
    session_user=Depends(get_verified_user),
):
    """Update the current user's display name and avatar."""
    if not session_user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
    user = Users.update_user_by_id(
        session_user.id,
        {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
    )
    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    return user


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm,
    session_user=Depends(get_current_user),
):
    """Change the current user's password after verifying the old one."""
    if BCGPT_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if not session_user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    user = Auths.authenticate_user(session_user.email, form_data.password)
    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_PASSWORD)

    validate_password_strength(form_data.new_password)
    hashed = get_password_hash(form_data.new_password)
    result = Auths.update_user_password_by_id(user.id, hashed)
    if result:
        Auths.increment_token_version(user.id)
        Users.update_user_api_key_by_id(user.id, None)
    return result


# ---------------------------------------------------------------------------
# LDAP authentication
# ---------------------------------------------------------------------------


@router.post("/ldap", response_model=SessionUserResponse)
async def ldap_auth(
    request: Request,
    response: Response,
    form_data: LdapForm,
):
    """Authenticate against an LDAP directory and create a local session.

    On first successful bind the user is auto-provisioned with the default
    role (or *admin* for the very first user).
    """
    cfg = request.app.state.config
    if not cfg.ENABLE_LDAP:
        raise HTTPException(400, detail="LDAP authentication is not enabled")

    ldap_tls = _build_ldap_tls(cfg)
    server = Server(
        host=cfg.LDAP_SERVER_HOST,
        port=cfg.LDAP_SERVER_PORT,
        get_info=NONE,
        use_ssl=cfg.LDAP_USE_TLS,
        tls=ldap_tls,
    )
    _ldap_app_bind(server, cfg)

    entry = _ldap_search_user(server, cfg, form_data.user)
    username, email, cn = _ldap_extract_fields(entry, cfg, form_data.user)
    _ldap_user_bind(server, entry.entry_dn, form_data.password, form_data.user)

    # Auto-provision if the LDAP user does not exist locally yet.
    user = Users.get_user_by_email(email)
    if not user:
        user = _ldap_auto_provision(request, cn, email)

    user = Auths.authenticate_user_by_trusted_header(email)
    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    token, expires_at, dt_expires = _issue_token(user, cfg.JWT_EXPIRES_IN)
    response.set_cookie(key="token", value=token, httponly=True)

    permissions = _get_permissions_for(user, cfg)
    return _build_session_payload(user, token, expires_at, permissions)


def _build_ldap_tls(cfg):
    """Construct a TLS object from the stored LDAP configuration."""
    try:
        return Tls(
            validate=CERT_REQUIRED,
            version=PROTOCOL_TLS,
            ca_certs_file=cfg.LDAP_CA_CERT_FILE,
            ciphers=cfg.LDAP_CIPHERS if cfg.LDAP_CIPHERS else "ALL",
        )
    except Exception:
        log.exception("LDAP TLS configuration error")
        raise HTTPException(401, detail="LDAP authentication failed")


def _ldap_app_bind(server, cfg) -> None:
    """Bind the application-level LDAP account."""
    conn = Connection(
        server,
        cfg.LDAP_APP_DN,
        cfg.LDAP_APP_PASSWORD,
        auto_bind="NONE",
        authentication="SIMPLE" if cfg.LDAP_APP_DN else "ANONYMOUS",
    )
    if not conn.bind():
        log.warning("LDAP application account bind failed")
        raise HTTPException(401, detail="LDAP authentication failed")


def _ldap_search_user(server, cfg, username: str):
    """Search for the LDAP entry matching *username*."""
    conn = Connection(
        server,
        cfg.LDAP_APP_DN,
        cfg.LDAP_APP_PASSWORD,
        auto_bind="NONE",
        authentication="SIMPLE" if cfg.LDAP_APP_DN else "ANONYMOUS",
    )
    if not conn.bind():
        raise HTTPException(401, detail="LDAP authentication failed")

    search_ok = conn.search(
        search_base=cfg.LDAP_SEARCH_BASE,
        search_filter=(
            f"(&({cfg.LDAP_ATTRIBUTE_FOR_USERNAME}="
            f"{escape_filter_chars(username.lower())})"
            f"{cfg.LDAP_SEARCH_FILTERS})"
        ),
        attributes=[
            cfg.LDAP_ATTRIBUTE_FOR_USERNAME,
            cfg.LDAP_ATTRIBUTE_FOR_MAIL,
            "cn",
        ],
    )
    if not search_ok:
        log.debug("LDAP search found no entry for user %s", username)
        raise HTTPException(401, detail="LDAP authentication failed")
    return conn.entries[0]


def _ldap_extract_fields(entry, cfg, supplied_user: str) -> tuple[str, str, str]:
    """Pull username, email and cn from the LDAP entry.

    Returns ``(username, email, cn)`` or raises 401 on missing data.
    """
    username = str(entry[cfg.LDAP_ATTRIBUTE_FOR_USERNAME]).lower()
    email = str(entry[cfg.LDAP_ATTRIBUTE_FOR_MAIL])
    if not email or email in ("", "[]"):
        log.debug("LDAP user %s has no email attribute", supplied_user)
        raise HTTPException(401, detail="LDAP authentication failed")
    email = email.lower()

    if username != supplied_user.lower():
        log.debug(
            "LDAP username mismatch for %s: expected %s, got %s",
            supplied_user,
            supplied_user.lower(),
            str(entry[cfg.LDAP_ATTRIBUTE_FOR_USERNAME]),
        )
        raise HTTPException(401, detail="LDAP authentication failed")

    cn = str(entry["cn"])
    return username, email, cn


def _ldap_user_bind(server, user_dn: str, password: str, username: str) -> None:
    """Attempt a direct bind as the LDAP user to verify the password."""
    if not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.INVALID_CRED,
        )
    conn = Connection(
        server, user_dn, password, auto_bind="NONE", authentication="SIMPLE"
    )
    if not conn.bind():
        log.debug("LDAP user bind failed for user %s", username)
        raise HTTPException(401, detail="LDAP authentication failed")


def _ldap_auto_provision(request, cn: str, email: str):
    """Create a local user record for a first-time LDAP login."""
    user_count = Users.get_num_users()
    role = _determine_role(user_count, request.app.state.config.DEFAULT_USER_ROLE)
    user = Auths.insert_new_auth(
        email=email,
        password=str(uuid.uuid4()),
        name=cn,
        role=role,
    )
    if not user:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    return user


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------


@router.post("/signin", response_model=SessionUserResponse)
async def signin(
    request: Request,
    response: Response,
    form_data: SigninForm,
):
    """Authenticate a user via trusted header, no-auth mode, or credentials."""
    # --- Trusted-header auth (reverse proxy injection) --------------------
    if BCGPT_AUTH_TRUSTED_EMAIL_HEADER:
        user = await _signin_trusted_header(request, response)
        if not user:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        token, expires_at, dt_expires = _issue_token(
            user, request.app.state.config.JWT_EXPIRES_IN
        )
        _set_token_cookie(response, token, dt_expires)
        permissions = _get_permissions_for(user, request.app.state.config)
        return _build_session_payload(user, token, expires_at, permissions)

    # --- No-auth mode (auto-admin) ----------------------------------------
    if BCGPT_AUTH is False:
        user = await _signin_no_auth(request, response)
        if not user:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        token, expires_at, dt_expires = _issue_token(
            user, request.app.state.config.JWT_EXPIRES_IN
        )
        _set_token_cookie(response, token, dt_expires)
        permissions = _get_permissions_for(user, request.app.state.config)
        return _build_session_payload(user, token, expires_at, permissions)

    # --- Interactive email / password login -------------------------------
    is_locked, locked_until = Auths.is_account_locked(form_data.email.lower())
    user = Auths.authenticate_user(form_data.email.lower(), form_data.password)

    if not user:
        if not is_locked:
            Auths.increment_failed_attempts(form_data.email.lower())
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    if is_locked:
        remaining = max(1, (locked_until - int(time.time())) // 60)
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCOUNT_LOCKED(str(remaining)),
        )

    Auths.reset_failed_attempts(user.id)

    # --- MFA (TOTP) gate (open-moai adoption 2.5) -------------------------
    if request.app.state.config.MFA_ENABLED:
        from bcgpt.models.user_mfa import UserMFAs

        if UserMFAs.is_enabled(user.id):
            if not form_data.totp_code:
                # Password OK but a second factor is required. Detail is a plain
                # string ("mfa_required") so the API client preserves it and the
                # frontend can match on it to show the TOTP step.
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    detail="mfa_required",
                )
            if not UserMFAs.verify_code(user.id, form_data.totp_code):
                Auths.increment_failed_attempts(form_data.email.lower())
                raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    token, expires_at, dt_expires = _issue_token(
        user, request.app.state.config.JWT_EXPIRES_IN
    )
    _set_token_cookie(response, token, dt_expires)
    permissions = _get_permissions_for(user, request.app.state.config)
    payload = _build_session_payload(user, token, expires_at, permissions)
    # Flag un-enrolled admins so the UI can prompt enrollment (no lockout).
    if request.app.state.config.MFA_REQUIRED_FOR_ADMIN and user.role == "admin":
        from bcgpt.models.user_mfa import UserMFAs

        if not UserMFAs.is_enabled(user.id):
            payload["mfa_enrollment_required"] = True
    return payload


############################
# JWKS — RS256 public key set (open-moai adoption 3.4)
############################


@router.get("/jwks")
async def get_jwks_endpoint():
    """Public JSON Web Key Set for verifying RS256-signed session tokens.

    Empty when running HS256 (a symmetric secret is never published). IdPs /
    resource servers fetch this at ``/api/v1/auths/jwks``.
    """
    from bcgpt.utils.auth import get_jwks

    return get_jwks()


############################
# MFA (TOTP) management — open-moai adoption 2.5
############################


class MFAVerifyForm(BaseModel):
    code: str


@router.get("/mfa/status")
async def mfa_status(user=Depends(get_verified_user)):
    """Return whether the current user has MFA enabled + backup codes left."""
    from bcgpt.models.user_mfa import UserMFAs

    return {
        "enabled": UserMFAs.is_enabled(user.id),
        "backup_codes_remaining": UserMFAs.backup_codes_remaining(user.id),
    }


@router.post("/mfa/enroll")
async def mfa_enroll(user=Depends(get_verified_user)):
    """Begin TOTP enrollment: returns the secret + otpauth provisioning URI.

    MFA is NOT active until the user confirms a code via ``/mfa/verify``.
    """
    from bcgpt.models.user_mfa import UserMFAs

    data = UserMFAs.start_enrollment(user.id, user.email)
    if not data:
        raise HTTPException(500, detail="Failed to start MFA enrollment")
    # Render a scannable QR (SVG data URI) server-side so the frontend needs no
    # QR dependency; falls back to manual secret entry if rendering fails.
    try:
        import segno

        data["qr_svg"] = segno.make(data["provisioning_uri"], error="m").svg_data_uri(
            scale=4
        )
    except Exception as e:
        log.warning("Failed to render MFA QR: %s", e)
        data["qr_svg"] = None
    return data


@router.post("/mfa/verify")
async def mfa_verify(form_data: MFAVerifyForm, user=Depends(get_verified_user)):
    """Confirm enrollment with a TOTP code; enables MFA and returns one-time
    backup codes (shown only once)."""
    from bcgpt.models.user_mfa import UserMFAs

    result = UserMFAs.verify_and_enable(user.id, form_data.code)
    if not result:
        raise HTTPException(400, detail="Invalid MFA code")
    return result


@router.post("/mfa/disable")
async def mfa_disable(form_data: MFAVerifyForm, user=Depends(get_verified_user)):
    """Disable MFA for the current user (requires a valid current TOTP/backup
    code to prevent a hijacked session from removing the second factor)."""
    from bcgpt.models.user_mfa import UserMFAs

    if not UserMFAs.is_enabled(user.id):
        return {"success": True}
    if not UserMFAs.verify_code(user.id, form_data.code):
        raise HTTPException(400, detail="Invalid MFA code")
    return {"success": UserMFAs.disable(user.id)}


async def _signin_trusted_header(request: Request, response: Response):
    """Authenticate via a reverse-proxy injected trusted email header."""
    if not _is_trusted_proxy(request):
        log.warning(
            "Rejected trusted-header login from untrusted peer %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(403, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

    if BCGPT_AUTH_TRUSTED_EMAIL_HEADER not in request.headers:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

    trusted_email = request.headers[BCGPT_AUTH_TRUSTED_EMAIL_HEADER].lower()
    trusted_name = trusted_email
    if BCGPT_AUTH_TRUSTED_NAME_HEADER:
        trusted_name = request.headers.get(
            BCGPT_AUTH_TRUSTED_NAME_HEADER, trusted_email
        )

    if not Users.get_user_by_email(trusted_email):
        await signup(
            request,
            response,
            SignupForm(
                email=trusted_email, password=str(uuid.uuid4()), name=trusted_name
            ),
        )
    return Auths.authenticate_user_by_trusted_header(trusted_email)


async def _signin_no_auth(request: Request, response: Response):
    """Authenticate against the built-in admin account when auth is disabled."""
    admin_email = "admin@localhost"
    admin_password = "admin"

    if Users.get_user_by_email(admin_email.lower()):
        return Auths.authenticate_user(admin_email.lower(), admin_password)

    if Users.get_num_users() != 0:
        raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

    await signup(
        request,
        response,
        SignupForm(email=admin_email, password=admin_password, name="User"),
    )
    return Auths.authenticate_user(admin_email.lower(), admin_password)


# ---------------------------------------------------------------------------
# Sign-up
# ---------------------------------------------------------------------------


@router.post("/signup", response_model=SessionUserResponse)
async def signup(
    request: Request,
    response: Response,
    form_data: SignupForm,
):
    """Register a new user account and return an authenticated session."""
    _check_signup_allowed(request, form_data)

    user_count = Users.get_num_users()
    _validate_new_email(form_data.email)

    try:
        role = _determine_role(user_count, request.app.state.config.DEFAULT_USER_ROLE)

        validate_password_strength(form_data.password)
        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            role,
        )

        if not user:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

        # Lock signup only once the first admin account actually exists;
        # flipping it earlier bricks onboarding if this request fails midway.
        if user_count == 0:
            request.app.state.config.ENABLE_SIGNUP = False

        token, expires_at, dt_expires = _issue_token(
            user, request.app.state.config.JWT_EXPIRES_IN
        )
        _set_token_cookie(response, token, dt_expires)

        _fire_signup_webhook(request, user)

        permissions = _get_permissions_for(user, request.app.state.config)
        return _build_session_payload(user, token, expires_at, permissions)

    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


def _check_signup_allowed(request: Request, form_data: SignupForm) -> None:
    """Raise 403 if signup is disabled or conditions are not met."""
    if BCGPT_AUTH:
        if (
            not request.app.state.config.ENABLE_SIGNUP
            or not request.app.state.config.ENABLE_LOGIN_FORM
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
    else:
        if Users.get_num_users() != 0:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )


def _fire_signup_webhook(request: Request, user) -> None:
    """Dispatch the user-signup webhook if configured."""
    cfg = request.app.state.config
    if not cfg.WEBHOOK_URL:
        return
    post_webhook(
        request.app.state.BCGPT_APP_NAME,
        cfg.WEBHOOK_URL,
        WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
        {
            "action": "signup",
            "message": WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
            "user": user.model_dump_json(exclude_none=True),
        },
    )


# ---------------------------------------------------------------------------
# Sign-out
# ---------------------------------------------------------------------------


@router.get("/signout")
async def signout(request: Request, response: Response):
    """Invalidate the current session token and clear cookies."""
    _invalidate_session_token(request)

    response.delete_cookie("token")

    if ENABLE_OAUTH_SIGNUP.value:
        redirect = await _maybe_oidc_logout(request, response)
        if redirect:
            return redirect

    return {"status": True}


def _invalidate_session_token(request: Request) -> None:
    """Bump the token version so any outstanding JWT is no longer valid."""
    try:
        token: str | None = None
        if "token" in request.cookies:
            token = request.cookies.get("token")
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if token:
            data = decode_token(token)
            if data and "id" in data:
                auth = Auths.get_auth_by_user_id(data["id"])
                # A stale tab can carry an older, already-revoked JWT. It must
                # not revoke the newer session by incrementing token_version
                # again during its best-effort sign-out request.
                if auth is None or auth.token_version == data.get("tv", 0):
                    Auths.increment_token_version(data["id"])
    except Exception:
        pass


async def _maybe_oidc_logout(
    request: Request, response: Response
) -> RedirectResponse | None:
    """Attempt an OpenID Connect back-channel logout."""
    oauth_id_token = request.cookies.get("oauth_id_token")
    if not oauth_id_token:
        return None

    try:
        async with ClientSession() as session:
            async with session.get(OPENID_PROVIDER_URL.value) as resp:
                if resp.status != 200:
                    raise HTTPException(
                        status_code=resp.status,
                        detail="Failed to fetch OpenID configuration",
                    )
                openid_data = await resp.json()
                logout_url = openid_data.get("end_session_endpoint")
                if logout_url:
                    response.delete_cookie("oauth_id_token")
                    return RedirectResponse(
                        headers=response.headers,
                        url=f"{logout_url}?id_token_hint={oauth_id_token}",
                    )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return None


# ---------------------------------------------------------------------------
# Admin — add user
# ---------------------------------------------------------------------------


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    """Create a new user (admin only) and return credentials."""
    _validate_new_email(form_data.email)

    try:
        validate_password_strength(form_data.password)
        hashed = get_password_hash(form_data.password)
        new_user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            form_data.role,
        )

        if not new_user:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

        auth = Auths.get_auth_by_user_id(new_user.id)
        token = create_token(
            data={"id": new_user.id, "tv": auth.token_version if auth else 0}
        )
        return {
            "token": token,
            "token_type": "Bearer",
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role,
            "profile_image_url": new_user.profile_image_url,
        }
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


# ---------------------------------------------------------------------------
# Admin — details
# ---------------------------------------------------------------------------


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_verified_user)):
    """Return the admin contact information (email / name)."""
    if not request.app.state.config.SHOW_ADMIN_DETAILS:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    admin_email = request.app.state.config.ADMIN_EMAIL
    admin_name = None

    if admin_email:
        admin = Users.get_user_by_email(admin_email)
        if admin:
            admin_name = admin.name
    else:
        admin = Users.get_first_user()
        if admin:
            admin_email = admin.email
            admin_name = admin.name

    log.info("Admin details - Email: %s, Name: %s", admin_email, admin_name)
    return {"name": admin_name, "email": admin_email}


# ---------------------------------------------------------------------------
# Admin — config CRUD
# ---------------------------------------------------------------------------


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    """Return the full admin configuration blob."""
    return _serialize_admin_config(request)


@router.post("/admin/config")
async def update_admin_config(
    request: Request,
    form_data: AdminConfig,
    user=Depends(get_admin_user),
):
    """Persist admin configuration changes."""
    cfg = request.app.state.config
    cfg.SHOW_ADMIN_DETAILS = form_data.SHOW_ADMIN_DETAILS
    cfg.BCGPT_URL = form_data.BCGPT_URL
    cfg.ENABLE_SIGNUP = form_data.ENABLE_SIGNUP

    cfg.ENABLE_API_KEY = form_data.ENABLE_API_KEY
    cfg.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
        form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
    )
    cfg.API_KEY_ALLOWED_ENDPOINTS = form_data.API_KEY_ALLOWED_ENDPOINTS

    cfg.ENABLE_CHANNELS = form_data.ENABLE_CHANNELS

    if form_data.DEFAULT_USER_ROLE in ("pending", "user", "admin"):
        cfg.DEFAULT_USER_ROLE = form_data.DEFAULT_USER_ROLE

    if re.match(r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$", form_data.JWT_EXPIRES_IN):
        cfg.JWT_EXPIRES_IN = form_data.JWT_EXPIRES_IN

    cfg.ENABLE_COMMUNITY_SHARING = form_data.ENABLE_COMMUNITY_SHARING
    cfg.ENABLE_MESSAGE_RATING = form_data.ENABLE_MESSAGE_RATING
    cfg.ENABLE_USER_WEBHOOKS = form_data.ENABLE_USER_WEBHOOKS
    cfg.BCGPT_LOGO_URL = form_data.logo_url

    request.app.state.BCGPT_APP_NAME = form_data.name
    BCGPT_APP_NAME_PERSISTENT.value = form_data.name
    BCGPT_APP_NAME_PERSISTENT.save()

    return _serialize_admin_config(request)


def _serialize_admin_config(request: Request) -> dict:
    """Read the current config into the wire-format dict."""
    cfg = request.app.state.config
    return {
        "SHOW_ADMIN_DETAILS": cfg.SHOW_ADMIN_DETAILS,
        "BCGPT_URL": cfg.BCGPT_URL,
        "ENABLE_SIGNUP": cfg.ENABLE_SIGNUP,
        "ENABLE_API_KEY": cfg.ENABLE_API_KEY,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": cfg.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
        "API_KEY_ALLOWED_ENDPOINTS": cfg.API_KEY_ALLOWED_ENDPOINTS,
        "ENABLE_CHANNELS": cfg.ENABLE_CHANNELS,
        "DEFAULT_USER_ROLE": cfg.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": cfg.JWT_EXPIRES_IN,
        "ENABLE_COMMUNITY_SHARING": cfg.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": cfg.ENABLE_MESSAGE_RATING,
        "ENABLE_USER_WEBHOOKS": cfg.ENABLE_USER_WEBHOOKS,
        "logo_url": cfg.BCGPT_LOGO_URL,
        "name": request.app.state.BCGPT_APP_NAME,
    }


# ---------------------------------------------------------------------------
# Admin — logo upload / delete
# ---------------------------------------------------------------------------


_ALLOWED_IMAGE_EXTS: frozenset[str] = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
_FAVICON_NAMES: frozenset[str] = frozenset(
    {"favicon.png", "favicon.ico", "favicon-96x96.png"}
)


@router.post("/admin/logo")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_admin_user),
):
    """Upload a custom logo image and update all favicon variants."""
    from bcgpt.env import STATIC_DIR

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "png"
    if ext not in _ALLOWED_IMAGE_EXTS:
        ext = "png"

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    logo_filename = f"custom-logo.{ext}"
    logo_path = os.path.join(str(STATIC_DIR), logo_filename)
    _write_bytes(logo_path, contents)

    frontend_static_dir = STATIC_DIR.parent.parent.parent / "static" / "static"
    if frontend_static_dir.exists():
        _write_bytes(os.path.join(str(frontend_static_dir), logo_filename), contents)

    _deploy_favicons(logo_path, STATIC_DIR, frontend_static_dir)

    logo_url = f"/static/{logo_filename}"
    request.app.state.config.BCGPT_LOGO_URL = logo_url
    BCGPT_LOGO_URL.value = logo_url
    BCGPT_LOGO_URL.save()

    return {"logo_url": logo_url}


@router.delete("/admin/logo")
async def delete_logo(request: Request, user=Depends(get_admin_user)):
    """Remove the custom logo and restore default favicons."""
    from bcgpt.env import STATIC_DIR

    request.app.state.config.BCGPT_LOGO_URL = ""
    BCGPT_LOGO_URL.value = ""
    BCGPT_LOGO_URL.save()

    frontend_static_dir = STATIC_DIR.parent.parent.parent / "static" / "static"

    _remove_logo_files(STATIC_DIR, frontend_static_dir)
    _restore_default_favicons(STATIC_DIR, frontend_static_dir)

    return {"logo_url": ""}


def _write_bytes(path: str, data: bytes) -> None:
    """Write *data* to *path*."""
    with open(path, "wb") as fh:
        fh.write(data)


def _deploy_favicons(logo_path: str, static_dir, frontend_static_dir) -> None:
    """Copy the logo over all favicon files, backing up originals."""
    for target_dir in (static_dir, frontend_static_dir):
        if not target_dir.exists():
            continue
        for name in _FAVICON_NAMES:
            favicon_path = os.path.join(str(target_dir), name)
            if os.path.exists(favicon_path) and not os.path.exists(
                favicon_path + ".default"
            ):
                shutil.copy2(favicon_path, favicon_path + ".default")
            shutil.copy2(logo_path, favicon_path)


def _remove_logo_files(static_dir, frontend_static_dir) -> None:
    """Delete all custom-logo.* files from static directories."""
    for target_dir in (static_dir, frontend_static_dir):
        if not target_dir.exists():
            continue
        for ext in _ALLOWED_IMAGE_EXTS:
            logo_path = os.path.join(str(target_dir), f"custom-logo.{ext}")
            if os.path.exists(logo_path):
                os.remove(logo_path)


def _restore_default_favicons(static_dir, frontend_static_dir) -> None:
    """Restore .default backups over the current favicon files."""
    for target_dir in (static_dir, frontend_static_dir):
        if not target_dir.exists():
            continue
        for name in _FAVICON_NAMES:
            favicon_path = os.path.join(str(target_dir), name)
            default_path = favicon_path + ".default"
            if os.path.exists(default_path):
                shutil.move(default_path, favicon_path)


# ---------------------------------------------------------------------------
# Admin — LDAP configuration
# ---------------------------------------------------------------------------


@router.get("/admin/config/ldap/server", response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    """Return the current LDAP server configuration."""
    return _serialize_ldap_server_config(request)


@router.post("/admin/config/ldap/server")
async def update_ldap_server(
    request: Request,
    form_data: LdapServerConfig,
    user=Depends(get_admin_user),
):
    """Persist LDAP server connection settings."""
    _validate_ldap_server_form(form_data)

    cfg = request.app.state.config
    cfg.LDAP_SERVER_LABEL = form_data.label
    cfg.LDAP_SERVER_HOST = form_data.host
    cfg.LDAP_SERVER_PORT = form_data.port
    cfg.LDAP_ATTRIBUTE_FOR_MAIL = form_data.attribute_for_mail
    cfg.LDAP_ATTRIBUTE_FOR_USERNAME = form_data.attribute_for_username
    cfg.LDAP_APP_DN = form_data.app_dn
    cfg.LDAP_APP_PASSWORD = form_data.app_dn_password
    cfg.LDAP_SEARCH_BASE = form_data.search_base
    cfg.LDAP_SEARCH_FILTERS = form_data.search_filters
    cfg.LDAP_USE_TLS = form_data.use_tls
    cfg.LDAP_CA_CERT_FILE = form_data.certificate_path
    cfg.LDAP_CIPHERS = form_data.ciphers

    return _serialize_ldap_server_config(request)


def _validate_ldap_server_form(form_data: LdapServerConfig) -> None:
    """Reject incomplete or inconsistent LDAP settings."""
    required = [
        "label",
        "host",
        "attribute_for_mail",
        "attribute_for_username",
        "app_dn",
        "app_dn_password",
        "search_base",
    ]
    for key in required:
        if not getattr(form_data, key):
            raise HTTPException(400, detail=f"Required field {key} is empty")

    if form_data.use_tls and not form_data.certificate_path:
        raise HTTPException(
            400, detail="TLS is enabled but certificate file path is missing"
        )


def _serialize_ldap_server_config(request: Request) -> dict:
    """Read LDAP server settings into the wire-format dict."""
    cfg = request.app.state.config
    return {
        "label": cfg.LDAP_SERVER_LABEL,
        "host": cfg.LDAP_SERVER_HOST,
        "port": cfg.LDAP_SERVER_PORT,
        "attribute_for_mail": cfg.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": cfg.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": cfg.LDAP_APP_DN,
        "app_dn_password": cfg.LDAP_APP_PASSWORD,
        "search_base": cfg.LDAP_SEARCH_BASE,
        "search_filters": cfg.LDAP_SEARCH_FILTERS,
        "use_tls": cfg.LDAP_USE_TLS,
        "certificate_path": cfg.LDAP_CA_CERT_FILE,
        "ciphers": cfg.LDAP_CIPHERS,
    }


@router.get("/admin/config/ldap")
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    """Return whether LDAP is enabled."""
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


@router.post("/admin/config/ldap")
async def update_ldap_config(
    request: Request,
    form_data: LdapConfigForm,
    user=Depends(get_admin_user),
):
    """Toggle LDAP authentication on or off."""
    request.app.state.config.ENABLE_LDAP = form_data.enable_ldap
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


# ---------------------------------------------------------------------------
# API key lifecycle
# ---------------------------------------------------------------------------


@router.post("/api_key", response_model=ApiKey)
async def generate_api_key(request: Request, user=Depends(get_current_user)):
    """Create a new API key for the current user."""
    if not request.app.state.config.ENABLE_API_KEY:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )

    api_key = create_api_key()
    success = Users.update_user_api_key_by_id(user.id, api_key)
    if not success:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)
    return {"api_key": api_key}


@router.delete("/api_key", response_model=bool)
async def delete_api_key(user=Depends(get_current_user)):
    """Revoke the current user's API key."""
    return Users.update_user_api_key_by_id(user.id, None)


@router.get("/api_key", response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user)):
    """Return the current user's existing API key."""
    api_key = Users.get_user_api_key_by_id(user.id)
    if not api_key:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)
    return {"api_key": api_key}
