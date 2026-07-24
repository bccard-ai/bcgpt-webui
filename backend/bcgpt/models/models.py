"""Custom model definitions that wrap or extend base LLM providers.

A "model" row represents a user-defined model configuration that may point
to a real LLM provider via ``base_model_id`` or stand alone as a virtual
model.  The ``params`` and ``meta`` JSON columns store arbitrary
configuration and display metadata respectively.
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, JSONField, get_db
from bcgpt.models import Users, UserResponse
from bcgpt.utils import has_access

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> int:
    """Return current UTC epoch seconds as an integer."""
    return int(time.time())


def _validate_model(row) -> Optional["ModelModel"]:
    """Convert a raw Model ORM row to ModelModel or return None."""
    return ModelModel.model_validate(row) if row else None


def _enrich_with_user(model: "ModelModel") -> "ModelUserResponse":
    """Attach the owner's UserResponse to a ModelModel."""
    user = Users.get_user_by_id(model.user_id)
    return ModelUserResponse.model_validate(
        {
            **model.model_dump(),
            "user": user.model_dump() if user else None,
        }
    )


# ---------------------------------------------------------------------------
# Pydantic value objects
# ---------------------------------------------------------------------------

class ModelParams(BaseModel):
    """Arbitrary key/value parameters stored in the ``params`` JSON column."""

    model_config = ConfigDict(extra="allow")


class ModelMeta(BaseModel):
    """Display metadata stored in the ``meta`` JSON column."""

    profile_image_url: Optional[str] = "/static/favicon.png"
    description: Optional[str] = None
    capabilities: Optional[dict] = None

    autonomy_level: Optional[str] = None
    """Agent autonomy tier: ``"suggest"`` | ``"assistant"`` | ``"operator"``."""

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# SQLAlchemy table
# ---------------------------------------------------------------------------

class Model(Base):
    """Persistent model-definition record.

    ``access_control`` follows the standard policy pattern:

    * ``None`` — public (any user with the "user" role)
    * ``{}``   — private (owner only)
    * ``{"read": {"group_ids": […]}, "write": {"group_ids": […]}}``
      — fine-grained per-group / per-user rules
    """

    __tablename__ = "model"

    id = Column(Text, primary_key=True)
    user_id = Column(Text)

    base_model_id = Column(Text, nullable=True)
    name = Column(Text)

    params = Column(JSONField)
    meta = Column(JSONField)

    access_control = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ModelModel(BaseModel):
    """Full model representation used throughout the application."""

    id: str
    user_id: str
    base_model_id: Optional[str] = None

    name: str
    params: ModelParams
    meta: ModelMeta

    access_control: Optional[dict] = None

    is_active: bool
    updated_at: int
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class ModelUserResponse(ModelModel):
    """ModelModel extended with owner information."""

    user: Optional[UserResponse] = None


class ModelResponse(ModelModel):
    """Alias kept for API backward compatibility."""

    pass


class ModelForm(BaseModel):
    """Payload accepted when creating or updating a model."""

    id: str
    base_model_id: Optional[str] = None
    name: str
    meta: ModelMeta
    params: ModelParams
    access_control: Optional[dict] = None
    is_active: bool = True


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------

class ModelsTable:
    """CRUD operations for :class:`Model` records."""

    # -- create -------------------------------------------------------------

    def insert_new_model(
        self, form_data: ModelForm, user_id: str
    ) -> Optional[ModelModel]:
        """Persist a new model definition owned by *user_id*."""
        model = ModelModel(
            **form_data.model_dump(),
            user_id=user_id,
            created_at=_now(),
            updated_at=_now(),
        )
        try:
            with get_db() as db:
                result = Model(**model.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return _validate_model(result)
        except Exception:
            log.exception("Failed to insert new model")
            return None

    # -- read ---------------------------------------------------------------

    def get_all_models(self) -> list[ModelModel]:
        """Return every model definition (active and inactive)."""
        with get_db() as db:
            return [
                ModelModel.model_validate(m) for m in db.query(Model).all()
            ]

    def get_models(self) -> list[ModelUserResponse]:
        """Return derived models (those with a ``base_model_id``) enriched with owner info."""
        with get_db() as db:
            results: list[ModelUserResponse] = []
            for row in db.query(Model).filter(Model.base_model_id != None).all():
                results.append(_enrich_with_user(ModelModel.model_validate(row)))
            return results

    def get_base_models(self) -> list[ModelModel]:
        """Return top-level models (those without a ``base_model_id``)."""
        with get_db() as db:
            return [
                ModelModel.model_validate(m)
                for m in db.query(Model).filter(Model.base_model_id == None).all()
            ]

    def get_models_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[ModelUserResponse]:
        """Return derived models accessible to *user_id* at *permission* level."""
        return [
            m
            for m in self.get_models()
            if m.user_id == user_id
            or has_access(user_id, permission, m.access_control)
        ]

    def get_model_by_id(self, id: str) -> Optional[ModelModel]:
        """Look up a single model by primary key."""
        try:
            with get_db() as db:
                row = db.get(Model, id)
                return ModelModel.model_validate(row)
        except Exception:
            return None

    # -- update -------------------------------------------------------------

    def toggle_model_by_id(self, id: str) -> Optional[ModelModel]:
        """Flip the ``is_active`` flag on a model."""
        with get_db() as db:
            try:
                current = db.query(Model).filter_by(id=id).first()
                if not current:
                    return None
                current.is_active = not current.is_active
                current.updated_at = _now()
                db.commit()
                return self.get_model_by_id(id)
            except Exception:
                return None

    def update_model_by_id(self, id: str, model: ModelForm) -> Optional[ModelModel]:
        """Replace mutable fields on a model from *model*."""
        try:
            with get_db() as db:
                db.query(Model).filter_by(id=id).update(
                    model.model_dump(exclude={"id"})
                )
                db.commit()
                row = db.get(Model, id)
                db.refresh(row)
                return ModelModel.model_validate(row)
        except Exception:
            log.exception("Failed to update model %s", id)
            return None

    # -- delete -------------------------------------------------------------

    def delete_model_by_id(self, id: str) -> bool:
        """Remove a single model definition."""
        try:
            with get_db() as db:
                db.query(Model).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_models(self) -> bool:
        """Remove every model definition."""
        try:
            with get_db() as db:
                db.query(Model).delete()
                db.commit()
                return True
        except Exception:
            return False


Models = ModelsTable()
