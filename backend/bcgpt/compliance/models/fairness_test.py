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


class AIFairnessTest(Base):
    __tablename__ = "ai_fairness_test"

    id = Column(String, primary_key=True)
    test_name = Column(String, nullable=False)
    model_id = Column(String, nullable=True, index=True)
    test_config = Column(JSON, nullable=True)
    status = Column(String, default="pending")
    started_at = Column(BigInteger, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    results = Column(JSON, nullable=True)
    metrics_summary = Column(JSON, nullable=True)
    threshold_passed = Column(Boolean, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIFairnessTestModel(BaseModel):
    id: str
    test_name: str
    model_id: Optional[str] = None
    test_config: Optional[dict] = None
    status: str = "pending"
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    results: Optional[dict] = None
    metrics_summary: Optional[dict] = None
    threshold_passed: Optional[bool] = None
    created_by: Optional[str] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIFairnessTestForm(BaseModel):
    test_name: str
    model_id: Optional[str] = None
    test_config: Optional[dict] = None
    status: str = "pending"
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    results: Optional[dict] = None
    metrics_summary: Optional[dict] = None
    threshold_passed: Optional[bool] = None
    created_by: Optional[str] = None


class AIFairnessTestTable:
    def insert(self, form_data: AIFairnessTestForm) -> Optional[AIFairnessTestModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                row = AIFairnessTest(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **form_data.model_dump(),
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIFairnessTestModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIFairnessTestModel]:
        try:
            with get_db() as db:
                row = db.query(AIFairnessTest).filter_by(id=id).first()
                return AIFairnessTestModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_all(self, status: Optional[str] = None) -> list[AIFairnessTestModel]:
        try:
            with get_db() as db:
                query = db.query(AIFairnessTest)
                if status is not None:
                    query = query.filter_by(status=status)
                return [
                    AIFairnessTestModel.model_validate(row)
                    for row in query.order_by(AIFairnessTest.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update_status(self, id: str, status: str) -> Optional[AIFairnessTestModel]:
        try:
            with get_db() as db:
                row = db.query(AIFairnessTest).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.status = status
                row.updated_at = now
                if status == "running" and row.started_at is None:
                    row.started_at = now
                if status in ["completed", "failed"] and row.completed_at is None:
                    row.completed_at = now

                db.commit()
                db.refresh(row)
                return AIFairnessTestModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def update_results(
        self,
        id: str,
        results: Optional[dict] = None,
        metrics_summary: Optional[dict] = None,
        threshold_passed: Optional[bool] = None,
    ) -> Optional[AIFairnessTestModel]:
        try:
            with get_db() as db:
                row = db.query(AIFairnessTest).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.results = results
                row.metrics_summary = metrics_summary
                row.threshold_passed = threshold_passed
                row.status = "completed"
                row.completed_at = now
                row.updated_at = now

                db.commit()
                db.refresh(row)
                return AIFairnessTestModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_latest_by_model(self, model_id: str) -> Optional[AIFairnessTestModel]:
        try:
            with get_db() as db:
                row = (
                    db.query(AIFairnessTest)
                    .filter_by(model_id=model_id)
                    .order_by(AIFairnessTest.created_at.desc())
                    .first()
                )
                return AIFairnessTestModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIFairnessTest).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIFairnessTests = AIFairnessTestTable()
