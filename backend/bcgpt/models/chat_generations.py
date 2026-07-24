"""Durable chat turn/generation admission and terminal authority.

The process-local asyncio task registry is only a delivery mechanism.  This
table is the durable authority used to make a client-generated generation ID
idempotent across retries, process restarts, and multiple API replicas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.exc import IntegrityError

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

ACTIVE_GENERATION_STATUSES = ("admitted", "running", "stop_requested")
TERMINAL_GENERATION_STATUSES = ("completed", "stopped", "error", "timed_out")
GENERATION_STATUSES = ACTIVE_GENERATION_STATUSES + TERMINAL_GENERATION_STATUSES

REPLAY_RUNNING_TTL_MS = 15 * 60 * 1000
REPLAY_TERMINAL_TTL_MS = 2 * 60 * 1000
REPLAY_MAX_CONTENT_CHARS = 1_000_000
REPLAY_MAX_TOTAL_BYTES = 2 * 1024 * 1024
REPLAY_MAX_EVENT_BYTES = 256 * 1024
REPLAY_MAX_EVENTS = 20_000
REPLAY_TAIL_LIMIT = 256
REPLAY_TAIL_MAX_BYTES = 64 * 1024

GenerationStatus = Literal[
    "admitted",
    "running",
    "stop_requested",
    "completed",
    "stopped",
    "error",
    "timed_out",
]
AdmissionKind = Literal["accepted", "duplicate", "stopped", "terminal", "conflict"]
StopKind = Literal[
    "accepted", "already_terminal", "already_completed", "different_generation"
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def generation_request_fingerprint(
    *,
    generation_id: str,
    turn_id: str,
    client_message_id: str,
    assistant_message_id: str,
    user_id: str,
    chat_id: str,
    model_id: str,
) -> str:
    """Return a content-free digest for idempotency conflict detection."""

    canonical = json.dumps(
        {
            "generation_id": generation_id,
            "turn_id": turn_id,
            "client_message_id": client_message_id,
            "assistant_message_id": assistant_message_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "model_id": model_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ChatGeneration(Base):
    __tablename__ = "chat_generation"
    __table_args__ = (
        Index(
            "uq_chat_generation_active_assistant_authority",
            "user_id",
            "chat_id",
            "assistant_message_id",
            unique=True,
            sqlite_where=text("status IN ('admitted', 'running', 'stop_requested')"),
            postgresql_where=text(
                "status IN ('admitted', 'running', 'stop_requested')"
            ),
        ),
    )

    generation_id = Column(String, primary_key=True)
    turn_id = Column(String, nullable=True)
    client_message_id = Column(String, nullable=True)
    assistant_message_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=False, index=True)
    model_id = Column(String, nullable=True)
    request_fingerprint = Column(String(64), nullable=True)
    task_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    terminal_reason = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    admitted_at = Column(BigInteger, nullable=True)
    started_at = Column(BigInteger, nullable=True)
    terminal_at = Column(BigInteger, nullable=True)


class ChatGenerationReplay(Base):
    """Short-lived, assistant-visible reconnect projection."""

    __tablename__ = "chat_generation_replay"

    generation_id = Column(
        String,
        ForeignKey("chat_generation.generation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=False, index=True)
    assistant_message_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    content = Column(Text, nullable=False, default="")
    degraded = Column(Boolean, nullable=False, default=False)
    last_sequence = Column(Integer, nullable=False, default=0)
    event_count = Column(Integer, nullable=False, default=0)
    total_bytes = Column(BigInteger, nullable=False, default=0)
    expires_at = Column(BigInteger, nullable=False, index=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    terminal_at = Column(BigInteger, nullable=True)


class ChatGenerationReplayEvent(Base):
    __tablename__ = "chat_generation_replay_event"

    generation_id = Column(
        String,
        ForeignKey("chat_generation_replay.generation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    payload_digest = Column(String(64), nullable=False)
    payload_bytes = Column(Integer, nullable=False)
    expires_at = Column(BigInteger, nullable=False, index=True)
    created_at = Column(BigInteger, nullable=False)


class ChatGenerationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: str
    turn_id: Optional[str] = None
    client_message_id: Optional[str] = None
    assistant_message_id: str
    user_id: str
    chat_id: str
    model_id: Optional[str] = None
    request_fingerprint: Optional[str] = None
    task_id: Optional[str] = None
    status: GenerationStatus
    terminal_reason: Optional[str] = None
    version: int = 0
    created_at: int
    updated_at: int
    admitted_at: Optional[int] = None
    started_at: Optional[int] = None
    terminal_at: Optional[int] = None


class ChatGenerationReplayModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: str
    user_id: str
    chat_id: str
    assistant_message_id: str
    status: str
    content: str
    degraded: bool
    last_sequence: int
    event_count: int
    total_bytes: int
    expires_at: int
    created_at: int
    updated_at: int
    terminal_at: Optional[int] = None


@dataclass(frozen=True)
class GenerationAdmissionResult:
    kind: AdmissionKind
    generation: ChatGenerationModel


@dataclass(frozen=True)
class GenerationStopResult:
    kind: StopKind
    generation: ChatGenerationModel


class ChatGenerationTable:
    @staticmethod
    def _model(row: ChatGeneration) -> ChatGenerationModel:
        return ChatGenerationModel.model_validate(row)

    @staticmethod
    def _replay_model(row: ChatGenerationReplay) -> ChatGenerationReplayModel:
        return ChatGenerationReplayModel.model_validate(row)

    @staticmethod
    def _prune_expired_replays(db, now: int, limit: int = 100) -> None:
        expired_ids = [
            item[0]
            for item in (
                db.query(ChatGenerationReplay.generation_id)
                .filter(ChatGenerationReplay.expires_at <= now)
                .limit(limit)
                .all()
            )
        ]
        if not expired_ids:
            return
        db.query(ChatGenerationReplayEvent).filter(
            ChatGenerationReplayEvent.generation_id.in_(expired_ids)
        ).delete(synchronize_session=False)
        db.query(ChatGenerationReplay).filter(
            ChatGenerationReplay.generation_id.in_(expired_ids)
        ).delete(synchronize_session=False)

    @staticmethod
    def _begin_replay(db, generation: ChatGeneration, now: int) -> None:
        replay = db.get(ChatGenerationReplay, generation.generation_id)
        if replay is not None:
            return
        db.add(
            ChatGenerationReplay(
                generation_id=generation.generation_id,
                user_id=generation.user_id,
                chat_id=generation.chat_id,
                assistant_message_id=generation.assistant_message_id,
                status="running",
                content="",
                degraded=False,
                last_sequence=0,
                event_count=0,
                total_bytes=0,
                expires_at=now + REPLAY_RUNNING_TTL_MS,
                created_at=now,
                updated_at=now,
            )
        )

    @staticmethod
    def _event_payload_bytes(payload: dict) -> tuple[str, int, str]:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        encoded = serialized.encode("utf-8")
        return serialized, len(encoded), hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _base_authority_matches(
        row: ChatGeneration,
        *,
        user_id: str,
        chat_id: str,
        assistant_message_id: str,
    ) -> bool:
        return (
            row.user_id == user_id
            and row.chat_id == chat_id
            and row.assistant_message_id == assistant_message_id
        )

    @staticmethod
    def _admission_kind(row: ChatGeneration, fingerprint: str) -> AdmissionKind:
        if row.request_fingerprint not in (None, fingerprint):
            return "conflict"
        if row.status in ("stopped", "stop_requested"):
            return "stopped"
        if row.status in TERMINAL_GENERATION_STATUSES:
            return "terminal"
        return "duplicate"

    def get_owned(
        self, generation_id: str, user_id: str
    ) -> Optional[ChatGenerationModel]:
        with get_db() as db:
            row = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .first()
            )
            return self._model(row) if row else None

    def list_active_by_chat(
        self, user_id: str, chat_id: str
    ) -> list[ChatGenerationModel]:
        with get_db() as db:
            rows = (
                db.query(ChatGeneration)
                .filter_by(user_id=user_id, chat_id=chat_id)
                .filter(ChatGeneration.status.in_(ACTIVE_GENERATION_STATUSES))
                .order_by(ChatGeneration.created_at.asc())
                .all()
            )
            return [self._model(row) for row in rows]

    def admit(
        self,
        *,
        generation_id: str,
        turn_id: str,
        client_message_id: str,
        assistant_message_id: str,
        user_id: str,
        chat_id: str,
        model_id: str,
    ) -> GenerationAdmissionResult:
        fingerprint = generation_request_fingerprint(
            generation_id=generation_id,
            turn_id=turn_id,
            client_message_id=client_message_id,
            assistant_message_id=assistant_message_id,
            user_id=user_id,
            chat_id=chat_id,
            model_id=model_id,
        )

        with get_db() as db:
            now = _now_ms()
            self._prune_expired_replays(db, now)
            row = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id)
                .with_for_update()
                .first()
            )
            if row:
                if not self._base_authority_matches(
                    row,
                    user_id=user_id,
                    chat_id=chat_id,
                    assistant_message_id=assistant_message_id,
                ):
                    return GenerationAdmissionResult("conflict", self._model(row))

                kind = self._admission_kind(row, fingerprint)
                if row.request_fingerprint is None:
                    # Fill a valid pre-admission Stop tombstone without ever
                    # changing its stopped authority.
                    row.turn_id = turn_id
                    row.client_message_id = client_message_id
                    row.model_id = model_id
                    row.request_fingerprint = fingerprint
                    row.updated_at = _now_ms()
                    row.version += 1
                    db.commit()
                    db.refresh(row)
                    kind = self._admission_kind(row, fingerprint)
                return GenerationAdmissionResult(kind, self._model(row))

            existing_assistant = (
                db.query(ChatGeneration)
                .filter_by(
                    user_id=user_id,
                    chat_id=chat_id,
                    assistant_message_id=assistant_message_id,
                )
                .filter(ChatGeneration.status.in_(ACTIVE_GENERATION_STATUSES))
                .first()
            )
            if existing_assistant:
                return GenerationAdmissionResult(
                    "conflict", self._model(existing_assistant)
                )

            row = ChatGeneration(
                generation_id=generation_id,
                turn_id=turn_id,
                client_message_id=client_message_id,
                assistant_message_id=assistant_message_id,
                user_id=user_id,
                chat_id=chat_id,
                model_id=model_id,
                request_fingerprint=fingerprint,
                status="admitted",
                version=0,
                created_at=now,
                updated_at=now,
                admitted_at=now,
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raced = db.get(ChatGeneration, generation_id)
                if raced and self._base_authority_matches(
                    raced,
                    user_id=user_id,
                    chat_id=chat_id,
                    assistant_message_id=assistant_message_id,
                ):
                    return GenerationAdmissionResult(
                        self._admission_kind(raced, fingerprint), self._model(raced)
                    )
                if raced:
                    return GenerationAdmissionResult("conflict", self._model(raced))
                raced = (
                    db.query(ChatGeneration)
                    .filter_by(
                        user_id=user_id,
                        chat_id=chat_id,
                        assistant_message_id=assistant_message_id,
                    )
                    .filter(ChatGeneration.status.in_(ACTIVE_GENERATION_STATUSES))
                    .first()
                )
                if raced:
                    return GenerationAdmissionResult("conflict", self._model(raced))
                raise

            db.refresh(row)
            return GenerationAdmissionResult("accepted", self._model(row))

    def bind_task(
        self, generation_id: str, user_id: str, task_id: str
    ) -> Optional[ChatGenerationModel]:
        with get_db() as db:
            row = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .with_for_update()
                .first()
            )
            if not row:
                return None
            if row.status in ("stop_requested", "stopped"):
                return self._model(row)
            if row.status in TERMINAL_GENERATION_STATUSES:
                return self._model(row)
            if row.task_id not in (None, task_id):
                return self._model(row)

            now = _now_ms()
            row.task_id = task_id
            row.status = "running"
            row.started_at = row.started_at or now
            row.updated_at = now
            row.version += 1
            self._begin_replay(db, row, now)
            db.commit()
            db.refresh(row)
            return self._model(row)

    def request_stop(
        self,
        *,
        generation_id: str,
        user_id: str,
        chat_id: str,
        assistant_message_id: str,
    ) -> GenerationStopResult:
        with get_db() as db:
            row = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id)
                .with_for_update()
                .first()
            )
            if row:
                if not self._base_authority_matches(
                    row,
                    user_id=user_id,
                    chat_id=chat_id,
                    assistant_message_id=assistant_message_id,
                ):
                    return GenerationStopResult(
                        "different_generation", self._model(row)
                    )
                if row.status == "stopped":
                    return GenerationStopResult("already_terminal", self._model(row))
                if row.status in ("completed", "error", "timed_out"):
                    return GenerationStopResult("already_completed", self._model(row))

                now = _now_ms()
                row.status = "stop_requested"
                row.terminal_reason = "user_requested"
                row.updated_at = now
                row.version += 1
                db.commit()
                db.refresh(row)
                return GenerationStopResult("accepted", self._model(row))

            now = _now_ms()
            row = ChatGeneration(
                generation_id=generation_id,
                assistant_message_id=assistant_message_id,
                user_id=user_id,
                chat_id=chat_id,
                status="stopped",
                terminal_reason="user_requested_before_admission",
                version=0,
                created_at=now,
                updated_at=now,
                terminal_at=now,
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raced = db.get(ChatGeneration, generation_id)
                if raced and self._base_authority_matches(
                    raced,
                    user_id=user_id,
                    chat_id=chat_id,
                    assistant_message_id=assistant_message_id,
                ):
                    if raced.status == "stopped":
                        return GenerationStopResult(
                            "already_terminal", self._model(raced)
                        )
                    if raced.status in ("completed", "error", "timed_out"):
                        return GenerationStopResult(
                            "already_completed", self._model(raced)
                        )
                    raced.status = "stop_requested"
                    raced.terminal_reason = "user_requested"
                    raced.updated_at = _now_ms()
                    raced.version += 1
                    db.commit()
                    db.refresh(raced)
                    return GenerationStopResult("accepted", self._model(raced))
                if raced:
                    return GenerationStopResult(
                        "different_generation", self._model(raced)
                    )
                raise

            db.refresh(row)
            return GenerationStopResult("already_terminal", self._model(row))

    def terminalize(
        self,
        generation_id: str,
        user_id: str,
        status: Literal["completed", "stopped", "error", "timed_out"],
        reason: str,
    ) -> Optional[ChatGenerationModel]:
        with get_db() as db:
            row = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .with_for_update()
                .first()
            )
            if not row:
                return None
            if row.status in TERMINAL_GENERATION_STATUSES:
                return self._model(row)

            if row.status == "stop_requested":
                status = "stopped"
                reason = row.terminal_reason or "user_requested"

            now = _now_ms()
            row.status = status
            row.terminal_reason = reason
            row.terminal_at = now
            row.updated_at = now
            row.version += 1

            replay = (
                db.query(ChatGenerationReplay)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .with_for_update()
                .first()
            )
            if replay is not None:
                terminal_expiry = now + REPLAY_TERMINAL_TTL_MS
                if replay.status == "running" and not replay.degraded:
                    payload, payload_bytes, digest = self._event_payload_bytes(
                        {"type": "terminal", "status": status}
                    )
                    sequence = replay.last_sequence + 1
                    db.add(
                        ChatGenerationReplayEvent(
                            generation_id=generation_id,
                            sequence=sequence,
                            event_type="terminal",
                            payload=payload,
                            payload_digest=digest,
                            payload_bytes=payload_bytes,
                            expires_at=terminal_expiry,
                            created_at=now,
                        )
                    )
                    replay.last_sequence = sequence
                    replay.event_count += 1
                    replay.total_bytes += payload_bytes
                replay.status = status
                replay.expires_at = terminal_expiry
                replay.updated_at = now
                replay.terminal_at = now
                db.query(ChatGenerationReplayEvent).filter_by(
                    generation_id=generation_id
                ).update(
                    {"expires_at": terminal_expiry},
                    synchronize_session=False,
                )
            db.commit()
            db.refresh(row)
            return self._model(row)

    def append_replay_snapshot(
        self, generation_id: str, user_id: str, content: str
    ) -> Optional[ChatGenerationReplayModel]:
        """Persist a bounded assistant-visible snapshot as an ordered delta."""

        if not isinstance(content, str):
            raise TypeError("Replay content must be a string")

        with get_db() as db:
            generation = (
                db.query(ChatGeneration)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .with_for_update()
                .first()
            )
            if generation is None or generation.status != "running":
                return None

            replay = (
                db.query(ChatGenerationReplay)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .with_for_update()
                .first()
            )
            if replay is None:
                now = _now_ms()
                self._begin_replay(db, generation, now)
                db.flush()
                replay = db.get(ChatGenerationReplay, generation_id)
            if replay is None or replay.status != "running":
                return None
            if replay.degraded:
                return self._replay_model(replay)
            if content == replay.content:
                return self._replay_model(replay)

            replace = not content.startswith(replay.content)
            visible_content = content if replace else content[len(replay.content) :]
            event_payload = {
                "type": "content",
                "content": visible_content,
                "replace": replace,
            }
            payload, payload_bytes, digest = self._event_payload_bytes(event_payload)
            content_bytes = len(content.encode("utf-8"))
            would_degrade = (
                len(content) > REPLAY_MAX_CONTENT_CHARS
                or content_bytes > REPLAY_MAX_TOTAL_BYTES
                or payload_bytes > REPLAY_MAX_EVENT_BYTES
                or replay.total_bytes + payload_bytes > REPLAY_MAX_TOTAL_BYTES - 1024
                or replay.event_count >= REPLAY_MAX_EVENTS - 1
            )
            now = _now_ms()
            if would_degrade:
                replay.degraded = True
                replay.updated_at = now
                replay.expires_at = now + REPLAY_TERMINAL_TTL_MS
                db.commit()
                db.refresh(replay)
                return self._replay_model(replay)

            sequence = replay.last_sequence + 1
            expiry = now + REPLAY_RUNNING_TTL_MS
            db.add(
                ChatGenerationReplayEvent(
                    generation_id=generation_id,
                    sequence=sequence,
                    event_type="content",
                    payload=payload,
                    payload_digest=digest,
                    payload_bytes=payload_bytes,
                    expires_at=expiry,
                    created_at=now,
                )
            )
            replay.content = content
            replay.last_sequence = sequence
            replay.event_count += 1
            replay.total_bytes += payload_bytes
            replay.expires_at = expiry
            replay.updated_at = now
            db.commit()
            db.refresh(replay)
            return self._replay_model(replay)

    def get_replay_snapshot(
        self, generation_id: str, user_id: str
    ) -> Optional[ChatGenerationReplayModel]:
        with get_db() as db:
            replay = (
                db.query(ChatGenerationReplay)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .first()
            )
            if replay is None:
                return None
            if replay.expires_at <= _now_ms():
                db.query(ChatGenerationReplayEvent).filter_by(
                    generation_id=generation_id
                ).delete(synchronize_session=False)
                db.delete(replay)
                db.commit()
                return None
            return self._replay_model(replay)

    def get_replay_tail(
        self,
        generation_id: str,
        user_id: str,
        *,
        after_sequence: int,
        limit: int = REPLAY_TAIL_LIMIT,
        max_bytes: int = REPLAY_TAIL_MAX_BYTES,
    ) -> Optional[dict]:
        if after_sequence < 0:
            raise ValueError("Replay cursor must not be negative")
        bounded_limit = max(1, min(REPLAY_TAIL_LIMIT, int(limit)))
        bounded_bytes = max(1, min(REPLAY_MAX_EVENT_BYTES, int(max_bytes)))
        with get_db() as db:
            replay = (
                db.query(ChatGenerationReplay)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .first()
            )
            if replay is None or replay.expires_at <= _now_ms():
                return None
            rows = (
                db.query(ChatGenerationReplayEvent)
                .filter_by(generation_id=generation_id)
                .filter(ChatGenerationReplayEvent.sequence > after_sequence)
                .order_by(ChatGenerationReplayEvent.sequence.asc())
                .limit(bounded_limit)
                .all()
            )
            events = []
            consumed = 0
            for row in rows:
                if events and consumed + row.payload_bytes > bounded_bytes:
                    break
                encoded_payload = row.payload.encode("utf-8")
                payload_valid = (
                    len(encoded_payload) == row.payload_bytes
                    and hashlib.sha256(encoded_payload).hexdigest()
                    == row.payload_digest
                )
                try:
                    payload = (
                        json.loads(row.payload)
                        if payload_valid
                        else {"type": "invalid"}
                    )
                except (TypeError, json.JSONDecodeError):
                    payload = {"type": "invalid"}
                events.append(
                    {
                        "sequence": row.sequence,
                        "type": row.event_type,
                        "payload": payload,
                    }
                )
                consumed += row.payload_bytes
            return {
                "cursor": replay.last_sequence,
                "status": replay.status,
                "degraded": replay.degraded,
                "events": events,
                "expires_at": replay.expires_at,
            }

    def is_stop_requested(self, generation_id: str, user_id: str) -> bool:
        with get_db() as db:
            row = (
                db.query(ChatGeneration.status)
                .filter_by(generation_id=generation_id, user_id=user_id)
                .first()
            )
            return bool(row and row[0] in ("stop_requested", "stopped"))


ChatGenerations = ChatGenerationTable()
