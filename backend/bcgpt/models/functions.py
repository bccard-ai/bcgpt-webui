"""Function model and table operations.

Manages Python function (tool) definitions stored in the database, including
their source code, metadata, valves (configuration), and activation state.
Functions can be global or per-user and filtered by type (filter, action, etc.).
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, String, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, JSONField, get_db
from bcgpt.models import Users

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class Function(Base):
    """Persistent representation of a function row."""

    __tablename__ = "function"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    name = Column(Text)
    type = Column(Text)
    content = Column(Text)
    meta = Column(JSONField)
    valves = Column(JSONField)
    is_active = Column(Boolean)
    is_global = Column(Boolean)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FunctionMeta(BaseModel):
    """Metadata describing a function (description and manifest)."""

    description: Optional[str] = None
    manifest: Optional[dict] = {}


class FunctionModel(BaseModel):
    """Full function representation returned to callers."""

    id: str
    user_id: str
    name: str
    type: str
    content: str
    meta: FunctionMeta
    is_active: bool = False
    is_global: bool = False
    updated_at: int  # epoch seconds
    created_at: int  # epoch seconds

    model_config = ConfigDict(from_attributes=True)


class FunctionResponse(BaseModel):
    """Function payload returned in API responses (excludes content)."""

    id: str
    user_id: str
    type: str
    name: str
    meta: FunctionMeta
    is_active: bool
    is_global: bool
    updated_at: int  # epoch seconds
    created_at: int  # epoch seconds


class FunctionForm(BaseModel):
    """Schema for creating or updating a function."""

    id: str
    name: str
    content: str
    meta: FunctionMeta


class FunctionValves(BaseModel):
    """Wrapper for function valve configuration."""

    valves: Optional[dict] = None


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class FunctionsTable:
    """Collection of database helpers for the ``function`` table."""

    def insert_new_function(
        self,
        user_id: str,
        type: str,
        form_data: FunctionForm,
    ) -> Optional[FunctionModel]:
        """Create a new function entry and return its model."""
        function = FunctionModel(
            **{
                **form_data.model_dump(),
                "user_id": user_id,
                "type": type,
                "updated_at": int(time.time()),
                "created_at": int(time.time()),
            }
        )

        try:
            with get_db() as db:
                result = Function(**function.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return FunctionModel.model_validate(result)
                else:
                    return None
        except Exception as e:
            log.exception("Error creating a new function: %s", e)
            return None

    def get_function_by_id(self, id: str) -> Optional[FunctionModel]:
        """Fetch a single function by its primary key."""
        try:
            with get_db() as db:
                function = db.get(Function, id)
                return FunctionModel.model_validate(function)
        except Exception:
            return None

    def get_functions(
        self, active_only: bool = False
    ) -> list[FunctionModel]:
        """Return all functions, optionally filtering to active-only."""
        with get_db() as db:
            if active_only:
                return [
                    FunctionModel.model_validate(function)
                    for function in db.query(Function).filter_by(is_active=True).all()
                ]
            else:
                return [
                    FunctionModel.model_validate(function)
                    for function in db.query(Function).all()
                ]

    def get_functions_by_type(
        self,
        type: str,
        active_only: bool = False,
    ) -> list[FunctionModel]:
        """Return functions of a given type, optionally active-only."""
        with get_db() as db:
            if active_only:
                return [
                    FunctionModel.model_validate(function)
                    for function in db.query(Function)
                    .filter_by(type=type, is_active=True)
                    .all()
                ]
            else:
                return [
                    FunctionModel.model_validate(function)
                    for function in db.query(Function).filter_by(type=type).all()
                ]

    def get_global_filter_functions(self) -> list[FunctionModel]:
        """Return all active global filter functions."""
        with get_db() as db:
            return [
                FunctionModel.model_validate(function)
                for function in db.query(Function)
                .filter_by(type="filter", is_active=True, is_global=True)
                .all()
            ]

    def get_global_action_functions(self) -> list[FunctionModel]:
        """Return all active global action functions."""
        with get_db() as db:
            return [
                FunctionModel.model_validate(function)
                for function in db.query(Function)
                .filter_by(type="action", is_active=True, is_global=True)
                .all()
            ]

    def get_function_valves_by_id(self, id: str) -> Optional[dict]:
        """Return the valve configuration dict for a function, or ``None``."""
        with get_db() as db:
            try:
                function = db.get(Function, id)
                return function.valves if function.valves else {}
            except Exception as e:
                log.exception(
                    "Error getting function valves by id %s: %s", id, e
                )
                return None

    def update_function_valves_by_id(
        self,
        id: str,
        valves: dict,
    ) -> Optional[FunctionValves]:
        """Replace the valve configuration for a function."""
        with get_db() as db:
            try:
                function = db.get(Function, id)
                function.valves = valves
                function.updated_at = int(time.time())
                db.commit()
                db.refresh(function)
                return self.get_function_by_id(id)
            except Exception:
                return None

    def get_user_valves_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
    ) -> Optional[dict]:
        """Retrieve per-user valve overrides for a given function."""
        try:
            user = Users.get_user_by_id(user_id)
            user_settings = user.settings.model_dump() if user.settings else {}

            if "functions" not in user_settings:
                user_settings["functions"] = {}
            if "valves" not in user_settings["functions"]:
                user_settings["functions"]["valves"] = {}

            return user_settings["functions"]["valves"].get(id, {})
        except Exception as e:
            log.exception(
                "Error getting user values by id %s and user id %s: %s",
                id,
                user_id,
                e,
            )
            return None

    def update_user_valves_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
        valves: dict,
    ) -> Optional[dict]:
        """Store per-user valve overrides for a given function."""
        try:
            user = Users.get_user_by_id(user_id)
            user_settings = user.settings.model_dump() if user.settings else {}

            if "functions" not in user_settings:
                user_settings["functions"] = {}
            if "valves" not in user_settings["functions"]:
                user_settings["functions"]["valves"] = {}

            user_settings["functions"]["valves"][id] = valves

            Users.update_user_by_id(user_id, {"settings": user_settings})

            return user_settings["functions"]["valves"][id]
        except Exception as e:
            log.exception(
                "Error updating user valves by id %s and user_id %s: %s",
                id,
                user_id,
                e,
            )
            return None

    def update_function_by_id(
        self,
        id: str,
        updated: dict,
    ) -> Optional[FunctionModel]:
        """Patch a function with arbitrary field updates."""
        with get_db() as db:
            try:
                db.query(Function).filter_by(id=id).update(
                    {
                        **updated,
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()
                return self.get_function_by_id(id)
            except Exception:
                return None

    def deactivate_all_functions(self) -> Optional[bool]:
        """Set ``is_active`` to ``False`` for every function."""
        with get_db() as db:
            try:
                db.query(Function).update(
                    {
                        "is_active": False,
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()
                return True
            except Exception:
                return None

    def delete_function_by_id(self, id: str) -> bool:
        """Delete a function by its primary key."""
        with get_db() as db:
            try:
                db.query(Function).filter_by(id=id).delete()
                db.commit()

                return True
            except Exception:
                return False


Functions = FunctionsTable()
