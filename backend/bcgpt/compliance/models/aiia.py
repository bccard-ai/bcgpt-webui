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


class AIIARecord(Base):
    __tablename__ = "aiia_record"

    id = Column(String, primary_key=True)
    inventory_id = Column(String, nullable=False, index=True)
    assessor_id = Column(String, nullable=False)
    assessment_version = Column(String, default="1.0")
    status = Column(String, default="draft")
    intended_purpose = Column(Text, nullable=True)
    user_population = Column(Text, nullable=True)
    high_impact_domain = Column(String, nullable=True)
    risk_scenarios = Column(JSON, nullable=True)
    mitigation_measures = Column(JSON, nullable=True)
    residual_risk = Column(String, nullable=True)
    next_review_date = Column(BigInteger, nullable=True)
    review_notes = Column(Text, nullable=True)
    approved_at = Column(BigInteger, nullable=True)
    approved_by = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIIARecordModel(BaseModel):
    id: str
    inventory_id: str
    assessor_id: str
    assessment_version: str = "1.0"
    status: str = "draft"
    intended_purpose: Optional[str] = None
    user_population: Optional[str] = None
    high_impact_domain: Optional[str] = None
    risk_scenarios: Optional[list] = None
    mitigation_measures: Optional[list] = None
    residual_risk: Optional[str] = None
    next_review_date: Optional[int] = None
    review_notes: Optional[str] = None
    approved_at: Optional[int] = None
    approved_by: Optional[str] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIIARecordForm(BaseModel):
    inventory_id: str
    assessor_id: str
    assessment_version: str = "1.0"
    status: str = "draft"
    intended_purpose: Optional[str] = None
    user_population: Optional[str] = None
    high_impact_domain: Optional[str] = None
    risk_scenarios: Optional[list] = None
    mitigation_measures: Optional[list] = None
    residual_risk: Optional[str] = None
    next_review_date: Optional[int] = None
    review_notes: Optional[str] = None
    approved_by: Optional[str] = None


class AIIARecordTable:
    def insert(self, form_data: AIIARecordForm) -> Optional[AIIARecordModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                data = form_data.model_dump()
                if data.get("next_review_date") is None:
                    data["next_review_date"] = now + (365 * 24 * 60 * 60 * 1000)
                row = AIIARecord(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **data,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIIARecordModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIIARecordModel]:
        try:
            with get_db() as db:
                row = db.query(AIIARecord).filter_by(id=id).first()
                return AIIARecordModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_inventory_id(self, inventory_id: str) -> list[AIIARecordModel]:
        try:
            with get_db() as db:
                return [
                    AIIARecordModel.model_validate(row)
                    for row in db.query(AIIARecord)
                    .filter_by(inventory_id=inventory_id)
                    .order_by(AIIARecord.created_at.desc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def get_all(self, status: Optional[str] = None) -> list[AIIARecordModel]:
        try:
            with get_db() as db:
                query = db.query(AIIARecord)
                if status is not None:
                    query = query.filter_by(status=status)
                return [
                    AIIARecordModel.model_validate(row)
                    for row in query.order_by(AIIARecord.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update_status(
        self, id: str, status: str, approved_by: Optional[str] = None
    ) -> Optional[AIIARecordModel]:
        try:
            with get_db() as db:
                row = db.query(AIIARecord).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.status = status
                row.updated_at = now
                if approved_by is not None:
                    row.approved_by = approved_by
                if status == "approved":
                    row.approved_at = now

                db.commit()
                db.refresh(row)
                return AIIARecordModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_expired(self) -> list[AIIARecordModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                return [
                    AIIARecordModel.model_validate(row)
                    for row in db.query(AIIARecord)
                    .filter(
                        AIIARecord.next_review_date < now,
                        AIIARecord.status == "approved",
                    )
                    .order_by(AIIARecord.next_review_date.asc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIIARecord).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIIARecords = AIIARecordTable()
