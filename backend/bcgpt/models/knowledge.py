"""Knowledge-base management for RAG document collections.

A knowledge base groups uploaded files and carries its own access-control
policy (public / private / per-group).  The ``data`` JSON column typically
holds file-id references used by the retrieval pipeline.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db
from bcgpt.models import FileMetadataResponse, Users, UserResponse
from bcgpt.utils import has_access

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> int:
    """Return current UTC epoch seconds as an integer."""
    return int(time.time())


def _validate_knowledge(row) -> Optional["KnowledgeModel"]:
    """Convert a raw Knowledge ORM row to KnowledgeModel or return None."""
    return KnowledgeModel.model_validate(row) if row else None


def _enrich_with_user(knowledge: KnowledgeModel) -> "KnowledgeUserModel":
    """Attach the owner's UserResponse to a KnowledgeModel."""
    user = Users.get_user_by_id(knowledge.user_id)
    return KnowledgeUserModel.model_validate(
        {
            **knowledge.model_dump(),
            "user": user.model_dump() if user else None,
        }
    )


# ---------------------------------------------------------------------------
# SQLAlchemy table
# ---------------------------------------------------------------------------


class Knowledge(Base):
    """Persistent knowledge-base record.

    ``access_control`` follows the standard policy pattern:

    * ``None`` — public (any user with the "user" role)
    * ``{}``   — private (owner only)
    * ``{"read": {"group_ids": […]}, "write": {"group_ids": […]}}``
      — fine-grained per-group / per-user rules
    """

    __tablename__ = "knowledge"

    id = Column(Text, unique=True, primary_key=True)
    user_id = Column(Text)

    name = Column(Text)
    description = Column(Text)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    access_control = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class KnowledgeModel(BaseModel):
    """Full knowledge-base representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

    name: str
    description: str

    data: Optional[dict] = None
    meta: Optional[dict] = None

    access_control: Optional[dict] = None

    created_at: int
    updated_at: int


class KnowledgeUserModel(KnowledgeModel):
    """KnowledgeModel extended with owner information."""

    user: Optional[UserResponse] = None


class KnowledgeResponse(KnowledgeModel):
    """Knowledge base with attached file metadata."""

    files: Optional[list[FileMetadataResponse | dict]] = None


class KnowledgeUserResponse(KnowledgeUserModel):
    """Knowledge base with owner info and attached file metadata."""

    files: Optional[list[FileMetadataResponse | dict]] = None


class KnowledgeForm(BaseModel):
    """Payload accepted when creating or updating a knowledge base."""

    name: str
    description: str
    data: Optional[dict] = None
    access_control: Optional[dict] = None


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------


class KnowledgeTable:
    """CRUD operations for :class:`Knowledge` records."""

    # -- create -------------------------------------------------------------

    def insert_new_knowledge(
        self, user_id: str, form_data: KnowledgeForm
    ) -> Optional[KnowledgeModel]:
        """Persist a new knowledge base owned by *user_id*."""
        with get_db() as db:
            now = _now()
            knowledge = KnowledgeModel(
                **form_data.model_dump(),
                id=str(uuid.uuid4()),
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
            try:
                result = Knowledge(**knowledge.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return _validate_knowledge(result)
            except Exception:
                return None

    # -- read ---------------------------------------------------------------

    def get_knowledge_bases(self) -> list[KnowledgeUserModel]:
        """Return all knowledge bases enriched with owner info, newest first."""
        with get_db() as db:
            items: list[KnowledgeUserModel] = []
            for row in db.query(Knowledge).order_by(Knowledge.updated_at.desc()).all():
                model = KnowledgeModel.model_validate(row)
                items.append(_enrich_with_user(model))
            return items

    def get_knowledge_bases_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[KnowledgeUserModel]:
        """Return knowledge bases accessible to *user_id* at *permission* level."""
        return [
            kb
            for kb in self.get_knowledge_bases()
            if kb.user_id == user_id
            or has_access(user_id, permission, kb.access_control)
        ]

    def get_knowledge_by_id(self, id: str) -> Optional[KnowledgeModel]:
        """Look up a single knowledge base by primary key."""
        try:
            with get_db() as db:
                row = db.query(Knowledge).filter_by(id=id).first()
                return _validate_knowledge(row)
        except Exception:
            return None

    # -- update -------------------------------------------------------------

    def update_knowledge_by_id(
        self, id: str, form_data: KnowledgeForm, overwrite: bool = False
    ) -> Optional[KnowledgeModel]:
        """Patch mutable fields on a knowledge base.

        When the caller omits ``data`` (or sends an empty dict) the existing
        file references are preserved so that a name/description update never
        wipes the document collection.
        """
        try:
            with get_db() as db:
                existing = self.get_knowledge_by_id(id=id)
                if not existing:
                    return None

                update_data = form_data.model_dump()
                if not update_data.get("data"):
                    update_data["data"] = existing.data

                db.query(Knowledge).filter_by(id=id).update(
                    {
                        **update_data,
                        "updated_at": _now(),
                    }
                )
                db.commit()
                return self.get_knowledge_by_id(id=id)
        except Exception:
            log.exception("Failed to update knowledge %s", id)
            return None

    def update_knowledge_data_by_id(
        self, id: str, data: dict
    ) -> Optional[KnowledgeModel]:
        """Replace the ``data`` JSON payload of a knowledge base."""
        try:
            with get_db() as db:
                db.query(Knowledge).filter_by(id=id).update(
                    {
                        "data": data,
                        "updated_at": _now(),
                    }
                )
                db.commit()
                return self.get_knowledge_by_id(id=id)
        except Exception:
            log.exception("Failed to update knowledge data for %s", id)
            return None

    # -- delete -------------------------------------------------------------

    def delete_knowledge_by_id(self, id: str) -> bool:
        """Remove a single knowledge base by primary key."""
        try:
            with get_db() as db:
                db.query(Knowledge).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_knowledge(self) -> bool:
        """Remove every knowledge-base row."""
        with get_db() as db:
            try:
                db.query(Knowledge).delete()
                db.commit()
                return True
            except Exception:
                return False


Knowledges = KnowledgeTable()
