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

_MS_PER_SEC = 1000
_SEC_PER_DAY = 86400

_REGIME_DEADLINES = {
    "eu_ai_act_2d": 2 * _SEC_PER_DAY,
    "eu_ai_act_15d": 15 * _SEC_PER_DAY,
    "pipa_72h": 72 * 3600,
    "credit_info_3d": 3 * _SEC_PER_DAY,
    "ai_basic_act": 0,
    "none": 0,
}

_CATEGORY_REGIME_MAP = {
    "pii_leak": "pipa_72h",
    "credit_info_leak": "credit_info_3d",
    "critical_infra": "eu_ai_act_2d",
    "hallucination_harm": "eu_ai_act_15d",
    "prompt_injection": "eu_ai_act_15d",
    "model_drift": "none",
    "bias": "eu_ai_act_15d",
    "other": "none",
}


def classify_reporting_regime(category: Optional[str]) -> str:
    if not category:
        return "none"
    return _CATEGORY_REGIME_MAP.get(category, "none")


def compute_reporting_deadline(regime: str, detected_at_ms: int) -> Optional[int]:
    seconds = _REGIME_DEADLINES.get(regime, 0)
    if seconds <= 0:
        return None
    return detected_at_ms + seconds * _MS_PER_SEC


class AIIncident(Base):
    __tablename__ = "ai_incident"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, default="medium")
    category = Column(String, nullable=True)
    status = Column(String, default="detected")
    detected_at = Column(BigInteger, nullable=False)
    detected_by = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    timeline = Column(JSON, nullable=True)
    reporting_regime = Column(String, nullable=True)
    reporting_deadline = Column(BigInteger, nullable=True)
    reported_at = Column(BigInteger, nullable=True)
    report_reference = Column(String, nullable=True)
    forensic_evidence = Column(JSON, nullable=True)
    related_chat_id = Column(String, nullable=True, index=True)
    related_user_id = Column(String, nullable=True, index=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIIncidentModel(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    category: Optional[str] = None
    status: str = "detected"
    detected_at: int
    detected_by: Optional[str] = None
    assigned_to: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    timeline: Optional[list] = None
    reporting_regime: Optional[str] = None
    reporting_deadline: Optional[int] = None
    reported_at: Optional[int] = None
    report_reference: Optional[str] = None
    forensic_evidence: Optional[dict] = None
    related_chat_id: Optional[str] = None
    related_user_id: Optional[str] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIIncidentForm(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    category: Optional[str] = None
    status: str = "detected"
    detected_at: Optional[int] = None
    detected_by: Optional[str] = None
    assigned_to: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    timeline: Optional[list] = None
    reporting_regime: Optional[str] = None
    reporting_deadline: Optional[int] = None
    reported_at: Optional[int] = None
    report_reference: Optional[str] = None
    forensic_evidence: Optional[dict] = None
    related_chat_id: Optional[str] = None
    related_user_id: Optional[str] = None


class AIIncidentTable:
    def insert(self, form_data: AIIncidentForm) -> Optional[AIIncidentModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                data = form_data.model_dump()
                if data.get("detected_at") is None:
                    data["detected_at"] = now

                if not data.get("reporting_regime"):
                    data["reporting_regime"] = classify_reporting_regime(
                        data.get("category")
                    )

                if not data.get("reporting_deadline") and data.get("reporting_regime"):
                    data["reporting_deadline"] = compute_reporting_deadline(
                        data["reporting_regime"], data["detected_at"]
                    )

                row = AIIncident(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **data,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIIncidentModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIIncidentModel]:
        try:
            with get_db() as db:
                row = db.query(AIIncident).filter_by(id=id).first()
                return AIIncidentModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_all(
        self, status: Optional[str] = None, severity: Optional[str] = None
    ) -> list[AIIncidentModel]:
        try:
            with get_db() as db:
                query = db.query(AIIncident)
                if status is not None:
                    query = query.filter_by(status=status)
                if severity is not None:
                    query = query.filter_by(severity=severity)
                return [
                    AIIncidentModel.model_validate(row)
                    for row in query.order_by(AIIncident.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update_status(
        self, id: str, status: str, assigned_to: Optional[str] = None
    ) -> Optional[AIIncidentModel]:
        try:
            with get_db() as db:
                row = db.query(AIIncident).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.status = status
                row.updated_at = now
                if assigned_to is not None:
                    row.assigned_to = assigned_to
                if status == "reported" and row.reported_at is None:
                    row.reported_at = now

                db.commit()
                db.refresh(row)
                return AIIncidentModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def add_timeline_event(
        self,
        id: str,
        event: str,
        actor: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> Optional[AIIncidentModel]:
        try:
            with get_db() as db:
                row = db.query(AIIncident).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                events = (
                    list(row.timeline or []) if isinstance(row.timeline, list) else []
                )
                events.append(
                    {
                        "timestamp": timestamp or now,
                        "event": event,
                        "actor": actor,
                    }
                )
                row.timeline = events
                row.updated_at = now

                db.commit()
                db.refresh(row)
                return AIIncidentModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_overdue(self) -> list[AIIncidentModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                return [
                    AIIncidentModel.model_validate(row)
                    for row in db.query(AIIncident)
                    .filter(
                        AIIncident.reporting_deadline < now,
                        AIIncident.status.notin_(["reported", "closed"]),
                    )
                    .order_by(AIIncident.reporting_deadline.asc())
                    .all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def get_stats(self) -> dict:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                rows = db.query(AIIncident).all()
                by_status: dict[str, int] = {}
                by_severity: dict[str, int] = {}
                overdue = 0

                for row in rows:
                    status = row.status or "unknown"
                    severity = row.severity or "unknown"
                    by_status[status] = by_status.get(status, 0) + 1
                    by_severity[severity] = by_severity.get(severity, 0) + 1
                    if (
                        row.reporting_deadline
                        and row.reporting_deadline < now
                        and row.status not in ["reported", "closed"]
                    ):
                        overdue += 1

                return {
                    "total": len(rows),
                    "by_status": by_status,
                    "by_severity": by_severity,
                    "overdue": overdue,
                }
        except Exception as e:
            log.exception("Error: %s", e)
            return {"total": 0, "by_status": {}, "by_severity": {}, "overdue": 0}

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIIncident).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIIncidents = AIIncidentTable()
