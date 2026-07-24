"""Channel model and table operations.

Provides the SQLAlchemy ORM model, Pydantic schemas, and a table-level
CRUD wrapper for channel entities.  Channels are top-level containers
that can be access-controlled per-user or per-group.
"""

import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, String, Text

from bcgpt.internal import Base, get_db
from bcgpt.utils import has_access


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class Channel(Base):
    """Persistent representation of a channel row."""

    __tablename__ = "channel"

    id = Column(Text, primary_key=True)
    user_id = Column(Text)
    type = Column(Text, nullable=True)

    name = Column(Text)
    description = Column(Text, nullable=True)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    access_control = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChannelModel(BaseModel):
    """Full channel representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    type: Optional[str] = None

    name: str
    description: Optional[str] = None

    data: Optional[dict] = None
    meta: Optional[dict] = None
    access_control: Optional[dict] = None

    created_at: int  # epoch nanoseconds
    updated_at: int  # epoch nanoseconds


class ChannelForm(BaseModel):
    """Schema for creating or updating a channel."""

    name: str
    description: Optional[str] = None
    data: Optional[dict] = None
    meta: Optional[dict] = None
    access_control: Optional[dict] = None


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class ChannelTable:
    """Collection of database helpers for the ``channel`` table."""

    def insert_new_channel(
        self,
        type: Optional[str],
        form_data: ChannelForm,
        user_id: str,
    ) -> Optional[ChannelModel]:
        """Create a new channel and return its model, or ``None`` on failure."""
        with get_db() as db:
            channel = ChannelModel(
                **{
                    **form_data.model_dump(),
                    "type": type,
                    "name": form_data.name.lower(),
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "created_at": int(time.time_ns()),
                    "updated_at": int(time.time_ns()),
                }
            )

            new_channel = Channel(**channel.model_dump())

            db.add(new_channel)
            db.commit()
            return channel

    def get_channels(self) -> list[ChannelModel]:
        """Return every channel in the database."""
        with get_db() as db:
            channels = db.query(Channel).all()
            return [ChannelModel.model_validate(channel) for channel in channels]

    def get_channels_by_user_id(
        self,
        user_id: str,
        permission: str = "read",
    ) -> list[ChannelModel]:
        """Return channels the given user is allowed to access."""
        channels = self.get_channels()
        return [
            channel
            for channel in channels
            if channel.user_id == user_id
            or has_access(user_id, permission, channel.access_control)
        ]

    def get_channel_by_id(self, id: str) -> Optional[ChannelModel]:
        """Fetch a single channel by its primary key."""
        with get_db() as db:
            channel = db.query(Channel).filter(Channel.id == id).first()
            return ChannelModel.model_validate(channel) if channel else None

    def update_channel_by_id(
        self,
        id: str,
        form_data: ChannelForm,
    ) -> Optional[ChannelModel]:
        """Patch an existing channel with new form data."""
        with get_db() as db:
            channel = db.query(Channel).filter(Channel.id == id).first()
            if not channel:
                return None

            channel.name = form_data.name
            channel.data = form_data.data
            channel.meta = form_data.meta
            channel.access_control = form_data.access_control
            channel.updated_at = int(time.time_ns())

            db.commit()
            return ChannelModel.model_validate(channel) if channel else None

    def delete_channel_by_id(self, id: str) -> bool:
        """Delete a channel by its primary key. Always returns ``True``."""
        with get_db() as db:
            db.query(Channel).filter(Channel.id == id).delete()
            db.commit()
            return True


Channels = ChannelTable()
