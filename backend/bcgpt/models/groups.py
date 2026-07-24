"""User-group management for role-based access control.

Groups aggregate user memberships and carry a permissions JSON payload.
The ``user_ids`` column is a JSON array of member user identifiers.
"""

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, func, JSON, String, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db
from bcgpt.models import FileMetadataResponse

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> int:
    """Return current UTC epoch seconds as an integer."""
    return int(time.time())


def _validate_group(row) -> Optional["GroupModel"]:
    """Convert a raw Group ORM row to GroupModel or return None."""
    return GroupModel.model_validate(row) if row else None


# ---------------------------------------------------------------------------
# SQLAlchemy table
# ---------------------------------------------------------------------------

class Group(Base):
    """Persistent user-group record."""

    __tablename__ = "group"

    id = Column(Text, unique=True, primary_key=True)
    user_id = Column(Text)

    name = Column(Text)
    description = Column(Text)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    permissions = Column(JSON, nullable=True)
    user_ids = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class GroupModel(BaseModel):
    """Full group representation used throughout the application."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

    name: str
    description: str

    data: Optional[dict] = None
    meta: Optional[dict] = None

    permissions: Optional[dict] = None
    user_ids: list[str] = []

    created_at: int
    updated_at: int


class GroupResponse(BaseModel):
    """Group data returned to API consumers."""

    id: str
    user_id: str
    name: str
    description: str
    permissions: Optional[dict] = None
    data: Optional[dict] = None
    meta: Optional[dict] = None
    user_ids: list[str] = []
    created_at: int
    updated_at: int


class GroupForm(BaseModel):
    """Payload accepted when creating a group."""

    name: str
    description: str
    permissions: Optional[dict] = None


class GroupUpdateForm(GroupForm):
    """Payload accepted when updating a group (may include new member list)."""

    user_ids: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------

class GroupTable:
    """CRUD operations for :class:`Group` records."""

    # -- create -------------------------------------------------------------

    def insert_new_group(
        self, user_id: str, form_data: GroupForm
    ) -> Optional[GroupModel]:
        """Persist a new group owned by *user_id*."""
        with get_db() as db:
            now = _now()
            group = GroupModel(
                **form_data.model_dump(exclude_none=True),
                id=str(uuid.uuid4()),
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
            try:
                result = Group(**group.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return _validate_group(result)
            except Exception:
                return None

    # -- read ---------------------------------------------------------------

    def get_groups(self) -> list[GroupModel]:
        """Return all groups ordered by last update (newest first)."""
        with get_db() as db:
            return [
                GroupModel.model_validate(g)
                for g in db.query(Group).order_by(Group.updated_at.desc()).all()
            ]

    def get_groups_by_member_id(self, user_id: str) -> list[GroupModel]:
        """Return groups whose ``user_ids`` array contains *user_id*."""
        with get_db() as db:
            return [
                GroupModel.model_validate(g)
                for g in db.query(Group)
                .filter(func.json_array_length(Group.user_ids) > 0)
                .filter(Group.user_ids.cast(String).like(f'%"{user_id}"%'))
                .order_by(Group.updated_at.desc())
                .all()
            ]

    def get_group_by_id(self, id: str) -> Optional[GroupModel]:
        """Look up a group by its primary key."""
        try:
            with get_db() as db:
                row = db.query(Group).filter_by(id=id).first()
                return _validate_group(row)
        except Exception:
            return None

    def get_group_user_ids_by_id(self, id: str) -> Optional[str]:
        """Return the ``user_ids`` list for the given group, or None."""
        group = self.get_group_by_id(id)
        return group.user_ids if group else None

    # -- update -------------------------------------------------------------

    def update_group_by_id(
        self, id: str, form_data: GroupUpdateForm, overwrite: bool = False
    ) -> Optional[GroupModel]:
        """Patch a group's mutable fields from *form_data*."""
        try:
            with get_db() as db:
                db.query(Group).filter_by(id=id).update(
                    {
                        **form_data.model_dump(exclude_none=True),
                        "updated_at": _now(),
                    }
                )
                db.commit()
                return self.get_group_by_id(id=id)
        except Exception:
            log.exception("Failed to update group %s", id)
            return None

    # -- delete -------------------------------------------------------------

    def delete_group_by_id(self, id: str) -> bool:
        """Remove a single group by primary key."""
        try:
            with get_db() as db:
                db.query(Group).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_groups(self) -> bool:
        """Remove every group row."""
        with get_db() as db:
            try:
                db.query(Group).delete()
                db.commit()
                return True
            except Exception:
                return False

    # -- membership ---------------------------------------------------------

    def remove_user_from_all_groups(self, user_id: str) -> bool:
        """Strip *user_id* from the member list of every group it belongs to."""
        with get_db() as db:
            try:
                for group in self.get_groups_by_member_id(user_id):
                    group.user_ids.remove(user_id)
                    db.query(Group).filter_by(id=group.id).update(
                        {
                            "user_ids": group.user_ids,
                            "updated_at": _now(),
                        }
                    )
                    db.commit()
                return True
            except Exception:
                return False


Groups = GroupTable()
