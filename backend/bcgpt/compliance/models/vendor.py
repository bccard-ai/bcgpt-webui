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


class AIVendor(Base):
    __tablename__ = "ai_vendor"

    id = Column(String, primary_key=True)
    vendor_name = Column(String, nullable=False, index=True)
    service_type = Column(String, nullable=True)
    contact_info = Column(JSON, nullable=True)
    compliance_certifications = Column(JSON, nullable=True)
    data_processing_agreement = Column(Boolean, default=False)
    due_diligence_date = Column(BigInteger, nullable=True)
    due_diligence_result = Column(Text, nullable=True)
    risk_assessment = Column(String, nullable=True)
    status = Column(String, default="active")
    exit_plan = Column(JSON, nullable=True)
    related_inventory_ids = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIVendorModel(BaseModel):
    id: str
    vendor_name: str
    service_type: Optional[str] = None
    contact_info: Optional[dict] = None
    compliance_certifications: Optional[list] = None
    data_processing_agreement: bool = False
    due_diligence_date: Optional[int] = None
    due_diligence_result: Optional[str] = None
    risk_assessment: Optional[str] = None
    status: str = "active"
    exit_plan: Optional[dict] = None
    related_inventory_ids: Optional[list] = None
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIVendorForm(BaseModel):
    vendor_name: str
    service_type: Optional[str] = None
    contact_info: Optional[dict] = None
    compliance_certifications: Optional[list] = None
    data_processing_agreement: bool = False
    due_diligence_date: Optional[int] = None
    due_diligence_result: Optional[str] = None
    risk_assessment: Optional[str] = None
    status: str = "active"
    exit_plan: Optional[dict] = None
    related_inventory_ids: Optional[list] = None


class AIVendorTable:
    def insert(self, form_data: AIVendorForm) -> Optional[AIVendorModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                row = AIVendor(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **form_data.model_dump(),
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIVendorModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIVendorModel]:
        try:
            with get_db() as db:
                row = db.query(AIVendor).filter_by(id=id).first()
                return AIVendorModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_all(self, status: Optional[str] = None) -> list[AIVendorModel]:
        try:
            with get_db() as db:
                query = db.query(AIVendor)
                if status is not None:
                    query = query.filter_by(status=status)
                return [
                    AIVendorModel.model_validate(row)
                    for row in query.order_by(AIVendor.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update(self, id: str, form_data: AIVendorForm) -> Optional[AIVendorModel]:
        try:
            with get_db() as db:
                row = db.query(AIVendor).filter_by(id=id).first()
                if not row:
                    return None

                for field, value in form_data.model_dump(exclude_unset=True).items():
                    setattr(row, field, value)
                row.updated_at = int(time.time() * 1000)

                db.commit()
                db.refresh(row)
                return AIVendorModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def update_status(self, id: str, status: str) -> Optional[AIVendorModel]:
        try:
            with get_db() as db:
                row = db.query(AIVendor).filter_by(id=id).first()
                if not row:
                    return None

                row.status = status
                row.updated_at = int(time.time() * 1000)

                db.commit()
                db.refresh(row)
                return AIVendorModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIVendor).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIVendors = AIVendorTable()
