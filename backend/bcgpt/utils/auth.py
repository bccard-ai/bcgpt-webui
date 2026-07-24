"""Authentication and authorization utilities for BCGPT WebUI.

Provides JWT creation/validation, password hashing, HMAC signature
verification, license data retrieval, and FastAPI dependency-based
user authentication (bearer token, cookie, API key).

Public exports (re-exported via ``bcgpt.utils.__init__``):
    ALGORITHM, SESSION_SECRET, bearer_security,
    verify_signature, override_static, get_license_data,
    verify_password, get_password_hash,
    create_token, decode_token, extract_token_from_auth_header,
    create_api_key, get_http_authorization_cred,
    get_current_user, get_current_user_by_api_key,
    get_verified_user, get_admin_user
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional, Union

import bcrypt
import jwt
import requests
from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import (
    SRC_LOG_LEVELS,
    STATIC_DIR,
    TRUSTED_SIGNATURE_KEY,
    BCGPT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_KEY_ID,
    JWT_RSA_PRIVATE_KEY,
    JWT_RSA_PUBLIC_KEY,
)
from bcgpt.models import Users

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OAUTH"])

SESSION_SECRET = BCGPT_SECRET_KEY
"""Secret key used for HS256 JWT signing and validation."""


def _resolve_jwt_config():
    """Resolve the effective JWT algorithm + signing/verification keys (3.4).

    RS256 is opt-in via ``JWT_ALGORITHM=RS256`` and requires both RSA PEM keys;
    any misconfiguration falls back to HS256 so authentication never breaks.
    Returns ``(algorithm, signing_key, verify_key, key_id)``.
    """
    if JWT_ALGORITHM == "RS256":
        if JWT_RSA_PRIVATE_KEY and JWT_RSA_PUBLIC_KEY:
            return "RS256", JWT_RSA_PRIVATE_KEY, JWT_RSA_PUBLIC_KEY, JWT_KEY_ID
        log.error(
            "JWT_ALGORITHM=RS256 but RSA keys are missing/unreadable; "
            "falling back to HS256."
        )
    return "HS256", SESSION_SECRET, SESSION_SECRET, None


ALGORITHM, _JWT_SIGNING_KEY, _JWT_VERIFY_KEY, _JWT_KEY_ID = _resolve_jwt_config()
"""JWT signing algorithm (``HS256`` default, or ``RS256`` when configured)."""

bearer_security = HTTPBearer(auto_error=False)
"""FastAPI security scheme that extracts Bearer tokens from the Authorization header."""

# ---------------------------------------------------------------------------
# HMAC signature verification
# ---------------------------------------------------------------------------


def verify_signature(payload: str, signature: str) -> bool:
    """Verify an HMAC-SHA256 signature against a trusted key.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        payload: The raw payload string that was signed.
        signature: The Base64-encoded HMAC signature to verify.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    try:
        expected = base64.b64encode(
            hmac.new(TRUSTED_SIGNATURE_KEY, payload.encode(), hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Static file override (license resource delivery)
# ---------------------------------------------------------------------------


def override_static(path: str, content: str) -> None:
    """Write a Base64-encoded resource into the static assets directory.

    Performs path-traversal validation before writing.  This is called by
    :func:`get_license_data` when the license server delivers branded
    static resources.

    Args:
        path: Relative filename (must not contain ``/`` or ``..``).
        content: Base64-encoded file content.
    """
    if "/" in path or ".." in path:
        log.error("Invalid static override path rejected: %s", path)
        return

    file_path = os.path.join(STATIC_DIR, path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(base64.b64decode(content))


# ---------------------------------------------------------------------------
# License data retrieval
# ---------------------------------------------------------------------------


def get_license_data(app, key: str) -> bool:
    """Fetch and apply enterprise license data from the BCGPT license server.

    On a successful response the function applies any bundled static
    resources, user-count limits, branding name, and license metadata
    to ``app.state``.

    Args:
        app: The FastAPI application instance (``app.state`` is mutated).
        key: The license key string.

    Returns:
        ``True`` if the license was validated and applied, ``False`` otherwise.
    """
    if not key:
        return False

    try:
        res = requests.post(
            "https://api.BCGPT.com/api/v1/license/",
            json={"key": key, "version": "1"},
            timeout=5,
        )

        if not getattr(res, "ok", False):
            log.error(
                "License retrieval failed: %s",
                getattr(res, "text", "unknown error"),
            )
            return False

        payload = getattr(res, "json", lambda: {})()
        for field_key, field_value in payload.items():
            if field_key == "resources":
                for resource_path, resource_content in field_value.items():
                    override_static(resource_path, resource_content)
            elif field_key == "count":
                setattr(app.state, "USER_COUNT", field_value)
            elif field_key == "name":
                setattr(app.state, "BCGPT_APP_NAME", field_value)
            elif field_key == "metadata":
                setattr(app.state, "LICENSE_METADATA", field_value)

        return True

    except Exception as exc:
        log.exception("License retrieval error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> Optional[bool]:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: The user-supplied plaintext password.
        hashed_password: The stored bcrypt hash.

    Returns:
        ``True`` if the password matches, ``False`` if it does not,
        or ``None`` if ``hashed_password`` is falsy.
    """
    if not hashed_password:
        return None
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt hash as a UTF-8 string.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT token operations
# ---------------------------------------------------------------------------


def create_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """Create a signed JWT token.

    Always stamps an ``iat`` (issued-at) claim for auditing and future
    time-based revocation support.

    Args:
        data: Payload claims to encode.
        expires_delta: Optional expiration duration.  If provided an ``exp``
            claim is added.

    Returns:
        The encoded JWT string.
    """
    payload = data.copy()
    payload.setdefault("iat", datetime.now(UTC))

    if expires_delta:
        payload["exp"] = datetime.now(UTC) + expires_delta

    headers = {"kid": _JWT_KEY_ID} if _JWT_KEY_ID else None
    return jwt.encode(payload, _JWT_SIGNING_KEY, algorithm=ALGORITHM, headers=headers)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload dict, or ``None`` if the token is invalid or
        expired.
    """
    try:
        return jwt.decode(token, _JWT_VERIFY_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def get_jwks() -> dict:
    """Return the JSON Web Key Set publishing the RS256 public key (3.4).

    Empty ``keys`` for HS256 (a symmetric secret is never published).
    """
    if ALGORITHM != "RS256" or not _JWT_VERIFY_KEY:
        return {"keys": []}
    try:
        import json as _json

        from cryptography.hazmat.primitives.serialization import (
            load_pem_public_key,
        )
        from jwt.algorithms import RSAAlgorithm

        public_key = load_pem_public_key(_JWT_VERIFY_KEY.encode("utf-8"))
        jwk = _json.loads(RSAAlgorithm.to_jwk(public_key))
        jwk.update({"use": "sig", "alg": "RS256", "kid": _JWT_KEY_ID})
        return {"keys": [jwk]}
    except Exception as e:
        log.error("Failed to build JWKS: %s", e)
        return {"keys": []}


def extract_token_from_auth_header(auth_header: str) -> str:
    """Strip the ``Bearer `` prefix from an Authorization header value.

    Args:
        auth_header: The raw ``Authorization`` header string.

    Returns:
        The bare token string.
    """
    return auth_header[len("Bearer "):]


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------


def create_api_key() -> str:
    """Generate a random API key with an ``sk-`` prefix.

    Returns:
        A new API key string (e.g. ``sk-a1b2c3…``).
    """
    return f"sk-{uuid.uuid4().hex}"


def get_http_authorization_cred(auth_header: str) -> HTTPAuthorizationCredentials:
    """Parse an ``Authorization`` header into a FastAPI credentials object.

    Args:
        auth_header: The raw ``Authorization`` header value.

    Returns:
        A parsed :class:`~fastapi.security.HTTPAuthorizationCredentials`.

    Raises:
        ValueError: If the header cannot be split into scheme and credentials.
    """
    try:
        scheme, credentials = auth_header.split(" ")
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
    except Exception:
        raise ValueError(ERROR_MESSAGES.INVALID_TOKEN)


# ---------------------------------------------------------------------------
# FastAPI authentication dependencies
# ---------------------------------------------------------------------------


def get_current_user(
    request: Request,
    background_tasks: BackgroundTasks,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
):
    """FastAPI dependency that resolves the current authenticated user.

    Supports three authentication mechanisms (checked in order):

    1. **Bearer token** from the ``Authorization`` header.
    2. **Cookie token** from the ``token`` cookie.
    3. **API key** (``sk-…`` prefix) from either source above.

    JWT tokens are validated against a ``token_version`` (``tv``) claim to
    support revocation on logout or password change.

    Args:
        request: The incoming HTTP request.
        background_tasks: FastAPI background task runner (used to update
            last-active timestamp asynchronously).
        auth_token: Injected Bearer credentials (may be ``None``).

    Returns:
        The authenticated :class:`~bcgpt.models.users.UserModel`.

    Raises:
        HTTPException (401/403): If authentication or authorization fails.
    """
    token: Optional[str] = None

    if auth_token is not None:
        token = auth_token.credentials

    if token is None and "token" in request.cookies:
        token = request.cookies.get("token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # --- API key path ---
    if token.startswith("sk-"):
        if not request.state.enable_api_key:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.API_KEY_NOT_ALLOWED,
            )

        if request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS:
            allowed_paths = [
                p.strip()
                for p in str(
                    request.app.state.config.API_KEY_ALLOWED_ENDPOINTS
                ).split(",")
            ]
            if request.url.path not in allowed_paths:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail=ERROR_MESSAGES.API_KEY_NOT_ALLOWED,
                )

        return get_current_user_by_api_key(token)

    # --- JWT path ---
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if data is None or "id" not in data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    user = Users.get_user_by_id(data["id"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.INVALID_TOKEN,
        )

    # Token-version revocation check
    from bcgpt.models.auths import Auths

    token_tv = data.get("tv", 0)
    auth = Auths.get_auth_by_user_id(user.id)
    if auth is not None and auth.token_version != token_tv:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
        )

    # Update last-active timestamp asynchronously
    if background_tasks:
        background_tasks.add_task(Users.update_user_last_active_by_id, user.id)

    return user


def get_current_user_by_api_key(api_key: str):
    """Resolve a user from an API key.

    Args:
        api_key: The ``sk-…`` API key string.

    Returns:
        The authenticated :class:`~bcgpt.models.users.UserModel`.

    Raises:
        HTTPException (401): If no user matches the API key.
    """
    user = Users.get_user_by_api_key(api_key)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.INVALID_TOKEN,
        )

    Users.update_user_last_active_by_id(user.id)
    return user


def get_verified_user(user=Depends(get_current_user)):
    """FastAPI dependency that requires the user to have ``user`` or ``admin`` role.

    Args:
        user: Injected by :func:`get_current_user`.

    Returns:
        The verified user model.

    Raises:
        HTTPException (401): If the user's role is not ``user`` or ``admin``.
    """
    if user.role not in {"user", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


def get_admin_user(user=Depends(get_current_user)):
    """FastAPI dependency that requires the user to have the ``admin`` role.

    Args:
        user: Injected by :func:`get_current_user`.

    Returns:
        The admin user model.

    Raises:
        HTTPException (401): If the user's role is not ``admin``.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user
