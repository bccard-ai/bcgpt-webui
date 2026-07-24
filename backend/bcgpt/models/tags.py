"""Tag model and table operations.

Manages tags that users attach to chats.  Tags use a composite primary
key of ``(id, user_id)`` so the same tag name can exist for different
users.
"""

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, PrimaryKeyConstraint, String

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class Tag(Base):
    """Persistent representation of a tag row.

    Uses a composite primary key ``(id, user_id)`` to allow the same
    tag name across different users.
    """

    __tablename__ = "tag"

    id = Column(String)
    name = Column(String)
    user_id = Column(String)
    meta = Column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", "user_id", name="pk_id_user_id"),
    )


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TagModel(BaseModel):
    """Full tag representation returned to callers."""

    id: str
    name: str
    user_id: str
    meta: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


class TagChatIdForm(BaseModel):
    """Schema linking a tag name to a chat ID."""

    name: str
    chat_id: str


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class TagTable:
    """Collection of database helpers for the ``tag`` table."""

    def insert_new_tag(
        self, name: str, user_id: str
    ) -> Optional[TagModel]:
        """Create a new tag.  The tag ID is derived from the name."""
        with get_db() as db:
            id = name.replace(" ", "_").lower()
            tag = TagModel(**{"id": id, "user_id": user_id, "name": name})
            try:
                result = Tag(**tag.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return TagModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception("Error inserting a new tag: %s", e)
                return None

    def get_tag_by_name_and_user_id(
        self,
        name: str,
        user_id: str,
    ) -> Optional[TagModel]:
        """Fetch a tag by its name (resolved to ID) and owner."""
        try:
            id = name.replace(" ", "_").lower()
            with get_db() as db:
                tag = (
                    db.query(Tag).filter_by(id=id, user_id=user_id).first()
                )
                return TagModel.model_validate(tag)
        except Exception:
            return None

    def get_tags_by_user_id(self, user_id: str) -> list[TagModel]:
        """Return all tags belonging to a user."""
        with get_db() as db:
            return [
                TagModel.model_validate(tag)
                for tag in (db.query(Tag).filter_by(user_id=user_id).all())
            ]

    def get_tags_by_ids_and_user_id(
        self,
        ids: list[str],
        user_id: str,
    ) -> list[TagModel]:
        """Return tags matching the given IDs that belong to a user."""
        with get_db() as db:
            return [
                TagModel.model_validate(tag)
                for tag in (
                    db.query(Tag)
                    .filter(Tag.id.in_(ids), Tag.user_id == user_id)
                    .all()
                )
            ]

    def delete_tag_by_name_and_user_id(
        self, name: str, user_id: str
    ) -> bool:
        """Delete a tag by its name and owner."""
        try:
            with get_db() as db:
                id = name.replace(" ", "_").lower()
                res = db.query(Tag).filter_by(id=id, user_id=user_id).delete()
                log.debug("res: %s", res)
                db.commit()
                return True
        except Exception as e:
            log.error("delete_tag: %s", e)
            return False


Tags = TagTable()
