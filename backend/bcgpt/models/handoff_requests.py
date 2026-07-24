import logging
import time
import uuid
from typing import Optional

from bcgpt.internal import Base, get_db

from bcgpt.env import SRC_LOG_LEVELS
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Column, String, Text, JSON, func

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


############################
# HandoffRequest DB Schema
############################


class HandoffRequest(Base):
    __tablename__ = "handoff_request"

    id = Column(String, primary_key=True)
    chat_id = Column(String, nullable=False, index=True)
    message_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending|accepted|resolved|dismissed
    assigned_to = Column(String, nullable=True)
    chat_snapshot = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)
    resolved_at = Column(BigInteger, nullable=True)
    # 'metadata' is reserved by SQLAlchemy's Declarative API (Base.metadata), so the
    # Python attribute is 'request_metadata' while the DB column stays "metadata".
    request_metadata = Column("metadata", JSON, nullable=True)


class HandoffRequestModel(BaseModel):
    id: str
    chat_id: str
    message_id: str
    user_id: str
    reason: Optional[str] = None
    status: str = "pending"
    assigned_to: Optional[str] = None
    chat_snapshot: Optional[dict] = None
    created_at: int
    updated_at: Optional[int] = None
    resolved_at: Optional[int] = None
    # Read from the SQLAlchemy attribute `request_metadata` (the DB column is "metadata",
    # but `.metadata` on a declarative object is the reserved Base.metadata registry).
    # Serialize back out as "metadata" to preserve the API contract.
    request_metadata: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="metadata",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


############################
# Forms
############################


class HandoffRequestForm(BaseModel):
    chat_id: str
    message_id: str
    reason: Optional[str] = None
    chat_snapshot: Optional[dict] = None
    request_metadata: Optional[dict] = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class HandoffStatusUpdateForm(BaseModel):
    status: str  # accepted|resolved|dismissed
    assigned_to: Optional[str] = None


class HandoffRequestsTable:
    def insert_new_request(
        self, user_id: str, form_data: HandoffRequestForm
    ) -> Optional[HandoffRequestModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            request = HandoffRequestModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "status": "pending",
                    **form_data.model_dump(),
                    "created_at": now,
                }
            )
            try:
                result = HandoffRequest(**request.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return HandoffRequestModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error creating a new handoff request: {e}")
                return None

    def get_request_by_id(self, id: str) -> Optional[HandoffRequestModel]:
        try:
            with get_db() as db:
                request = db.query(HandoffRequest).filter_by(id=id).first()
                if not request:
                    return None
                return HandoffRequestModel.model_validate(request)
        except Exception:
            return None

    def get_pending_requests(
        self, limit: int = 50, offset: int = 0
    ) -> list[HandoffRequestModel]:
        with get_db() as db:
            return [
                HandoffRequestModel.model_validate(r)
                for r in db.query(HandoffRequest)
                .filter_by(status="pending")
                .order_by(HandoffRequest.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def get_requests_by_user_id(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[HandoffRequestModel]:
        with get_db() as db:
            return [
                HandoffRequestModel.model_validate(r)
                for r in db.query(HandoffRequest)
                .filter_by(user_id=user_id)
                .order_by(HandoffRequest.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def get_requests_by_chat_id(self, chat_id: str) -> list[HandoffRequestModel]:
        with get_db() as db:
            return [
                HandoffRequestModel.model_validate(r)
                for r in db.query(HandoffRequest)
                .filter_by(chat_id=chat_id)
                .order_by(HandoffRequest.created_at.desc())
                .all()
            ]

    def get_all_requests(
        self, limit: int = 50, offset: int = 0
    ) -> list[HandoffRequestModel]:
        with get_db() as db:
            return [
                HandoffRequestModel.model_validate(r)
                for r in db.query(HandoffRequest)
                .order_by(HandoffRequest.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def update_request_status(
        self,
        id: str,
        status: str,
        assigned_to: Optional[str] = None,
    ) -> Optional[HandoffRequestModel]:
        with get_db() as db:
            request = db.query(HandoffRequest).filter_by(id=id).first()
            if not request:
                return None

            request.status = status
            request.updated_at = int(time.time() * 1000)

            if assigned_to is not None:
                request.assigned_to = assigned_to

            if status == "resolved":
                request.resolved_at = int(time.time() * 1000)

            db.commit()
            return HandoffRequestModel.model_validate(request)

    def get_handoff_stats(self) -> dict:
        with get_db() as db:
            requests = db.query(HandoffRequest).all()

            by_status: dict[str, int] = {}
            total_resolution_time_ms = 0
            resolved_count = 0

            for r in requests:
                by_status[r.status] = by_status.get(r.status, 0) + 1
                if r.status == "resolved" and r.resolved_at and r.created_at:
                    total_resolution_time_ms += r.resolved_at - r.created_at
                    resolved_count += 1

            avg_resolution_time_ms = (
                total_resolution_time_ms / resolved_count if resolved_count > 0 else 0
            )

            return {
                "total": len(requests),
                "by_status": by_status,
                "avg_resolution_time_ms": avg_resolution_time_ms,
            }

    def count_pending(self) -> int:
        with get_db() as db:
            return (
                db.query(func.count(HandoffRequest.id))
                .filter(HandoffRequest.status == "pending")
                .scalar()
                or 0
            )


HandoffRequests = HandoffRequestsTable()
