"""Folder management for organizing user content into hierarchical trees.

Each folder belongs to a user and may have a parent folder, forming a
recursive directory-like structure.  Folders optionally hold an ``items``
JSON payload and ``is_expanded`` UI state.
"""

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, BigInteger, Column, JSON, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db
from bcgpt.models import Chats

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> int:
    """Return current UTC epoch seconds as an integer."""
    return int(time.time())


def _validate_folder(row) -> Optional["FolderModel"]:
    """Convert a raw Folder ORM row to FolderModel or return None."""
    return FolderModel.model_validate(row) if row else None


# ---------------------------------------------------------------------------
# SQLAlchemy table
# ---------------------------------------------------------------------------

class Folder(Base):
    """Persistent folder record."""

    __tablename__ = "folder"

    id = Column(Text, primary_key=True)
    parent_id = Column(Text, nullable=True)
    user_id = Column(Text)
    name = Column(Text)
    items = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    is_expanded = Column(Boolean, default=False)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FolderModel(BaseModel):
    """Full folder representation used throughout the application."""

    id: str
    parent_id: Optional[str] = None
    user_id: str
    name: str
    items: Optional[dict] = None
    meta: Optional[dict] = None
    is_expanded: bool = False
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class FolderForm(BaseModel):
    """Payload accepted when creating or renaming a folder."""

    name: str
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------

class FolderTable:
    """CRUD operations for :class:`Folder` records."""

    # -- create -------------------------------------------------------------

    def insert_new_folder(
        self, user_id: str, name: str, parent_id: Optional[str] = None
    ) -> Optional[FolderModel]:
        """Create a folder owned by *user_id* under *parent_id*."""
        with get_db() as db:
            now = _now()
            folder = FolderModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=name,
                parent_id=parent_id,
                created_at=now,
                updated_at=now,
            )
            try:
                result = Folder(**folder.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return _validate_folder(result)
            except Exception:
                log.exception("Failed to insert new folder")
                return None

    # -- read ---------------------------------------------------------------

    def get_folder_by_id_and_user_id(
        self, id: str, user_id: str
    ) -> Optional[FolderModel]:
        """Return a single folder matching both *id* and *user_id*."""
        try:
            with get_db() as db:
                row = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                return _validate_folder(row)
        except Exception:
            return None

    def get_children_folders_by_id_and_user_id(
        self, id: str, user_id: str
    ) -> Optional[list[FolderModel]]:
        """Return all descendant folders (children, grandchildren, …)."""
        try:
            with get_db() as db:
                root = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                if not root:
                    return None

                collected: list[FolderModel] = []

                def _walk(parent: FolderModel) -> None:
                    children = self.get_folders_by_parent_id_and_user_id(
                        parent.id, user_id
                    )
                    for child in children:
                        _walk(child)
                        collected.append(child)

                _walk(root)
                return collected
        except Exception:
            return None

    def get_folders_by_user_id(self, user_id: str) -> list[FolderModel]:
        """Return every folder owned by *user_id*."""
        with get_db() as db:
            return [
                FolderModel.model_validate(f)
                for f in db.query(Folder).filter_by(user_id=user_id).all()
            ]

    def get_folder_by_parent_id_and_user_id_and_name(
        self, parent_id: Optional[str], user_id: str, name: str
    ) -> Optional[FolderModel]:
        """Case-insensitive folder lookup by parent, owner and name."""
        try:
            with get_db() as db:
                row = (
                    db.query(Folder)
                    .filter_by(parent_id=parent_id, user_id=user_id)
                    .filter(Folder.name.ilike(name))
                    .first()
                )
                return _validate_folder(row)
        except Exception:
            log.exception("Failed to look up folder by parent/name")
            return None

    def get_folders_by_parent_id_and_user_id(
        self, parent_id: Optional[str], user_id: str
    ) -> list[FolderModel]:
        """Return immediate child folders of *parent_id* owned by *user_id*."""
        with get_db() as db:
            return [
                FolderModel.model_validate(f)
                for f in db.query(Folder)
                .filter_by(parent_id=parent_id, user_id=user_id)
                .all()
            ]

    # -- update -------------------------------------------------------------

    def update_folder_parent_id_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
        parent_id: str,
    ) -> Optional[FolderModel]:
        """Move a folder to a new parent."""
        try:
            with get_db() as db:
                row = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                if not row:
                    return None
                row.parent_id = parent_id
                row.updated_at = _now()
                db.commit()
                return FolderModel.model_validate(row)
        except Exception:
            log.exception("Failed to update folder parent")
            return None

    def update_folder_name_by_id_and_user_id(
        self, id: str, user_id: str, name: str
    ) -> Optional[FolderModel]:
        """Rename a folder.  Returns None if a sibling already has *name*."""
        try:
            with get_db() as db:
                row = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                if not row:
                    return None

                duplicate = (
                    db.query(Folder)
                    .filter_by(name=name, parent_id=row.parent_id, user_id=user_id)
                    .first()
                )
                if duplicate:
                    return None

                row.name = name
                row.updated_at = _now()
                db.commit()
                return FolderModel.model_validate(row)
        except Exception:
            log.exception("Failed to rename folder")
            return None

    def update_folder_is_expanded_by_id_and_user_id(
        self, id: str, user_id: str, is_expanded: bool
    ) -> Optional[FolderModel]:
        """Toggle the expanded UI state for a folder."""
        try:
            with get_db() as db:
                row = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                if not row:
                    return None
                row.is_expanded = is_expanded
                row.updated_at = _now()
                db.commit()
                return FolderModel.model_validate(row)
        except Exception:
            log.exception("Failed to update folder expanded state")
            return None

    # -- delete -------------------------------------------------------------

    def delete_folder_by_id_and_user_id(
        self, id: str, user_id: str, delete_chats: bool = True
    ) -> bool:
        """Remove a folder and all descendants.

        When *delete_chats* is True the associated chats are also deleted.
        """
        try:
            with get_db() as db:
                root = db.query(Folder).filter_by(id=id, user_id=user_id).first()
                if not root:
                    return False

                def _purge(folder: FolderModel) -> None:
                    children = self.get_folders_by_parent_id_and_user_id(
                        folder.id, user_id
                    )
                    for child in children:
                        if delete_chats:
                            Chats.delete_chats_by_user_id_and_folder_id(
                                user_id, child.id
                            )
                        _purge(child)
                        row = db.query(Folder).filter_by(id=child.id).first()
                        if row:
                            db.delete(row)
                            db.commit()

                if delete_chats:
                    Chats.delete_chats_by_user_id_and_folder_id(user_id, root.id)

                _purge(root)
                db.delete(root)
                db.commit()
                return True
        except Exception:
            log.exception("Failed to delete folder")
            return False


Folders = FolderTable()
