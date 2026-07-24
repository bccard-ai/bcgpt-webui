"""Memory model and table operations.

Stores short textual memories associated with individual users.
Memories are typically used for per-user context personalisation.
"""

import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text

from bcgpt.internal import Base, get_db


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class Memory(Base):
    """Persistent representation of a memory row."""

    __tablename__ = "memory"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    content = Column(Text)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MemoryModel(BaseModel):
    """Full memory representation returned to callers."""

    id: str
    user_id: str
    content: str
    updated_at: int  # epoch seconds
    created_at: int  # epoch seconds

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class MemoriesTable:
    """Collection of database helpers for the ``memory`` table."""

    def insert_new_memory(
        self,
        user_id: str,
        content: str,
    ) -> Optional[MemoryModel]:
        """Create a new memory entry and return its model."""
        with get_db() as db:
            id = str(uuid.uuid4())

            memory = MemoryModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "content": content,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )
            result = Memory(**memory.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            if result:
                return MemoryModel.model_validate(result)
            else:
                return None

    def update_memory_by_id(
        self,
        id: str,
        content: str,
    ) -> Optional[MemoryModel]:
        """Update the content of an existing memory entry."""
        with get_db() as db:
            try:
                db.query(Memory).filter_by(id=id).update(
                    {"content": content, "updated_at": int(time.time())}
                )
                db.commit()
                return self.get_memory_by_id(id)
            except Exception:
                return None

    def get_memories(self) -> list[MemoryModel]:
        """Return every memory entry in the database."""
        with get_db() as db:
            try:
                memories = db.query(Memory).all()
                return [
                    MemoryModel.model_validate(memory) for memory in memories
                ]
            except Exception:
                return None

    def get_memories_by_user_id(
        self, user_id: str
    ) -> list[MemoryModel]:
        """Return all memory entries belonging to a specific user."""
        with get_db() as db:
            try:
                memories = db.query(Memory).filter_by(user_id=user_id).all()
                return [
                    MemoryModel.model_validate(memory) for memory in memories
                ]
            except Exception:
                return None

    def get_memory_by_id(self, id: str) -> Optional[MemoryModel]:
        """Fetch a single memory entry by its primary key."""
        with get_db() as db:
            try:
                memory = db.get(Memory, id)
                return MemoryModel.model_validate(memory)
            except Exception:
                return None

    def delete_memory_by_id(self, id: str) -> bool:
        """Delete a memory entry by its primary key."""
        with get_db() as db:
            try:
                db.query(Memory).filter_by(id=id).delete()
                db.commit()

                return True

            except Exception:
                return False

    def delete_memories_by_user_id(self, user_id: str) -> bool:
        """Delete all memory entries belonging to a user."""
        with get_db() as db:
            try:
                db.query(Memory).filter_by(user_id=user_id).delete()
                db.commit()

                return True
            except Exception:
                return False

    def delete_memory_by_id_and_user_id(
        self, id: str, user_id: str
    ) -> bool:
        """Delete a memory entry matching both ID and owner."""
        with get_db() as db:
            try:
                db.query(Memory).filter_by(id=id, user_id=user_id).delete()
                db.commit()

                return True
            except Exception:
                return False


Memories = MemoriesTable()
