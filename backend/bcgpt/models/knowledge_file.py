"""Knowledge↔File junction table (P2.1).

Replaces the denormalized ``knowledge.data['file_ids']`` JSON list with a real
junction table for referential integrity, reference-counted orphan detection,
and O(1) reverse lookup (which KBs reference a file). The JSON list is retained
as a denormalized cache during the transition (dual-write in the knowledge
router); reads prefer the junction and fall back to the JSON list for KBs that
pre-date the migration backfill.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy import BigInteger, Column, ForeignKey, Text, and_

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


def _now() -> int:
    """Return current UTC epoch seconds."""
    return int(time.time())


class KnowledgeFile(Base):
    """Membership row linking a knowledge base to one of its files."""

    __tablename__ = "knowledge_file"

    knowledge_id = Column(
        Text, ForeignKey("knowledge.id", ondelete="CASCADE"), primary_key=True
    )
    file_id = Column(Text, ForeignKey("file.id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(BigInteger, nullable=False)
    added_by = Column(Text, nullable=True)


class KnowledgeFiles:
    """CRUD for the ``knowledge_file`` junction."""

    @staticmethod
    def add(knowledge_id: str, file_id: str, user_id: Optional[str] = None) -> bool:
        """Idempotently add a membership row. Returns True on success / existing."""
        with get_db() as db:
            try:
                existing = (
                    db.query(KnowledgeFile)
                    .filter(
                        and_(
                            KnowledgeFile.knowledge_id == knowledge_id,
                            KnowledgeFile.file_id == file_id,
                        )
                    )
                    .first()
                )
                if existing:
                    return True
                db.add(
                    KnowledgeFile(
                        knowledge_id=knowledge_id,
                        file_id=file_id,
                        added_at=_now(),
                        added_by=user_id,
                    )
                )
                db.commit()
                return True
            except Exception:
                log.exception("KnowledgeFiles.add failed")
                return False

    @staticmethod
    def remove(knowledge_id: str, file_id: str) -> bool:
        """Remove a single membership row."""
        with get_db() as db:
            try:
                db.query(KnowledgeFile).filter(
                    and_(
                        KnowledgeFile.knowledge_id == knowledge_id,
                        KnowledgeFile.file_id == file_id,
                    )
                ).delete()
                db.commit()
                return True
            except Exception:
                log.exception("KnowledgeFiles.remove failed")
                return False

    @staticmethod
    def remove_knowledge(knowledge_id: str) -> bool:
        """Remove all membership rows for a knowledge base (KB delete)."""
        with get_db() as db:
            try:
                db.query(KnowledgeFile).filter(
                    KnowledgeFile.knowledge_id == knowledge_id
                ).delete()
                db.commit()
                return True
            except Exception:
                log.exception("KnowledgeFiles.remove_knowledge failed")
                return False

    @staticmethod
    def file_ids_for_knowledge(knowledge_id: str) -> list[str]:
        """All file_ids attached to *knowledge_id* (empty list on error)."""
        with get_db() as db:
            try:
                rows = (
                    db.query(KnowledgeFile)
                    .filter(KnowledgeFile.knowledge_id == knowledge_id)
                    .all()
                )
                return [r.file_id for r in rows]
            except Exception:
                log.exception("KnowledgeFiles.file_ids_for_knowledge failed")
                return []

    @staticmethod
    def knowledges_for_file(file_id: str) -> list[str]:
        """All knowledge_ids that reference *file_id* (reference-count / orphan check)."""
        with get_db() as db:
            try:
                rows = (
                    db.query(KnowledgeFile)
                    .filter(KnowledgeFile.file_id == file_id)
                    .all()
                )
                return [r.knowledge_id for r in rows]
            except Exception:
                log.exception("KnowledgeFiles.knowledges_for_file failed")
                return []
