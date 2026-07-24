import hashlib
import json
import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Float, Integer, JSON, String, Text

from bcgpt.internal import Base, get_db
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

_RETENTION_10_YEARS_MS = 365 * 10 * 24 * 60 * 60 * 1000


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_signature(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AIRAGProvenance(Base):
    __tablename__ = "ai_rag_provenance"

    id = Column(String, primary_key=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    model_name = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    prompt_hash = Column(String, nullable=True)
    query_text = Column(Text, nullable=True)
    retrieved_chunks = Column(JSON, nullable=True)
    response_hash = Column(String, nullable=True)
    response_text = Column(Text, nullable=True)
    total_tokens = Column(Integer, default=0)
    retention_until = Column(BigInteger, nullable=True)
    signature = Column(String, nullable=True)
    related_chat_id = Column(String, nullable=True, index=True)
    created_at = Column(BigInteger, nullable=False)


class AIRAGProvenanceModel(BaseModel):
    id: str
    timestamp: int
    user_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    query_text: Optional[str] = None
    retrieved_chunks: Optional[list] = None
    response_hash: Optional[str] = None
    response_text: Optional[str] = None
    total_tokens: int = 0
    retention_until: Optional[int] = None
    signature: Optional[str] = None
    related_chat_id: Optional[str] = None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class AIRAGProvenanceForm(BaseModel):
    timestamp: Optional[int] = None
    user_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    query_text: Optional[str] = None
    retrieved_chunks: Optional[list] = None
    response_hash: Optional[str] = None
    response_text: Optional[str] = None
    total_tokens: int = 0
    retention_until: Optional[int] = None
    signature: Optional[str] = None
    related_chat_id: Optional[str] = None


class AIRAGProvenanceTable:
    def insert(self, form_data: AIRAGProvenanceForm) -> Optional[AIRAGProvenanceModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                data = form_data.model_dump()

                if data.get("timestamp") is None:
                    data["timestamp"] = now

                if data.get("retention_until") is None:
                    data["retention_until"] = now + _RETENTION_10_YEARS_MS

                query_text = data.get("query_text") or ""
                if data.get("prompt_hash") is None and query_text:
                    data["prompt_hash"] = _sha256(query_text)

                response_text = data.get("response_text") or ""
                if data.get("response_hash") is None and response_text:
                    data["response_hash"] = _sha256(response_text)

                sig_source = {k: v for k, v in data.items() if k != "signature"}
                data["signature"] = _compute_signature(sig_source)

                row = AIRAGProvenance(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **data,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIRAGProvenanceModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIRAGProvenanceModel]:
        try:
            with get_db() as db:
                row = db.query(AIRAGProvenance).filter_by(id=id).first()
                return AIRAGProvenanceModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_chat_id(self, chat_id: str) -> list[AIRAGProvenanceModel]:
        try:
            with get_db() as db:
                return [
                    AIRAGProvenanceModel.model_validate(row)
                    for row in db.query(AIRAGProvenance)
                    .filter_by(related_chat_id=chat_id)
                    .order_by(AIRAGProvenance.timestamp.desc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def get_by_user_id(self, user_id: str) -> list[AIRAGProvenanceModel]:
        try:
            with get_db() as db:
                return [
                    AIRAGProvenanceModel.model_validate(row)
                    for row in db.query(AIRAGProvenance)
                    .filter_by(user_id=user_id)
                    .order_by(AIRAGProvenance.timestamp.desc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def purge_expired(self) -> int:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                deleted = (
                    db.query(AIRAGProvenance)
                    .filter(AIRAGProvenance.retention_until < now)
                    .delete(synchronize_session=False)
                )
                db.commit()
                return int(deleted or 0)
        except Exception as e:
            log.exception("Error: %s", e)
            return 0

    def count_records(self) -> int:
        try:
            with get_db() as db:
                return int(db.query(AIRAGProvenance).count() or 0)
        except Exception as e:
            log.exception("Error: %s", e)
            return 0

    def record_from_chat(
        self,
        *,
        user_id: str,
        model_name: str,
        query: str,
        response: str,
        sources: Optional[list[dict]] = None,
        total_tokens: int = 0,
        chat_id: Optional[str] = None,
    ) -> Optional[AIRAGProvenanceModel]:
        """Convenience method for middleware to record a RAG-augmented chat.

        Auto-computes SHA-256 hashes for prompt/response, builds a chunk
        reference list from sources, and sets 10-year retention.
        """
        chunks = []
        if sources:
            for i, src in enumerate(sources):
                chunks.append(
                    {
                        "chunk_id": src.get("id", src.get("chunk_id", "")),
                        "doc_id": src.get("file_id", src.get("doc_id", "")),
                        "page": src.get("page"),
                        "similarity": src.get("score", src.get("similarity")),
                        "retrieval_rank": i,
                    }
                )

        form = AIRAGProvenanceForm(
            user_id=user_id,
            model_name=model_name,
            query_text=query[:4096],
            response_text=response[:8192],
            retrieved_chunks=chunks if chunks else None,
            total_tokens=total_tokens,
            related_chat_id=chat_id,
        )
        return self.insert(form)


AIRAGProvenances = AIRAGProvenanceTable()
