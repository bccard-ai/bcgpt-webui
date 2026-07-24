"""Prompt model and table operations.

Manages saved prompt templates keyed by a unique command string.
Prompts support per-user and per-group access control and can be
listed with their associated user information.
"""

import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, String, Text

from bcgpt.internal import Base, get_db
from bcgpt.models import UserResponse, Users
from bcgpt.utils import has_access


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class Prompt(Base):
    """Persistent representation of a prompt row."""

    __tablename__ = "prompt"

    command = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(Text)
    content = Column(Text)
    timestamp = Column(BigInteger)

    access_control = Column(JSON, nullable=True)
    # Controls data access levels:
    # - ``None``:  Public — available to all users with the "user" role.
    # - ``{}``:    Private — restricted exclusively to the owner.
    # - Custom permissions with ``read`` / ``write`` group and user lists.


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PromptModel(BaseModel):
    """Full prompt representation returned to callers."""

    command: str
    user_id: str
    title: str
    content: str
    timestamp: int  # epoch seconds

    access_control: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


class PromptUserResponse(PromptModel):
    """Prompt enriched with the owning user's public profile."""

    user: Optional[UserResponse] = None


class PromptForm(BaseModel):
    """Schema for creating or updating a prompt."""

    command: str
    title: str
    content: str
    access_control: Optional[dict] = None


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class PromptsTable:
    """Collection of database helpers for the ``prompt`` table."""

    def insert_new_prompt(
        self,
        user_id: str,
        form_data: PromptForm,
    ) -> Optional[PromptModel]:
        """Create a new prompt entry and return its model."""
        prompt = PromptModel(
            **{
                "user_id": user_id,
                **form_data.model_dump(),
                "timestamp": int(time.time()),
            }
        )

        try:
            with get_db() as db:
                result = Prompt(**prompt.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return PromptModel.model_validate(result)
                else:
                    return None
        except Exception:
            return None

    def get_prompt_by_command(self, command: str) -> Optional[PromptModel]:
        """Fetch a single prompt by its command string."""
        try:
            with get_db() as db:
                prompt = (
                    db.query(Prompt).filter_by(command=command).first()
                )
                return PromptModel.model_validate(prompt)
        except Exception:
            return None

    def get_prompts(self) -> list[PromptUserResponse]:
        """Return all prompts enriched with owner profile, newest first."""
        with get_db() as db:
            prompts: list[PromptUserResponse] = []

            for prompt in (
                db.query(Prompt).order_by(Prompt.timestamp.desc()).all()
            ):
                user = Users.get_user_by_id(prompt.user_id)
                prompts.append(
                    PromptUserResponse.model_validate(
                        {
                            **PromptModel.model_validate(prompt).model_dump(),
                            "user": user.model_dump() if user else None,
                        }
                    )
                )

            return prompts

    def get_prompts_by_user_id(
        self,
        user_id: str,
        permission: str = "write",
    ) -> list[PromptUserResponse]:
        """Return prompts accessible to a user (owned or via access control)."""
        prompts = self.get_prompts()

        return [
            prompt
            for prompt in prompts
            if prompt.user_id == user_id
            or has_access(user_id, permission, prompt.access_control)
        ]

    def update_prompt_by_command(
        self,
        command: str,
        form_data: PromptForm,
    ) -> Optional[PromptModel]:
        """Patch an existing prompt identified by its command string."""
        try:
            with get_db() as db:
                prompt = (
                    db.query(Prompt).filter_by(command=command).first()
                )
                prompt.title = form_data.title
                prompt.content = form_data.content
                prompt.access_control = form_data.access_control
                prompt.timestamp = int(time.time())
                db.commit()
                return PromptModel.model_validate(prompt)
        except Exception:
            return None

    def delete_prompt_by_command(self, command: str) -> bool:
        """Delete a prompt by its command string."""
        try:
            with get_db() as db:
                db.query(Prompt).filter_by(command=command).delete()
                db.commit()

                return True
        except Exception:
            return False


Prompts = PromptsTable()
