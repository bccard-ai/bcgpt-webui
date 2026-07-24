"""Tool management for BYOF (Bring Your Own Function) Python tools.

Each tool stores its Python source in ``content`` and parsed OpenAI-style
function specs in ``specs``.  Runtime valves (configuration overrides) are
kept in the ``valves`` JSON column, while per-user valve overrides are
stored inside the user's ``settings`` JSON blob.
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, String, Text

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


def _validate_tool(row) -> Optional["ToolModel"]:
    """Convert a raw Tool ORM row to ToolModel or return None."""
    return ToolModel.model_validate(row) if row else None


def _enrich_with_user(tool: "ToolModel") -> "ToolUserModel":
    """Attach the owner's UserResponse to a ToolModel."""
    user = Users.get_user_by_id(tool.user_id)
    return ToolUserModel.model_validate(
        {
            **tool.model_dump(),
            "user": user.model_dump() if user else None,
        }
    )


def _get_user_tools_settings(user_id: str) -> tuple[dict, dict]:
    """Return ``(user_settings, tools_valves)`` for a given user.

    Ensures the nested ``settings.tools.valves`` path exists.
    """
    user = Users.get_user_by_id(user_id)
    settings = user.settings.model_dump() if user.settings else {}
    settings.setdefault("tools", {})
    settings["tools"].setdefault("valves", {})
    return settings, settings["tools"]["valves"]


# ---------------------------------------------------------------------------
# SQLAlchemy table
# ---------------------------------------------------------------------------

class Tool(Base):
    """Persistent tool record.

    ``access_control`` follows the standard policy pattern:

    * ``None`` — public (any user with the "user" role)
    * ``{}``   — private (owner only)
    * ``{"read": {"group_ids": […]}, "write": {"group_ids": […]}}``
      — fine-grained per-group / per-user rules
    """

    __tablename__ = "tool"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    name = Column(Text)
    content = Column(Text)
    specs = Column(JSONField)
    meta = Column(JSONField)
    valves = Column(JSONField)

    access_control = Column(JSON, nullable=True)

    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ToolMeta(BaseModel):
    """Tool display metadata stored in the ``meta`` JSON column."""

    description: Optional[str] = None
    manifest: Optional[dict] = {}


class ToolModel(BaseModel):
    """Full tool representation used throughout the application."""

    id: str
    user_id: str
    name: str
    content: str
    specs: list[dict]
    meta: ToolMeta
    access_control: Optional[dict] = None

    updated_at: int
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class ToolUserModel(ToolModel):
    """ToolModel extended with owner information."""

    user: Optional[UserResponse] = None


class ToolResponse(BaseModel):
    """Tool data returned to API consumers (source content excluded)."""

    id: str
    user_id: str
    name: str
    meta: ToolMeta
    access_control: Optional[dict] = None
    updated_at: int
    created_at: int


class ToolUserResponse(ToolResponse):
    """ToolResponse extended with owner information."""

    user: Optional[UserResponse] = None


class ToolForm(BaseModel):
    """Payload accepted when creating a tool."""

    id: str
    name: str
    content: str
    meta: ToolMeta
    access_control: Optional[dict] = None


class ToolValves(BaseModel):
    """Wrapper for tool-level valve overrides."""

    valves: Optional[dict] = None


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------

class ToolsTable:
    """CRUD operations for :class:`Tool` records."""

    # -- create -------------------------------------------------------------

    def insert_new_tool(
        self, user_id: str, form_data: ToolForm, specs: list[dict]
    ) -> Optional[ToolModel]:
        """Persist a new tool with parsed *specs* owned by *user_id*."""
        with get_db() as db:
            now = _now()
            tool = ToolModel(
                **form_data.model_dump(),
                specs=specs,
                user_id=user_id,
                updated_at=now,
                created_at=now,
            )
            try:
                result = Tool(**tool.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return _validate_tool(result)
            except Exception:
                log.exception("Failed to create tool")
                return None

    # -- read ---------------------------------------------------------------

    def get_tool_by_id(self, id: str) -> Optional[ToolModel]:
        """Look up a single tool by primary key."""
        try:
            with get_db() as db:
                row = db.get(Tool, id)
                return ToolModel.model_validate(row)
        except Exception:
            return None

    def get_tools(self) -> list[ToolUserModel]:
        """Return all tools enriched with owner info, newest first."""
        with get_db() as db:
            results: list[ToolUserModel] = []
            for row in db.query(Tool).order_by(Tool.updated_at.desc()).all():
                results.append(_enrich_with_user(ToolModel.model_validate(row)))
            return results

    def get_tools_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[ToolUserModel]:
        """Return tools accessible to *user_id* at *permission* level."""
        return [
            t
            for t in self.get_tools()
            if t.user_id == user_id
            or has_access(user_id, permission, t.access_control)
        ]

    # -- valves (tool-level) ------------------------------------------------

    def get_tool_valves_by_id(self, id: str) -> Optional[dict]:
        """Return the tool-level valves dict, or empty dict if unset."""
        try:
            with get_db() as db:
                row = db.get(Tool, id)
                return row.valves if row.valves else {}
        except Exception:
            log.exception("Failed to get tool valves for %s", id)
            return None

    def update_tool_valves_by_id(self, id: str, valves: dict) -> Optional[ToolValves]:
        """Replace the tool-level valves and return the updated tool."""
        try:
            with get_db() as db:
                db.query(Tool).filter_by(id=id).update(
                    {"valves": valves, "updated_at": _now()}
                )
                db.commit()
                return self.get_tool_by_id(id)
        except Exception:
            return None

    # -- valves (per-user) --------------------------------------------------

    def get_user_valves_by_id_and_user_id(
        self, id: str, user_id: str
    ) -> Optional[dict]:
        """Return per-user valve overrides for tool *id*."""
        try:
            _settings, tool_valves = _get_user_tools_settings(user_id)
            return tool_valves.get(id, {})
        except Exception:
            log.exception(
                "Failed to get user valves for tool %s / user %s", id, user_id
            )
            return None

    def update_user_valves_by_id_and_user_id(
        self, id: str, user_id: str, valves: dict
    ) -> Optional[dict]:
        """Set per-user valve overrides for tool *id* and return them."""
        try:
            settings, tool_valves = _get_user_tools_settings(user_id)
            tool_valves[id] = valves
            Users.update_user_by_id(user_id, {"settings": settings})
            return tool_valves[id]
        except Exception:
            log.exception(
                "Failed to update user valves for tool %s / user %s", id, user_id
            )
            return None

    # -- update -------------------------------------------------------------

    def update_tool_by_id(self, id: str, updated: dict) -> Optional[ToolModel]:
        """Patch arbitrary columns on a tool and return the updated model."""
        try:
            with get_db() as db:
                db.query(Tool).filter_by(id=id).update(
                    {**updated, "updated_at": _now()}
                )
                db.commit()
                row = db.query(Tool).get(id)
                db.refresh(row)
                return ToolModel.model_validate(row)
        except Exception:
            return None

    # -- delete -------------------------------------------------------------

    def delete_tool_by_id(self, id: str) -> bool:
        """Remove a single tool by primary key."""
        try:
            with get_db() as db:
                db.query(Tool).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False


Tools = ToolsTable()
