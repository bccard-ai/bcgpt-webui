"""Message and message-reaction models and table operations.

Manages channel messages, threaded replies, and emoji-style reactions.
Messages belong to a channel and can be nested via ``parent_id``.
"""

import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, String, Text
from sqlalchemy import or_, func, select, and_, text
from sqlalchemy.sql import exists

from bcgpt.internal import Base, get_db
from bcgpt.models import Tag, TagModel, Tags


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------

class MessageReaction(Base):
    """Persistent representation of a message reaction row."""

    __tablename__ = "message_reaction"

    id = Column(Text, primary_key=True)
    user_id = Column(Text)
    message_id = Column(Text)
    name = Column(Text)
    created_at = Column(BigInteger)


class Message(Base):
    """Persistent representation of a message row."""

    __tablename__ = "message"

    id = Column(Text, primary_key=True)

    user_id = Column(Text)
    channel_id = Column(Text, nullable=True)

    parent_id = Column(Text, nullable=True)

    content = Column(Text)
    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    created_at = Column(BigInteger)  # epoch nanoseconds
    updated_at = Column(BigInteger)  # epoch nanoseconds


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MessageReactionModel(BaseModel):
    """Full message-reaction representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    message_id: str
    name: str
    created_at: int  # epoch nanoseconds


class MessageModel(BaseModel):
    """Full message representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    channel_id: Optional[str] = None

    parent_id: Optional[str] = None

    content: str
    data: Optional[dict] = None
    meta: Optional[dict] = None

    created_at: int  # epoch nanoseconds
    updated_at: int  # epoch nanoseconds


class MessageForm(BaseModel):
    """Schema for creating or updating a message."""

    content: str
    parent_id: Optional[str] = None
    data: Optional[dict] = None
    meta: Optional[dict] = None


class Reactions(BaseModel):
    """Aggregated reaction summary for a single reaction name."""

    name: str
    user_ids: list[str]
    count: int


class MessageResponse(MessageModel):
    """Extended message representation including reply metadata and reactions."""

    latest_reply_at: Optional[int]
    reply_count: int
    reactions: list[Reactions]


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class MessageTable:
    """Collection of database helpers for the ``message`` table."""

    def insert_new_message(
        self,
        form_data: MessageForm,
        channel_id: str,
        user_id: str,
    ) -> Optional[MessageModel]:
        """Create a new message and return its model."""
        with get_db() as db:
            id = str(uuid.uuid4())

            ts = int(time.time_ns())
            message = MessageModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "parent_id": form_data.parent_id,
                    "content": form_data.content,
                    "data": form_data.data,
                    "meta": form_data.meta,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )

            result = Message(**message.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return MessageModel.model_validate(result) if result else None

    def get_message_by_id(self, id: str) -> Optional[MessageResponse]:
        """Fetch a message together with its reactions and reply metadata."""
        with get_db() as db:
            message = db.get(Message, id)
            if not message:
                return None

            reactions = self.get_reactions_by_message_id(id)
            replies = self.get_replies_by_message_id(id)

            return MessageResponse(
                **{
                    **MessageModel.model_validate(message).model_dump(),
                    "latest_reply_at": replies[0].created_at if replies else None,
                    "reply_count": len(replies),
                    "reactions": reactions,
                }
            )

    def get_replies_by_message_id(
        self, id: str
    ) -> list[MessageModel]:
        """Return all replies to a given parent message, newest first."""
        with get_db() as db:
            all_messages = (
                db.query(Message)
                .filter_by(parent_id=id)
                .order_by(Message.created_at.desc())
                .all()
            )
            return [
                MessageModel.model_validate(message)
                for message in all_messages
            ]

    def get_reply_user_ids_by_message_id(
        self, id: str
    ) -> list[str]:
        """Return the user IDs of all users who replied to a message."""
        with get_db() as db:
            return [
                message.user_id
                for message in db.query(Message).filter_by(parent_id=id).all()
            ]

    def get_messages_by_channel_id(
        self,
        channel_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageModel]:
        """Return top-level messages in a channel, paginated and newest first."""
        with get_db() as db:
            all_messages = (
                db.query(Message)
                .filter_by(channel_id=channel_id, parent_id=None)
                .order_by(Message.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            return [
                MessageModel.model_validate(message)
                for message in all_messages
            ]

    def get_messages_by_parent_id(
        self,
        channel_id: str,
        parent_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageModel]:
        """Return threaded replies under a parent message.

        If fewer than *limit* replies exist the parent message itself is
        appended to the result list.
        """
        with get_db() as db:
            message = db.get(Message, parent_id)

            if not message:
                return []

            all_messages = (
                db.query(Message)
                .filter_by(channel_id=channel_id, parent_id=parent_id)
                .order_by(Message.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )

            if len(all_messages) < limit:
                all_messages.append(message)

            return [
                MessageModel.model_validate(message)
                for message in all_messages
            ]

    def update_message_by_id(
        self,
        id: str,
        form_data: MessageForm,
    ) -> Optional[MessageModel]:
        """Patch an existing message with new form data."""
        with get_db() as db:
            message = db.get(Message, id)
            message.content = form_data.content
            message.data = form_data.data
            message.meta = form_data.meta
            message.updated_at = int(time.time_ns())
            db.commit()
            db.refresh(message)
            return MessageModel.model_validate(message) if message else None

    def add_reaction_to_message(
        self,
        id: str,
        user_id: str,
        name: str,
    ) -> Optional[MessageReactionModel]:
        """Attach a named reaction to a message for a given user."""
        with get_db() as db:
            reaction_id = str(uuid.uuid4())
            reaction = MessageReactionModel(
                id=reaction_id,
                user_id=user_id,
                message_id=id,
                name=name,
                created_at=int(time.time_ns()),
            )
            result = MessageReaction(**reaction.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return (
                MessageReactionModel.model_validate(result) if result else None
            )

    def get_reactions_by_message_id(self, id: str) -> list[Reactions]:
        """Aggregate all reactions for a message, grouped by name."""
        with get_db() as db:
            all_reactions = (
                db.query(MessageReaction).filter_by(message_id=id).all()
            )

            reactions: dict[str, dict] = {}
            for reaction in all_reactions:
                if reaction.name not in reactions:
                    reactions[reaction.name] = {
                        "name": reaction.name,
                        "user_ids": [],
                        "count": 0,
                    }
                reactions[reaction.name]["user_ids"].append(reaction.user_id)
                reactions[reaction.name]["count"] += 1

            return [Reactions(**reaction) for reaction in reactions.values()]

    def remove_reaction_by_id_and_user_id_and_name(
        self,
        id: str,
        user_id: str,
        name: str,
    ) -> bool:
        """Remove a specific reaction from a message for a given user."""
        with get_db() as db:
            db.query(MessageReaction).filter_by(
                message_id=id, user_id=user_id, name=name
            ).delete()
            db.commit()
            return True

    def delete_reactions_by_id(self, id: str) -> bool:
        """Delete all reactions attached to a message."""
        with get_db() as db:
            db.query(MessageReaction).filter_by(message_id=id).delete()
            db.commit()
            return True

    def delete_replies_by_id(self, id: str) -> bool:
        """Delete all replies under a parent message."""
        with get_db() as db:
            db.query(Message).filter_by(parent_id=id).delete()
            db.commit()
            return True

    def delete_message_by_id(self, id: str) -> bool:
        """Delete a message together with all its reactions."""
        with get_db() as db:
            db.query(Message).filter_by(id=id).delete()

            db.query(MessageReaction).filter_by(message_id=id).delete()

            db.commit()
            return True


Messages = MessageTable()
