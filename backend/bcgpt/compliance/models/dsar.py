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


class AIDSARRequest(Base):
    __tablename__ = "ai_dsar_request"

    id = Column(String, primary_key=True)
    request_type = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, default="pending")
    requested_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger, nullable=True)
    export_url = Column(String, nullable=True)
    export_expires_at = Column(BigInteger, nullable=True)
    details = Column(JSON, nullable=True)
    handled_by = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIDSARRequestModel(BaseModel):
    id: str
    request_type: str
    user_id: str
    status: str = "pending"
    requested_at: int
    completed_at: Optional[int] = None
    export_url: Optional[str] = None
    export_expires_at: Optional[int] = None
    details: Optional[dict] = None
    handled_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIDSARRequestForm(BaseModel):
    request_type: str
    user_id: str
    status: str = "pending"
    requested_at: Optional[int] = None
    completed_at: Optional[int] = None
    export_url: Optional[str] = None
    export_expires_at: Optional[int] = None
    details: Optional[dict] = None
    handled_by: Optional[str] = None
    rejection_reason: Optional[str] = None


class AIDSARRequestTable:
    def insert(self, form_data: AIDSARRequestForm) -> Optional[AIDSARRequestModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                data = form_data.model_dump()
                if data.get("requested_at") is None:
                    data["requested_at"] = now
                row = AIDSARRequest(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **data,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIDSARRequestModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIDSARRequestModel]:
        try:
            with get_db() as db:
                row = db.query(AIDSARRequest).filter_by(id=id).first()
                return AIDSARRequestModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_user_id(self, user_id: str) -> list[AIDSARRequestModel]:
        try:
            with get_db() as db:
                return [
                    AIDSARRequestModel.model_validate(row)
                    for row in db.query(AIDSARRequest)
                    .filter_by(user_id=user_id)
                    .order_by(AIDSARRequest.created_at.desc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def get_all(self, status: Optional[str] = None) -> list[AIDSARRequestModel]:
        try:
            with get_db() as db:
                query = db.query(AIDSARRequest)
                if status is not None:
                    query = query.filter_by(status=status)
                return [
                    AIDSARRequestModel.model_validate(row)
                    for row in query.order_by(AIDSARRequest.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update_status(
        self,
        id: str,
        status: str,
        handled_by: Optional[str] = None,
        export_url: Optional[str] = None,
        export_expires_at: Optional[int] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[AIDSARRequestModel]:
        try:
            with get_db() as db:
                row = db.query(AIDSARRequest).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.status = status
                row.updated_at = now
                if handled_by is not None:
                    row.handled_by = handled_by
                if export_url is not None:
                    row.export_url = export_url
                if export_expires_at is not None:
                    row.export_expires_at = export_expires_at
                if rejection_reason is not None:
                    row.rejection_reason = rejection_reason
                if status in ["completed", "rejected"] and row.completed_at is None:
                    row.completed_at = now

                db.commit()
                db.refresh(row)
                return AIDSARRequestModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIDSARRequest).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIDSARRequests = AIDSARRequestTable()
