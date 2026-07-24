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


def _generate_model_card_stub(model_id: str, provider: str, intended_use: str) -> str:
    return f"""# Model Card: {model_id}

## Model Details
- **Model ID**: {model_id}
- **Provider**: {provider or "Unknown"}
- **Version**: (to be filled)
- **License**: (to be filled)
- **Contact**: (to be filled)

## Intended Use
- **Primary Use Cases**: {intended_use or "(to be filled)"}
- **Out-of-Scope Uses**: (to be filled)
- **Foreseeable Misuse**: (to be filled)

## Factors
- **Relevant Factors**: (to be filled — demographic, cultural, technical)

## Metrics
- **Performance Measures**: (to be filled)
- **Thresholds**: (to be filled)

## Evaluation Data
- **Datasets**: (to be filled)
- **Motivation**: (to be filled)
- **Preprocessing**: (to be filled)

## Training Data
- **Summary**: (to be filled — per AI Basic Act Art. 34(1)(2))

## Quantitative Analyses
- **Disaggregated Performance**: (to be filled)

## Ethical Considerations
- **Sensitive Data Use**: (to be filled)
- **Human-Life Impact**: (to be filled)
- **Mitigations**: (to be filled)

## Caveats & Recommendations
- (to be filled)
"""


class AIModelInventory(Base):
    __tablename__ = "ai_model_inventory"

    id = Column(String, primary_key=True)
    model_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    version = Column(String, nullable=True)
    risk_tier = Column(String, nullable=True, index=True)
    is_high_impact = Column(Boolean, default=False)
    high_impact_domain = Column(String, nullable=True)
    business_owner_id = Column(String, nullable=True, index=True)
    data_classification = Column(String, nullable=True)
    intended_use = Column(Text, nullable=True)
    out_of_scope_use = Column(Text, nullable=True)
    validation_status = Column(String, default="draft")
    approved_at = Column(BigInteger, nullable=True)
    approved_by = Column(String, nullable=True)
    model_card_md = Column(Text, nullable=True)
    license_info = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)


class AIModelInventoryModel(BaseModel):
    id: str
    model_id: str
    provider: Optional[str] = None
    display_name: Optional[str] = None
    version: Optional[str] = None
    risk_tier: Optional[str] = None
    is_high_impact: bool = False
    high_impact_domain: Optional[str] = None
    business_owner_id: Optional[str] = None
    data_classification: Optional[str] = None
    intended_use: Optional[str] = None
    out_of_scope_use: Optional[str] = None
    validation_status: str = "draft"
    approved_at: Optional[int] = None
    approved_by: Optional[str] = None
    model_card_md: Optional[str] = None
    license_info: Optional[str] = None
    is_active: bool = True
    created_at: int
    updated_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIModelInventoryForm(BaseModel):
    model_id: str
    provider: Optional[str] = None
    display_name: Optional[str] = None
    version: Optional[str] = None
    risk_tier: Optional[str] = None
    is_high_impact: bool = False
    high_impact_domain: Optional[str] = None
    business_owner_id: Optional[str] = None
    data_classification: Optional[str] = None
    intended_use: Optional[str] = None
    out_of_scope_use: Optional[str] = None
    validation_status: str = "draft"
    approved_by: Optional[str] = None
    model_card_md: Optional[str] = None
    license_info: Optional[str] = None
    is_active: bool = True


class AIModelInventoryTable:
    def insert(
        self, form_data: AIModelInventoryForm
    ) -> Optional[AIModelInventoryModel]:
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                data = form_data.model_dump()

                if not data.get("model_card_md") and data.get("model_id"):
                    data["model_card_md"] = _generate_model_card_stub(
                        data["model_id"],
                        data.get("provider", ""),
                        data.get("intended_use", ""),
                    )

                row = AIModelInventory(
                    id=str(uuid.uuid4()),
                    created_at=now,
                    **data,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return AIModelInventoryModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_by_id(self, id: str) -> Optional[AIModelInventoryModel]:
        try:
            with get_db() as db:
                row = db.query(AIModelInventory).filter_by(id=id).first()
                return AIModelInventoryModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def get_all(self, status: Optional[str] = None) -> list[AIModelInventoryModel]:
        try:
            with get_db() as db:
                query = db.query(AIModelInventory)
                if status is not None:
                    query = query.filter_by(validation_status=status)
                return [
                    AIModelInventoryModel.model_validate(row)
                    for row in query.order_by(AIModelInventory.created_at.desc()).all()
                ]
        except Exception as e:
            log.exception("Error: %s", e)
            return []

    def update_status(
        self, id: str, status: str, approved_by: Optional[str] = None
    ) -> Optional[AIModelInventoryModel]:
        try:
            with get_db() as db:
                row = db.query(AIModelInventory).filter_by(id=id).first()
                if not row:
                    return None

                now = int(time.time() * 1000)
                row.validation_status = status
                row.updated_at = now
                if approved_by is not None:
                    row.approved_by = approved_by
                if status == "approved":
                    row.approved_at = now

                db.commit()
                db.refresh(row)
                return AIModelInventoryModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def update(
        self, id: str, form_data: AIModelInventoryForm
    ) -> Optional[AIModelInventoryModel]:
        try:
            with get_db() as db:
                row = db.query(AIModelInventory).filter_by(id=id).first()
                if not row:
                    return None

                for field, value in form_data.model_dump(exclude_unset=True).items():
                    setattr(row, field, value)
                row.updated_at = int(time.time() * 1000)

                db.commit()
                db.refresh(row)
                return AIModelInventoryModel.model_validate(row)
        except Exception as e:
            log.exception("Error: %s", e)
            return None

    def delete_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                deleted = db.query(AIModelInventory).filter_by(id=id).delete()
                db.commit()
                return bool(deleted)
        except Exception as e:
            log.exception("Error: %s", e)
            return False


AIModelInventories = AIModelInventoryTable()
