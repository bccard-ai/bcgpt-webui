"""Feedback model and table operations.

Stores user feedback (ratings, comments, snapshots) tied to chat
messages.  Each feedback entry is versioned and can be queried by
type or user.
"""

import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Feedback(Base):
    """Persistent representation of a feedback row."""

    __tablename__ = "feedback"

    id = Column(Text, primary_key=True)
    user_id = Column(Text)
    version = Column(BigInteger, default=0)
    type = Column(Text)
    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    snapshot = Column(JSON, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FeedbackModel(BaseModel):
    """Full feedback representation returned to callers."""

    id: str
    user_id: str
    version: int
    type: str
    data: Optional[dict] = None
    meta: Optional[dict] = None
    snapshot: Optional[dict] = None
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class FeedbackResponse(BaseModel):
    """Feedback payload returned in API responses (excludes snapshot)."""

    id: str
    user_id: str
    version: int
    type: str
    data: Optional[dict] = None
    meta: Optional[dict] = None
    created_at: int
    updated_at: int


class RatingData(BaseModel):
    """Structured rating information attached to feedback."""

    rating: Optional[str | int] = None
    model_id: Optional[str] = None
    sibling_model_ids: Optional[list[str]] = None
    reason: Optional[str] = None
    comment: Optional[str] = None
    model_config = ConfigDict(extra="allow", protected_namespaces=())


class MetaData(BaseModel):
    """Metadata associated with a feedback entry."""

    arena: Optional[bool] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    tags: Optional[list[str]] = None
    model_config = ConfigDict(extra="allow")


class SnapshotData(BaseModel):
    """Snapshot of the chat state at feedback time."""

    chat: Optional[dict] = None
    model_config = ConfigDict(extra="allow")


class FeedbackForm(BaseModel):
    """Schema for creating or updating feedback."""

    type: str
    data: Optional[RatingData] = None
    meta: Optional[dict] = None
    snapshot: Optional[SnapshotData] = None
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------


class FeedbackTable:
    """Collection of database helpers for the ``feedback`` table."""

    def insert_new_feedback(
        self,
        user_id: str,
        form_data: FeedbackForm,
    ) -> Optional[FeedbackModel]:
        """Create a new feedback entry and return its model."""
        with get_db() as db:
            id = str(uuid.uuid4())
            feedback = FeedbackModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "version": 0,
                    **form_data.model_dump(),
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )
            try:
                result = Feedback(**feedback.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return FeedbackModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception("Error creating a new feedback: %s", e)
                return None

    def get_feedback_by_id(self, id: str) -> Optional[FeedbackModel]:
        """Fetch a single feedback entry by its primary key."""
        try:
            with get_db() as db:
                feedback = db.query(Feedback).filter_by(id=id).first()
                if not feedback:
                    return None
                return FeedbackModel.model_validate(feedback)
        except Exception:
            return None

    def get_feedback_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
    ) -> Optional[FeedbackModel]:
        """Fetch a feedback entry belonging to a specific user."""
        try:
            with get_db() as db:
                feedback = db.query(Feedback).filter_by(id=id, user_id=user_id).first()
                if not feedback:
                    return None
                return FeedbackModel.model_validate(feedback)
        except Exception:
            return None

    def get_all_feedbacks(self) -> list[FeedbackModel]:
        """Return every feedback entry ordered by most recently updated."""
        with get_db() as db:
            return [
                FeedbackModel.model_validate(feedback)
                for feedback in db.query(Feedback)
                .order_by(Feedback.updated_at.desc())
                .all()
            ]

    def get_feedbacks_by_type(self, type: str) -> list[FeedbackModel]:
        """Return feedback entries of a given type, most recently updated first."""
        with get_db() as db:
            return [
                FeedbackModel.model_validate(feedback)
                for feedback in db.query(Feedback)
                .filter_by(type=type)
                .order_by(Feedback.updated_at.desc())
                .all()
            ]

    def get_feedbacks_by_user_id(self, user_id: str) -> list[FeedbackModel]:
        """Return all feedback entries submitted by a user, most recently updated first."""
        with get_db() as db:
            return [
                FeedbackModel.model_validate(feedback)
                for feedback in db.query(Feedback)
                .filter_by(user_id=user_id)
                .order_by(Feedback.updated_at.desc())
                .all()
            ]

    def update_feedback_by_id(
        self,
        id: str,
        form_data: FeedbackForm,
    ) -> Optional[FeedbackModel]:
        """Patch an existing feedback entry with new form data."""
        with get_db() as db:
            feedback = db.query(Feedback).filter_by(id=id).first()
            if not feedback:
                return None

            if form_data.data:
                feedback.data = form_data.data.model_dump()
            if form_data.meta:
                feedback.meta = form_data.meta
            if form_data.snapshot:
                feedback.snapshot = form_data.snapshot.model_dump()

            feedback.updated_at = int(time.time())

            db.commit()
            return FeedbackModel.model_validate(feedback)

    def update_feedback_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
        form_data: FeedbackForm,
    ) -> Optional[FeedbackModel]:
        """Patch a feedback entry owned by a specific user."""
        with get_db() as db:
            feedback = db.query(Feedback).filter_by(id=id, user_id=user_id).first()
            if not feedback:
                return None

            if form_data.data:
                feedback.data = form_data.data.model_dump()
            if form_data.meta:
                feedback.meta = form_data.meta
            if form_data.snapshot:
                feedback.snapshot = form_data.snapshot.model_dump()

            feedback.updated_at = int(time.time())

            db.commit()
            return FeedbackModel.model_validate(feedback)

    def delete_feedback_by_id(self, id: str) -> bool:
        """Delete a single feedback entry. Returns ``True`` if deleted."""
        with get_db() as db:
            feedback = db.query(Feedback).filter_by(id=id).first()
            if not feedback:
                return False
            db.delete(feedback)
            db.commit()
            return True

    def delete_feedback_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        """Delete a feedback entry owned by a specific user."""
        with get_db() as db:
            feedback = db.query(Feedback).filter_by(id=id, user_id=user_id).first()
            if not feedback:
                return False
            db.delete(feedback)
            db.commit()
            return True

    def delete_feedbacks_by_user_id(self, user_id: str) -> bool:
        """Delete all feedback entries belonging to a user."""
        with get_db() as db:
            feedbacks = db.query(Feedback).filter_by(user_id=user_id).all()
            if not feedbacks:
                return False
            for feedback in feedbacks:
                db.delete(feedback)
            db.commit()
            return True

    def delete_all_feedbacks(self) -> bool:
        """Delete every feedback entry in the database."""
        with get_db() as db:
            feedbacks = db.query(Feedback).all()
            if not feedbacks:
                return False
            for feedback in feedbacks:
                db.delete(feedback)
            db.commit()
            return True

    def rating_distribution(self, start_ts_s: int, end_ts_s: int) -> dict:
        """Aggregate feedback.data.rating (str|int) into a 1-5 distribution.

        ``created_at`` is epoch seconds. data.rating may be missing/non-numeric;
        those rows are ignored for the average but counted under 'other'.
        """
        with get_db() as db:
            rows = (
                db.query(Feedback.data, Feedback.created_at)
                .filter(
                    Feedback.created_at >= start_ts_s,
                    Feedback.created_at <= end_ts_s,
                )
                .all()
            )
        dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        total = 0
        total_rating = 0.0
        for data, _ts in rows:
            rating = None
            try:
                rating = (data or {}).get("rating")
            except Exception:
                rating = None
            try:
                r = int(rating)
            except (TypeError, ValueError):
                continue
            if 1 <= r <= 5:
                dist[str(r)] = dist.get(str(r), 0) + 1
                total += 1
                total_rating += r
        avg = round(total_rating / total, 2) if total else 0.0
        return {**dist, "count": total, "avg": avg}


Feedbacks = FeedbackTable()
