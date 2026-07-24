"""Authentication persistence layer.

Provides the ``Auth`` SQLAlchemy model, Pydantic request/response schemas,
and the ``AuthsTable`` repository that mediates all auth-related database
operations including credential verification, account lockout enforcement,
and JWT token-version tracking.

Public exports consumed elsewhere:

* ``Auths`` – singleton ``AuthsTable`` instance.
* ``Auth``, ``AuthModel`` – ORM and Pydantic representations.
* ``MAX_FAILED_ATTEMPTS``, ``LOCKOUT_DURATION`` – lockout policy constants.
* Various ``*Form`` / ``*Response`` Pydantic models.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db
from bcgpt.models import UserModel, Users
from bcgpt.utils import verify_password

# ---------------------------------------------------------------------------
# Lockout policy constants (imported by routers)
# ---------------------------------------------------------------------------

MAX_FAILED_ATTEMPTS: int = 5
LOCKOUT_DURATION: int = 30 * 60  # seconds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

# ===================================================================
# SQLAlchemy ORM model
# ===================================================================


class Auth(Base):  # type: ignore[misc]
    """Row-level representation of the ``auth`` table.

    Columns
    -------
    id : str
        Primary key – a UUID shared with the companion ``user`` row.
    email : str
        Login email address (not necessarily unique at the DB level;
        uniqueness is enforced at the application layer).
    password : str
        bcrypt hash of the user's password.
    active : bool
        ``True`` when the account is enabled.
    failed_attempts : int
        Consecutive failed login attempts since last success / unlock.
    locked_until : int | None
        Unix timestamp until which the account is locked, or ``None``.
    token_version : int
        Monotonically increasing counter bumped on events that must
        invalidate previously-issued JWTs (logout, password change).
    """

    __tablename__ = "auth"

    id: str = Column(String, primary_key=True)
    email: str = Column(String)
    password: str = Column(Text)
    active: bool = Column(Boolean)
    failed_attempts: int = Column(Integer, default=0)
    locked_until: Optional[int] = Column(BigInteger, nullable=True)
    token_version: int = Column(
        Integer, default=0, server_default="0", nullable=False
    )


# ===================================================================
# Pydantic schemas
# ===================================================================


class AuthModel(BaseModel):
    """Pydantic mirror of :class:`Auth` for API serialization."""

    id: str
    email: str
    password: str
    active: bool = True
    failed_attempts: int = 0
    locked_until: Optional[int] = None
    token_version: int = 0


class Token(BaseModel):
    token: str
    token_type: str


class ApiKey(BaseModel):
    api_key: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    profile_image_url: str


class SigninResponse(Token, UserResponse):
    """Combined token + user payload returned on successful sign-in."""


class SigninForm(BaseModel):
    email: str
    password: str
    # open-moai adoption 2.5 — optional TOTP code for MFA-enrolled users.
    totp_code: Optional[str] = None


class LdapForm(BaseModel):
    user: str
    password: str


class ProfileImageUrlForm(BaseModel):
    profile_image_url: str


class UpdateProfileForm(BaseModel):
    profile_image_url: str
    name: str


class UpdatePasswordForm(BaseModel):
    password: str
    new_password: str


class SignupForm(BaseModel):
    name: str
    email: str
    password: str
    profile_image_url: Optional[str] = "/user.png"


class AddUserForm(SignupForm):
    role: Optional[str] = "pending"


# ===================================================================
# Lockout policy helper
# ===================================================================


class LockoutPolicy:
    """Encapsulates account-lockout rules.

    All methods are stateless; they read the current timestamp and the
    persisted ``failed_attempts`` / ``locked_until`` values to make
    decisions.
    """

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        lockout_duration: int = LOCKOUT_DURATION,
    ) -> None:
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration

    def is_locked(self, locked_until: Optional[int]) -> tuple[bool, Optional[int]]:
        """Return ``(is_locked, locked_until_ts)``.

        If the stored lock has already expired the account is considered
        *not* locked.
        """
        if locked_until is None:
            return False, None
        now = int(time.time())
        if now < locked_until:
            return True, locked_until
        return False, None

    def compute_next_attempts(
        self, current_attempts: int, locked_until: Optional[int]
    ) -> tuple[int, Optional[int]]:
        """Return ``(new_attempt_count, new_locked_until)``.

        If the previous lock expired, the attempt counter resets before
        incrementing so that a single post-expiry mistype does not
        immediately re-lock the account.
        """
        now = int(time.time())
        # Reset counter if the previous lockout has already expired.
        if locked_until is not None and now >= locked_until:
            current_attempts = 0

        new_count = current_attempts + 1
        if new_count >= self.max_attempts:
            return new_count, now + self.lockout_duration
        return new_count, None


# ===================================================================
# Repository (AuthsTable)
# ===================================================================


class AuthsTable:
    """Data-access repository for the ``auth`` table.

    Every public method preserves the original signature so that existing
    callers (routers, middleware) continue to work without modification.
    """

    def __init__(self, lockout: Optional[LockoutPolicy] = None) -> None:
        self._lockout = lockout or LockoutPolicy()

    # -- Account creation --------------------------------------------------

    def insert_new_auth(
        self,
        email: str,
        password: str,
        name: str,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        oauth_sub: Optional[str] = None,
    ) -> Optional[UserModel]:
        """Create a new auth record + companion user record.

        Returns the :class:`UserModel` on success, or ``None`` if the
        user record could not be created.
        """
        with get_db() as db:
            log.info("insert_new_auth")
            user_id = str(uuid.uuid4())

            auth = Auth(
                id=user_id,
                email=email,
                password=password,
                active=True,
            )
            db.add(auth)

            user = Users.insert_new_user(
                user_id, name, email, profile_image_url, role, oauth_sub
            )

            db.commit()
            db.refresh(auth)

            return user if (auth and user) else None

    # -- Authentication ----------------------------------------------------

    def authenticate_user(
        self, email: str, password: str
    ) -> Optional[UserModel]:
        """Verify credentials and return the matching user, or ``None``."""
        log.info("authenticate_user: %s", email)
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if auth is None:
                    return None
                if not verify_password(password, auth.password):
                    return None
                return Users.get_user_by_id(auth.id)
        except Exception:
            return None

    def authenticate_user_by_api_key(
        self, api_key: str
    ) -> Optional[UserModel]:
        """Look up a user by their long-lived API key."""
        log.info("authenticate_user_by_api_key: ***redacted***")
        if not api_key:
            return None
        try:
            user = Users.get_user_by_api_key(api_key)
            return user if user else None
        except Exception:
            return None

    def authenticate_user_by_trusted_header(
        self, email: str
    ) -> Optional[UserModel]:
        """Authenticate via a reverse-proxy trusted header."""
        log.info("authenticate_user_by_trusted_header: %s", email)
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if auth is None:
                    return None
                return Users.get_user_by_id(auth.id)
        except Exception:
            return None

    # -- Reads -------------------------------------------------------------

    def get_auth_by_email(self, email: str) -> Optional[AuthModel]:
        """Return an :class:`AuthModel` for the given email, or ``None``."""
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email).first()
                return AuthModel.model_validate(auth) if auth else None
        except Exception:
            return None

    def get_auth_by_user_id(self, user_id: str) -> Optional[AuthModel]:
        """Return an :class:`AuthModel` for the given user id, or ``None``."""
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(id=user_id).first()
                return AuthModel.model_validate(auth) if auth else None
        except Exception:
            return None

    # -- Token versioning --------------------------------------------------

    def increment_token_version(self, user_id: str) -> bool:
        """Bump ``token_version`` to invalidate all existing JWTs."""
        try:
            with get_db() as db:
                result = (
                    db.query(Auth)
                    .filter_by(id=user_id)
                    .update({"token_version": Auth.token_version + 1})
                )
                db.commit()
                return result == 1
        except Exception:
            return False

    # -- Account lockout ---------------------------------------------------

    def is_account_locked(self, email: str) -> tuple[bool, Optional[int]]:
        """Check whether the account is currently locked out.

        Returns ``(is_locked, locked_until_timestamp)``.
        """
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if not auth:
                    return False, None
                return self._lockout.is_locked(auth.locked_until)
        except Exception:
            return False, None

    def increment_failed_attempts(self, email: str) -> Optional[int]:
        """Record a failed login attempt and lock if threshold reached.

        Admin accounts are exempt from lockout.  Returns the new attempt
        count, or ``None`` on error / admin exemption.
        """
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if auth is None:
                    return None

                # Admin accounts are exempt from lockout.
                user = Users.get_user_by_id(auth.id)
                if user and user.role == "admin":
                    return None

                current = auth.failed_attempts or 0
                new_count, new_locked_until = self._lockout.compute_next_attempts(
                    current, auth.locked_until
                )

                db.query(Auth).filter_by(id=auth.id).update(
                    {
                        "failed_attempts": new_count,
                        "locked_until": new_locked_until,
                    }
                )
                db.commit()
                return new_count
        except Exception:
            return None

    def reset_failed_attempts(self, id: str) -> bool:
        """Clear failed-attempt counters after a successful login."""
        try:
            with get_db() as db:
                db.query(Auth).filter_by(id=id).update(
                    {"failed_attempts": 0, "locked_until": None}
                )
                db.commit()
                return True
        except Exception:
            return False

    def unlock_account_by_id(self, id: str) -> bool:
        """Administratively unlock an account."""
        try:
            with get_db() as db:
                db.query(Auth).filter_by(id=id).update(
                    {"failed_attempts": 0, "locked_until": None}
                )
                db.commit()
                return True
        except Exception:
            return False

    def get_all_lockout_statuses(self) -> dict[str, Any]:
        """Return a dict mapping user id to lockout metadata."""
        try:
            with get_db() as db:
                auths = db.query(Auth).all()
                now = int(time.time())
                return {
                    auth.id: {
                        "failed_attempts": auth.failed_attempts or 0,
                        "locked_until": auth.locked_until,
                        "is_locked": (
                            auth.locked_until is not None
                            and now < auth.locked_until
                        ),
                    }
                    for auth in auths
                }
        except Exception:
            return {}

    # -- Mutations ---------------------------------------------------------

    def update_user_password_by_id(self, id: str, new_password: str) -> bool:
        """Replace the stored password hash.  Returns ``True`` on success."""
        try:
            with get_db() as db:
                result = db.query(Auth).filter_by(id=id).update(
                    {"password": new_password}
                )
                db.commit()
                return result == 1
        except Exception:
            return False

    def update_email_by_id(self, id: str, email: str) -> bool:
        """Change the email address.  Returns ``True`` on success."""
        try:
            with get_db() as db:
                result = db.query(Auth).filter_by(id=id).update(
                    {"email": email}
                )
                db.commit()
                return result == 1
        except Exception:
            return False

    def delete_auth_by_id(self, id: str) -> bool:
        """Delete both the auth record and its companion user."""
        try:
            with get_db() as db:
                if not Users.delete_user_by_id(id):
                    return False
                db.query(Auth).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False


# Singleton instance consumed throughout the application.
Auths = AuthsTable()
