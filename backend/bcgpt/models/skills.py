"""Skill model and table operations.

Manages SKILL.md skill definitions stored in the database: frontmatter,
body (prompt instructions), bundled reference resources, and activation
state. Skills are prompt + reference content only — no executable scripts.
Skills can be global (admin catalog), per-user, or built-in.
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, String, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, JSONField, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class Skill(Base):
    """Persistent representation of a skill row."""

    __tablename__ = "skill"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    name = Column(Text)
    description = Column(Text)
    content = Column(Text)  # SKILL.md body (instructions / workflow)
    meta = Column(JSONField)  # {description, resources:{path:text}, tools, ...}
    is_active = Column(Boolean)
    is_global = Column(Boolean)
    is_builtin = Column(Boolean)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


class SkillMeta(BaseModel):
    """Metadata describing a skill."""

    description: Optional[str] = None
    resources: dict = {}  # {relative_path: text_content} — bundled reference files
    tools: list = []
    required_capabilities: list = []
    tags: list = []
    version: Optional[str] = None
    source_url: Optional[str] = None


class SkillModel(BaseModel):
    """Full skill representation returned to callers."""

    id: str
    user_id: str
    name: str
    description: str = ""
    content: str = ""
    meta: SkillMeta
    is_active: bool = False
    is_global: bool = False
    is_builtin: bool = False
    updated_at: int
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class SkillForm(BaseModel):
    """Schema for creating or updating a skill."""

    id: str
    name: str
    description: str = ""
    content: str = ""
    meta: SkillMeta = SkillMeta()


class SkillsTable:
    """Collection of database helpers for the ``skill`` table."""

    def insert_new_skill(
        self, user_id: str, form_data: SkillForm
    ) -> Optional[SkillModel]:
        skill = SkillModel(
            **{
                **form_data.model_dump(),
                "user_id": user_id,
                "is_active": False,
                "is_global": False,
                "is_builtin": False,
                "updated_at": int(time.time()),
                "created_at": int(time.time()),
            }
        )
        try:
            with get_db() as db:
                result = Skill(**skill.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return SkillModel.model_validate(result) if result else None
        except Exception as e:
            log.exception("Error creating a new skill: %s", e)
            return None

    def get_skill_by_id(self, id: str) -> Optional[SkillModel]:
        try:
            with get_db() as db:
                skill = db.get(Skill, id)
                return SkillModel.model_validate(skill) if skill else None
        except Exception:
            return None

    def get_skills(self, active_only: bool = False) -> list[SkillModel]:
        with get_db() as db:
            q = db.query(Skill)
            if active_only:
                q = q.filter_by(is_active=True)
            return [SkillModel.model_validate(s) for s in q.all()]

    def get_active_global_skills(self) -> list[SkillModel]:
        with get_db() as db:
            rows = db.query(Skill).filter_by(is_active=True, is_global=True).all()
            return [SkillModel.model_validate(s) for s in rows]

    def get_skills_for_user(self, user_id: str) -> list[SkillModel]:
        """Return a user's own (non-global) skills."""
        with get_db() as db:
            rows = (
                db.query(Skill)
                .filter(Skill.user_id == user_id, Skill.is_global.is_(False))
                .all()
            )
            return [SkillModel.model_validate(s) for s in rows]

    def update_skill_by_id(self, id: str, updated: dict) -> Optional[SkillModel]:
        with get_db() as db:
            try:
                db.query(Skill).filter_by(id=id).update(
                    {**updated, "updated_at": int(time.time())}
                )
                db.commit()
                return self.get_skill_by_id(id)
            except Exception as e:
                log.exception("Error updating skill %s: %s", id, e)
                return None

    def delete_skill_by_id(self, id: str) -> bool:
        with get_db() as db:
            try:
                db.query(Skill).filter_by(id=id).delete()
                db.commit()
                return True
            except Exception:
                return False


Skills = SkillsTable()
