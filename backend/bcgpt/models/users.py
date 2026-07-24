"""User model and table operations.

Manages user accounts including authentication credentials (API key,
OAuth sub), per-user settings stored as JSON, and profile metadata.
User deletion cascades to associated chats and group memberships.
"""

import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text

from bcgpt.internal import Base, JSONField, get_db
from bcgpt.models import Chats, Groups

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class User(Base):
    """Persistent representation of a user row."""

    __tablename__ = "user"

    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    role = Column(String)
    profile_image_url = Column(Text)

    last_active_at = Column(BigInteger)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)

    api_key = Column(String, nullable=True, unique=True)
    settings = Column(JSONField, nullable=True)
    info = Column(JSONField, nullable=True)

    oauth_sub = Column(Text, unique=True)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UserSettings(BaseModel):
    """User settings blob persisted as JSON."""

    ui: Optional[dict] = {}
    model_config = ConfigDict(extra="allow")


class UserModel(BaseModel):
    """Full user representation returned to callers."""

    id: str
    name: str
    email: str
    role: str = "pending"
    profile_image_url: str

    last_active_at: int  # epoch seconds
    updated_at: int  # epoch seconds
    created_at: int  # epoch seconds

    api_key: Optional[str] = None
    settings: Optional[UserSettings] = None
    info: Optional[dict] = None

    oauth_sub: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Minimal user payload returned in API responses."""

    id: str
    name: str
    email: str
    role: str
    profile_image_url: str


class UserNameResponse(BaseModel):
    """User payload with name and role only."""

    id: str
    name: str
    role: str
    profile_image_url: str


class UserRoleUpdateForm(BaseModel):
    """Schema for updating a user's role."""

    id: str
    role: str


class UserUpdateForm(BaseModel):
    """Schema for updating a user's profile."""

    name: str
    email: str
    profile_image_url: str
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------


class UsersTable:
    """Collection of database helpers for the ``user`` table."""

    def insert_new_user(
        self,
        id: str,
        name: str,
        email: str,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        oauth_sub: Optional[str] = None,
    ) -> Optional[UserModel]:
        """Create a new user and return its model, or ``None`` on failure."""
        with get_db() as db:
            user = UserModel(
                **{
                    "id": id,
                    "name": name,
                    "email": email,
                    "role": role,
                    "profile_image_url": profile_image_url,
                    "last_active_at": int(time.time()),
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                    "oauth_sub": oauth_sub,
                }
            )
            result = User(**user.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            if result:
                return user
            else:
                return None

    def get_user_by_id(self, id: str) -> Optional[UserModel]:
        """Fetch a single user by primary key."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_api_key(self, api_key: str) -> Optional[UserModel]:
        """Fetch a user by their API key."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(api_key=api_key).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """Fetch a user by email address."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(email=email).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_oauth_sub(self, sub: str) -> Optional[UserModel]:
        """Fetch a user by their OAuth subject identifier."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(oauth_sub=sub).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_users(
        self,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[UserModel]:
        """Return users ordered by creation time, with optional pagination."""
        with get_db() as db:

            query = db.query(User).order_by(User.created_at.desc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            users = query.all()

            return [UserModel.model_validate(user) for user in users]

    def get_users_by_user_ids(self, user_ids: list[str]) -> list[UserModel]:
        """Return users matching a list of IDs."""
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [UserModel.model_validate(user) for user in users]

    def get_num_users(self) -> Optional[int]:
        """Return the total number of users."""
        with get_db() as db:
            return db.query(User).count()

    def get_first_user(self) -> Optional[UserModel]:
        """Return the earliest-created user (the first signup)."""
        try:
            with get_db() as db:
                user = db.query(User).order_by(User.created_at).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_webhook_url_by_id(self, id: str) -> Optional[str]:
        """Extract the notification webhook URL from user settings."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()

                if user.settings is None:
                    return None
                else:
                    return (
                        user.settings.get("ui", {})
                        .get("notifications", {})
                        .get("webhook_url", None)
                    )
        except Exception:
            return None

    def update_user_role_by_id(self, id: str, role: str) -> Optional[UserModel]:
        """Change the role of a user."""
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"role": role})
                db.commit()
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_profile_image_url_by_id(
        self,
        id: str,
        profile_image_url: str,
    ) -> Optional[UserModel]:
        """Update the profile image URL of a user."""
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"profile_image_url": profile_image_url}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_last_active_by_id(self, id: str) -> Optional[UserModel]:
        """Touch the ``last_active_at`` timestamp for a user."""
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"last_active_at": int(time.time())}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_oauth_sub_by_id(
        self,
        id: str,
        oauth_sub: str,
    ) -> Optional[UserModel]:
        """Set or update the OAuth subject identifier for a user."""
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"oauth_sub": oauth_sub})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        """Apply arbitrary field updates to a user."""
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(updated)
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_settings_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        """Merge new settings into the existing user settings blob."""
        try:
            with get_db() as db:
                user_settings = db.query(User).filter_by(id=id).first().settings

                if user_settings is None:
                    user_settings = {}

                user_settings.update(updated)

                db.query(User).filter_by(id=id).update({"settings": user_settings})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def delete_user_by_id(self, id: str) -> bool:
        """Delete a user and cascade to groups and chats.

        Returns ``True`` if the user and their chats were successfully
        deleted.
        """
        try:
            # Remove user from all groups
            Groups.remove_user_from_all_groups(id)

            # Delete user chats first
            result = Chats.delete_chats_by_user_id(id)
            if result:
                with get_db() as db:
                    db.query(User).filter_by(id=id).delete()
                    db.commit()

                return True
            else:
                return False
        except Exception:
            return False

    def update_user_api_key_by_id(self, id: str, api_key: str) -> bool:
        """Set or regenerate the API key for a user."""
        try:
            with get_db() as db:
                result = db.query(User).filter_by(id=id).update({"api_key": api_key})
                db.commit()
                return True if result == 1 else False
        except Exception:
            return False

    def get_user_api_key_by_id(self, id: str) -> Optional[str]:
        """Return the API key for a user, or ``None``."""
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return user.api_key
        except Exception:
            return None

    def get_valid_user_ids(self, user_ids: list[str]) -> list[str]:
        """Filter a list of user IDs to only those that exist."""
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [user.id for user in users]

    def signups_by_day(self, start_ts_s: int, end_ts_s: int) -> list[dict]:
        from sqlalchemy import cast, func, Integer

        day_expr = cast(func.floor(User.created_at / 86400.0), Integer).label("day")
        with get_db() as db:
            rows = (
                db.query(day_expr, func.count(User.id))
                .filter(User.created_at >= start_ts_s, User.created_at <= end_ts_s)
                .group_by(day_expr)
                .order_by(day_expr)
                .all()
            )
            return [{"day": int(r[0]), "value": int(r[1])} for r in rows]

    def active_users_by_day(self, start_ts_s: int, end_ts_s: int) -> list[dict]:
        """Distinct users active (last_active_at >= day start) per epoch-day.

        Buckets each user into the day of their last_active_at within the window.
        """
        from sqlalchemy import cast, func, Integer

        day_expr = cast(func.floor(User.last_active_at / 86400.0), Integer).label("day")
        with get_db() as db:
            rows = (
                db.query(day_expr, func.count(func.distinct(User.id)))
                .filter(
                    User.last_active_at >= start_ts_s,
                    User.last_active_at <= end_ts_s,
                )
                .group_by(day_expr)
                .order_by(day_expr)
                .all()
            )
            return [{"day": int(r[0]), "value": int(r[1])} for r in rows]


Users = UsersTable()
