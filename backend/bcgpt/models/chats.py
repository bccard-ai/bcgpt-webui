"""Chat persistence layer — ORM model, Pydantic schemas, and data-access table.

Public exports consumed across the application:

    * ``Chat``              — SQLAlchemy declarative model (``chat`` table)
    * ``ChatModel``         — Pydantic representation of a persisted chat row
    * ``ChatForm``          — Inbound form for creating a new chat
    * ``ChatImportForm``    — Extended form used when importing chats
    * ``ChatTitleMessagesForm`` — Form carrying title + message list
    * ``ChatTitleForm``     — Form carrying only a title update
    * ``ChatResponse``      — Full chat DTO returned by API endpoints
    * ``ChatTitleIdResponse`` — Lightweight DTO (id / title / timestamps)
    * ``ChatSearchMessage`` — Bounded visible-message search projection
    * ``ChatSearchResult``  — Search DTO with snippet and message anchor
    * ``ChatTable``         — Class that groups all CRUD operations
    * ``Chats``             — Module-level singleton (``ChatTable()``)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy import and_, func, or_, select, text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, get_db
from bcgpt.models import TagModel, Tag, Tags

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_ts() -> int:
    """Return the current wall-clock time as an integer epoch seconds value."""
    return int(time.time())


def _extract_title(chat_data: dict[str, Any], fallback: str = "New Chat") -> str:
    """Derive a human-readable title from raw chat payload data."""
    return chat_data.get("title", fallback)


def _normalize_tag(name: str) -> str:
    """Canonicalise a tag name for storage and lookup (lowercase, underscores)."""
    return name.replace(" ", "_").lower()


_SEARCHABLE_ROLES = frozenset({"user", "assistant"})
_MAX_SEARCH_MESSAGE_CHARS = 100_000
_MAX_SEARCH_MESSAGES_PER_CHAT = 20_000
_MAX_SEARCH_CHAT_CHARS = 2_000_000


def _searchable_message_content(content: Any) -> str:
    """Extract only user-visible text from a message content value.

    Tool payloads, citations, model metadata, and arbitrary dictionaries are
    deliberately excluded from the search projection. Structured text blocks
    used by multimodal clients are accepted when their type is explicitly
    text-like.
    """
    if isinstance(content, str):
        return content.replace("\x00", "")[:_MAX_SEARCH_MESSAGE_CHARS]
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    remaining = _MAX_SEARCH_MESSAGE_CHARS
    for block in content:
        value = ""
        if isinstance(block, str):
            value = block
        elif isinstance(block, dict) and block.get("type") in {
            "text",
            "input_text",
            "output_text",
        }:
            candidate = block.get("text", block.get("content", ""))
            if isinstance(candidate, str):
                value = candidate
        if value and remaining > 0:
            value = value.replace("\x00", "")[:remaining]
            parts.append(value)
            remaining -= len(value)
        if remaining <= 0:
            break
    return "\n".join(parts)[:_MAX_SEARCH_MESSAGE_CHARS]


def _iter_searchable_messages(chat_data: dict[str, Any]):
    """Yield bounded message projection records with anchor capability."""
    history = chat_data.get("history") if isinstance(chat_data, dict) else None
    messages: Any = history.get("messages") if isinstance(history, dict) else None
    if not messages:
        messages = chat_data.get("messages") if isinstance(chat_data, dict) else None

    if isinstance(messages, dict):
        entries = messages.items()
        anchorable = True
    elif isinstance(messages, list):
        entries = enumerate(messages)
        anchorable = False
    else:
        return

    seen: set[str] = set()
    remaining_chat_chars = _MAX_SEARCH_CHAT_CHARS
    for position, (key, message) in enumerate(entries):
        if position >= _MAX_SEARCH_MESSAGES_PER_CHAT or remaining_chat_chars <= 0:
            break
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in _SEARCHABLE_ROLES:
            continue
        message_id = str(message.get("id") or key)
        if not message_id or len(message_id) > 255 or message_id in seen:
            continue
        content = _searchable_message_content(message.get("content"))
        if not content:
            continue
        content = content[:remaining_chat_chars]
        remaining_chat_chars -= len(content)
        seen.add(message_id)
        yield message_id, role, content, position, anchorable


def _make_search_snippet(content: str, query: str, radius: int = 70) -> str:
    """Build a plain-text, markup-free context snippet around a match."""
    collapsed = " ".join(content.split())
    start = collapsed.casefold().find(query.casefold())
    if start < 0:
        return collapsed[: radius * 2]
    end = start + len(query)
    left = max(0, start - radius)
    right = min(len(collapsed), end + radius)
    return (
        ("…" if left else "")
        + collapsed[left:right]
        + ("…" if right < len(collapsed) else "")
    )


def _validate_chat_row(db, chat_id: str):
    """Fetch a ``Chat`` row by primary key; raise on missing so the caller's
    ``except`` block returns ``None`` / ``False``."""
    row = db.get(Chat, chat_id)
    if row is None:
        raise LookupError("chat not found: %s", chat_id)
    return row


def _build_tag_filter_fragment(dialect: str, tag_id: str, param_name: str):
    """Return an ``sqlalchemy.text`` clause that checks for a tag inside the
    ``meta->tags`` JSON array, parameterised as *param_name*.

    Supports *sqlite* and *postgresql* dialects; raises ``NotImplementedError``
    for anything else.
    """
    if dialect == "sqlite":
        sql = (
            "EXISTS ("
            "  SELECT 1 FROM json_each(Chat.meta, '$.tags') "
            f"  WHERE json_each.value = :{param_name}"
            ")"
        )
        return text(sql)
    if dialect == "postgresql":
        sql = (
            "EXISTS ("
            "  SELECT 1 FROM json_array_elements_text(Chat.meta->'tags') elem "
            f"  WHERE elem = :{param_name}"
            ")"
        )
        return text(sql)
    raise NotImplementedError("Unsupported dialect: %s", dialect)


def _build_no_tags_fragment(dialect: str):
    """Return a clause ensuring ``meta->tags`` is empty / absent."""
    if dialect == "sqlite":
        return text(
            "NOT EXISTS (" "  SELECT 1 FROM json_each(Chat.meta, '$.tags') AS tag" ")"
        )
    if dialect == "postgresql":
        return text(
            "NOT EXISTS ("
            "  SELECT 1 FROM json_array_elements_text(Chat.meta->'tags') AS tag"
            ")"
        )
    raise NotImplementedError("Unsupported dialect: %s", dialect)


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------


class Chat(Base):
    """Persisted conversation record.

    Each row stores the full chat tree as a JSON blob in the ``chat`` column
    and carries lightweight metadata columns for filtering and sorting.
    """

    __tablename__ = "chat"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(Text)
    chat = Column(JSON)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)

    share_id = Column(Text, unique=True, nullable=True)
    archived = Column(Boolean, default=False)
    pinned = Column(Boolean, default=False, nullable=True)

    meta = Column(JSON, server_default="{}")
    folder_id = Column(Text, nullable=True)


class ChatSearchMessage(Base):
    """Bounded, searchable projection of visible conversation text."""

    __tablename__ = "chat_search_message"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_chat_search_message_role"
        ),
        Index("ix_chat_search_message_user_chat", "user_id", "chat_id"),
        Index("ix_chat_search_message_user_updated", "user_id", "updated_at"),
    )

    chat_id = Column(
        String,
        ForeignKey("chat.id", ondelete="CASCADE"),
        primary_key=True,
    )
    message_id = Column(String(length=255), primary_key=True)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    anchorable = Column(Boolean, nullable=False, default=True)
    updated_at = Column(BigInteger, nullable=False)


def _sync_chat_search_projection(db, row: Chat) -> None:
    """Replace one chat's search rows inside the caller's transaction."""
    db.query(ChatSearchMessage).filter_by(chat_id=row.id).delete(
        synchronize_session=False
    )
    for message_id, role, content, position, anchorable in _iter_searchable_messages(
        row.chat or {}
    ):
        db.add(
            ChatSearchMessage(
                chat_id=row.id,
                message_id=message_id,
                user_id=row.user_id,
                role=role,
                content=content,
                position=position,
                anchorable=anchorable,
                updated_at=row.updated_at,
            )
        )


def _delete_chat_search_projection(db, chat_ids: list[str]) -> None:
    if chat_ids:
        db.query(ChatSearchMessage).filter(
            ChatSearchMessage.chat_id.in_(chat_ids)
        ).delete(synchronize_session=False)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ChatModel(BaseModel):
    """Full ORM-to-Pydantic mapping for a ``chat`` row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    chat: dict

    created_at: int
    updated_at: int

    share_id: Optional[str] = None
    archived: bool = False
    pinned: Optional[bool] = False

    meta: dict = {}
    folder_id: Optional[str] = None


class ChatForm(BaseModel):
    """Payload accepted when creating a new chat."""

    chat: dict


class ChatImportForm(ChatForm):
    """Extended payload for importing an existing chat with metadata."""

    meta: Optional[dict] = {}
    pinned: Optional[bool] = False
    folder_id: Optional[str] = None


class ChatTitleMessagesForm(BaseModel):
    """Payload carrying both a title and a list of chat messages."""

    title: str
    messages: list[dict]


class ChatTitleForm(BaseModel):
    """Payload for updating only the chat title."""

    title: str


class ChatResponse(BaseModel):
    """Full chat DTO serialised by API endpoints."""

    id: str
    user_id: str
    title: str
    chat: dict
    updated_at: int
    created_at: int
    share_id: Optional[str] = None
    archived: bool
    pinned: Optional[bool] = False
    meta: dict = {}
    folder_id: Optional[str] = None


class ChatTitleIdResponse(BaseModel):
    """Lightweight DTO exposing id, title, and timestamps for list views."""

    id: str
    title: str
    updated_at: int
    created_at: int


class ChatSearchResult(ChatTitleIdResponse):
    """Chat search hit with an optional message-level jump target."""

    match_message_id: Optional[str] = None
    match_role: Optional[str] = None
    match_snippet: Optional[str] = None


# ---------------------------------------------------------------------------
# Data-access layer
# ---------------------------------------------------------------------------


class ChatTable:
    """Groups all CRUD operations for the ``chat`` table.

    Every public method opens its own short-lived database session via
    :pyfunc:`bcgpt.internal.get_db` and returns plain Pydantic models or
    builtin types — never leaked ORM objects.
    """

    # -- Mutations ----------------------------------------------------------

    def insert_new_chat(self, user_id: str, form_data: ChatForm) -> Optional[ChatModel]:
        """Persist a brand-new chat and return its model representation."""
        with get_db() as db:
            now = _now_ts()
            model = ChatModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=_extract_title(form_data.chat),
                chat=form_data.chat,
                created_at=now,
                updated_at=now,
            )
            row = Chat(**model.model_dump())
            db.add(row)
            db.flush()
            _sync_chat_search_projection(db, row)
            db.commit()
            db.refresh(row)
            return ChatModel.model_validate(row) if row else None

    def new_chats_by_day(self, start_ts_s: int, end_ts_s: int) -> list[dict]:
        """Count of new chats per epoch-day in [start_ts_s, end_ts_s] (epoch sec).

        ``chat.created_at`` is epoch seconds, so epoch-day = floor(sec / 86400).
        DB-agnostic float-floor (works on PostgreSQL and SQLite).
        """
        from sqlalchemy import cast, func, Integer

        day_expr = cast(func.floor(Chat.created_at / 86400.0), Integer).label("day")
        with get_db() as db:
            rows = (
                db.query(day_expr, func.count(Chat.id))
                .filter(Chat.created_at >= start_ts_s, Chat.created_at <= end_ts_s)
                .group_by(day_expr)
                .order_by(day_expr)
                .all()
            )
            return [{"day": int(r[0]), "value": int(r[1])} for r in rows]

    def import_chat(
        self, user_id: str, form_data: ChatImportForm
    ) -> Optional[ChatModel]:
        """Import an external chat including optional meta, pinned state, and folder."""
        with get_db() as db:
            now = _now_ts()
            model = ChatModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=_extract_title(form_data.chat),
                chat=form_data.chat,
                meta=form_data.meta,
                pinned=form_data.pinned,
                folder_id=form_data.folder_id,
                created_at=now,
                updated_at=now,
            )
            row = Chat(**model.model_dump())
            db.add(row)
            db.flush()
            _sync_chat_search_projection(db, row)
            db.commit()
            db.refresh(row)
            return ChatModel.model_validate(row) if row else None

    def update_chat_by_id(self, id: str, chat: dict) -> Optional[ChatModel]:
        """Overwrite the full ``chat`` JSON blob and refresh ``updated_at``."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.chat = chat
                row.title = _extract_title(chat)
                row.updated_at = _now_ts()
                _sync_chat_search_projection(db, row)
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def update_chat_title_by_id(self, id: str, title: str) -> Optional[ChatModel]:
        """Replace the title string inside the stored chat payload."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None
        data = chat_model.chat
        data["title"] = title
        return self.update_chat_by_id(id, data)

    def update_chat_tags_by_id(
        self, id: str, tags: list[str], user
    ) -> Optional[ChatModel]:
        """Replace the full tag list on a chat, cleaning up orphaned tag rows."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None

        self.delete_all_tags_by_id_and_user_id(id, user.id)

        for stale_tag in chat_model.meta.get("tags", []):
            if self.count_chats_by_tag_name_and_user_id(stale_tag, user.id) == 0:
                Tags.delete_tag_by_name_and_user_id(stale_tag, user.id)

        for tag_name in tags:
            if tag_name.lower() == "none":
                continue
            self.add_chat_tag_by_id_and_user_id_and_tag_name(id, user.id, tag_name)

        return self.get_chat_by_id(id)

    # -- Shared-chat mutations ----------------------------------------------

    def insert_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        """Create a shared copy of *chat_id* and record the ``share_id`` back-link."""
        with get_db() as db:
            original = _validate_chat_row(db, chat_id)
            if original.share_id:
                return self.get_chat_by_id_and_user_id(original.share_id, "shared")

            now = _now_ts()
            shared = ChatModel(
                id=str(uuid.uuid4()),
                user_id=f"shared-{chat_id}",
                title=original.title,
                chat=original.chat,
                created_at=original.created_at,
                updated_at=now,
            )
            shared_row = Chat(**shared.model_dump())
            db.add(shared_row)
            db.flush()
            _sync_chat_search_projection(db, shared_row)
            db.commit()
            db.refresh(shared_row)

            db.query(Chat).filter_by(id=chat_id).update({"share_id": shared.id})
            db.commit()
            return shared if (shared_row) else None

    def update_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        """Sync the shared copy with the latest title and chat data from the original."""
        try:
            with get_db() as db:
                _validate_chat_row(db, chat_id)
                shared = db.query(Chat).filter_by(user_id=f"shared-{chat_id}").first()
                if shared is None:
                    return self.insert_shared_chat_by_chat_id(chat_id)

                original = _validate_chat_row(db, chat_id)
                shared.title = original.title
                shared.chat = original.chat
                shared.updated_at = _now_ts()
                _sync_chat_search_projection(db, shared)
                db.commit()
                db.refresh(shared)
                return ChatModel.model_validate(shared)
        except Exception:
            return None

    def delete_shared_chat_by_chat_id(self, chat_id: str) -> bool:
        """Remove the shared copy associated with *chat_id*."""
        try:
            with get_db() as db:
                shared_ids = [
                    row[0]
                    for row in db.query(Chat.id)
                    .filter_by(user_id=f"shared-{chat_id}")
                    .all()
                ]
                _delete_chat_search_projection(db, shared_ids)
                db.query(Chat).filter_by(user_id=f"shared-{chat_id}").delete(
                    synchronize_session=False
                )
                db.commit()
                return True
        except Exception:
            return False

    def update_chat_share_id_by_id(
        self, id: str, share_id: Optional[str]
    ) -> Optional[ChatModel]:
        """Set or clear the ``share_id`` column on a chat."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.share_id = share_id
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    # -- Toggle helpers -----------------------------------------------------

    def toggle_chat_pinned_by_id(self, id: str) -> Optional[ChatModel]:
        """Flip the ``pinned`` flag and touch ``updated_at``."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.pinned = not row.pinned
                row.updated_at = _now_ts()
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def toggle_chat_archive_by_id(self, id: str) -> Optional[ChatModel]:
        """Flip the ``archived`` flag and touch ``updated_at``."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.archived = not row.archived
                row.updated_at = _now_ts()
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def archive_all_chats_by_user_id(self, user_id: str) -> bool:
        """Bulk-archive every chat belonging to *user_id*."""
        try:
            with get_db() as db:
                db.query(Chat).filter_by(user_id=user_id).update({"archived": True})
                db.commit()
                return True
        except Exception:
            return False

    # -- Queries (lists) ----------------------------------------------------

    def get_archived_chat_list_by_user_id(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        """Return all archived chats for *user_id* ordered by recency."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter_by(user_id=user_id, archived=True)
                .order_by(Chat.updated_at.desc())
                .all()
            )
            return [ChatModel.model_validate(r) for r in rows]

    def get_chat_list_by_user_id(
        self,
        user_id: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ChatModel]:
        """Return chats for *user_id*, optionally including archived, with pagination."""
        with get_db() as db:
            query = db.query(Chat).filter_by(user_id=user_id)
            if not include_archived:
                query = query.filter_by(archived=False)

            query = query.order_by(Chat.updated_at.desc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            return [ChatModel.model_validate(r) for r in query.all()]

    def get_chat_title_id_list_by_user_id(
        self,
        user_id: str,
        include_archived: bool = False,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[ChatTitleIdResponse]:
        """Return lightweight id/title/timestamp tuples for unpinned, unfiled chats."""
        with get_db() as db:
            query = db.query(Chat).filter_by(user_id=user_id).filter_by(folder_id=None)
            query = query.filter(
                or_(Chat.pinned == False, Chat.pinned == None)
            )  # noqa: E712

            if not include_archived:
                query = query.filter_by(archived=False)

            query = query.order_by(Chat.updated_at.desc()).with_entities(
                Chat.id, Chat.title, Chat.updated_at, Chat.created_at
            )

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            return [
                ChatTitleIdResponse.model_validate(
                    {
                        "id": r[0],
                        "title": r[1],
                        "updated_at": r[2],
                        "created_at": r[3],
                    }
                )
                for r in query.all()
            ]

    def get_chat_list_by_chat_ids(
        self, chat_ids: list[str], skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        """Return non-archived chats whose ids appear in *chat_ids*."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter(Chat.id.in_(chat_ids))
                .filter_by(archived=False)
                .order_by(Chat.updated_at.desc())
                .all()
            )
            return [ChatModel.model_validate(r) for r in rows]

    # -- Queries (single) ---------------------------------------------------

    def get_chat_by_id(self, id: str) -> Optional[ChatModel]:
        """Fetch a single chat by its primary key."""
        try:
            with get_db() as db:
                row = db.get(Chat, id)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def get_chat_by_share_id(self, id: str) -> Optional[ChatModel]:
        """Resolve a shared link — returns the chat if the share is still active."""
        try:
            with get_db() as db:
                link = db.query(Chat).filter_by(share_id=id).first()
                if link:
                    return self.get_chat_by_id(id)
                return None
        except Exception:
            return None

    def get_chat_by_id_and_user_id(self, id: str, user_id: str) -> Optional[ChatModel]:
        """Fetch a chat only if it belongs to *user_id*."""
        try:
            with get_db() as db:
                row = db.query(Chat).filter_by(id=id, user_id=user_id).first()
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def get_chats(self, skip: int = 0, limit: int = 50) -> list[ChatModel]:
        """Return every chat in the system ordered by recency."""
        with get_db() as db:
            rows = db.query(Chat).order_by(Chat.updated_at.desc())
            return [ChatModel.model_validate(r) for r in rows]

    def get_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        """Return every chat for *user_id* ordered by recency."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter_by(user_id=user_id)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(r) for r in rows]

    def get_pinned_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        """Return pinned, non-archived chats for *user_id*."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter_by(user_id=user_id, pinned=True, archived=False)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(r) for r in rows]

    def get_archived_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        """Return all archived chats for *user_id*."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter_by(user_id=user_id, archived=True)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(r) for r in rows]

    # -- Queries (message-level access) -------------------------------------

    def get_chat_title_by_id(self, id: str) -> Optional[str]:
        """Return the title string from the chat payload."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None
        return chat_model.chat.get("title", "New Chat")

    def get_messages_by_chat_id(self, id: str) -> Optional[dict]:
        """Return the ``history.messages`` dict from the stored chat payload."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None
        return chat_model.chat.get("history", {}).get("messages", {}) or {}

    def get_message_by_id_and_message_id(
        self, id: str, message_id: str
    ) -> Optional[dict]:
        """Return a single message dict by its *message_id* key."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None
        return (
            chat_model.chat.get("history", {}).get("messages", {}).get(message_id, {})
        )

    def upsert_message_to_chat_by_id_and_message_id(
        self, id: str, message_id: str, message: dict
    ) -> Optional[ChatModel]:
        """Insert or merge a message into the chat history and set ``currentId``."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None

        data = chat_model.chat
        history = data.get("history", {})

        if message_id in history.get("messages", {}):
            history["messages"][message_id] = {
                **history["messages"][message_id],
                **message,
            }
        else:
            history["messages"][message_id] = message

        history["currentId"] = message_id
        data["history"] = history
        return self.update_chat_by_id(id, data)

    def add_message_status_to_chat_by_id_and_message_id(
        self, id: str, message_id: str, status: dict
    ) -> Optional[ChatModel]:
        """Append a status entry to ``statusHistory`` on the given message."""
        chat_model = self.get_chat_by_id(id)
        if chat_model is None:
            return None

        data = chat_model.chat
        history = data.get("history", {})

        if message_id in history.get("messages", {}):
            status_log = history["messages"][message_id].get("statusHistory", [])
            status_log.append(status)
            history["messages"][message_id]["statusHistory"] = status_log

        data["history"] = history
        return self.update_chat_by_id(id, data)

    # -- Search -------------------------------------------------------------

    def get_chats_by_user_id_and_search_text(
        self,
        user_id: str,
        search_text: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 60,
    ) -> list[ChatSearchResult]:
        """Search titles and the normalized message projection with tag filters.

        Tag filters are expressed as ``tag:<name>`` tokens inside the query
        string.  The special token ``tag:none`` matches chats with no tags.
        """
        normalized = search_text.lower().strip()
        if not normalized:
            chats = self.get_chat_list_by_user_id(
                user_id, include_archived, skip, limit
            )
            return [ChatSearchResult(**chat.model_dump()) for chat in chats]

        words = normalized.split(" ")

        # Extract tag: prefixed tokens
        tag_ids = [
            _normalize_tag(w.replace("tag:", "")) for w in words if w.startswith("tag:")
        ]
        content_words = [w for w in words if not w.startswith("tag:")]
        content_query = " ".join(content_words)

        with get_db() as db:
            query = db.query(Chat).filter(Chat.user_id == user_id)
            if not include_archived:
                query = query.filter(Chat.archived == False)  # noqa: E712
            query = query.order_by(Chat.updated_at.desc())

            # Title / content search
            if content_query:
                escaped_title_match = func.lower(Chat.title).contains(
                    content_query, autoescape=True
                )
                message_match = (
                    select(ChatSearchMessage.message_id)
                    .where(
                        ChatSearchMessage.chat_id == Chat.id,
                        ChatSearchMessage.user_id == user_id,
                        func.lower(ChatSearchMessage.content).contains(
                            content_query, autoescape=True
                        ),
                    )
                    .exists()
                )
                query = query.filter(or_(escaped_title_match, message_match))

            dialect = db.bind.dialect.name

            # Tag filtering — must match ALL specified tags
            if "none" in tag_ids:
                query = query.filter(_build_no_tags_fragment(dialect))
            elif tag_ids:
                query = query.filter(
                    and_(
                        *[
                            _build_tag_filter_fragment(
                                dialect, tid, f"tag_id_{idx}"
                            ).params(**{f"tag_id_{idx}": tid})
                            for idx, tid in enumerate(tag_ids)
                        ]
                    )
                )

            rows = query.offset(skip).limit(limit).all()
            log.info("Search returned %d chats for user %s", len(rows), user_id)
            first_matches: dict[str, ChatSearchMessage] = {}
            if content_query and rows:
                matches = (
                    db.query(ChatSearchMessage)
                    .filter(
                        ChatSearchMessage.user_id == user_id,
                        ChatSearchMessage.chat_id.in_([row.id for row in rows]),
                        func.lower(ChatSearchMessage.content).contains(
                            content_query, autoescape=True
                        ),
                    )
                    .order_by(
                        ChatSearchMessage.chat_id,
                        ChatSearchMessage.position.desc(),
                    )
                    .all()
                )
                for match in matches:
                    first_matches.setdefault(match.chat_id, match)

            results: list[ChatSearchResult] = []
            for row in rows:
                match = first_matches.get(row.id)
                results.append(
                    ChatSearchResult(
                        id=row.id,
                        title=row.title,
                        updated_at=row.updated_at,
                        created_at=row.created_at,
                        match_message_id=(
                            match.message_id if match and match.anchorable else None
                        ),
                        match_role=match.role if match else None,
                        match_snippet=(
                            _make_search_snippet(match.content, content_query)
                            if match
                            else None
                        ),
                    )
                )
            return results

    # -- Folder queries -----------------------------------------------------

    def get_chats_by_folder_id_and_user_id(
        self, folder_id: str, user_id: str
    ) -> list[ChatModel]:
        """Return non-archived, unpinned chats in a specific folder."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter_by(folder_id=folder_id, user_id=user_id)
                .filter(or_(Chat.pinned == False, Chat.pinned == None))  # noqa: E712
                .filter_by(archived=False)
                .order_by(Chat.updated_at.desc())
                .all()
            )
            return [ChatModel.model_validate(r) for r in rows]

    def get_chats_by_folder_ids_and_user_id(
        self, folder_ids: list[str], user_id: str
    ) -> list[ChatModel]:
        """Return non-archived, unpinned chats across multiple folders."""
        with get_db() as db:
            rows = (
                db.query(Chat)
                .filter(Chat.folder_id.in_(folder_ids), Chat.user_id == user_id)
                .filter(or_(Chat.pinned == False, Chat.pinned == None))  # noqa: E712
                .filter_by(archived=False)
                .order_by(Chat.updated_at.desc())
                .all()
            )
            return [ChatModel.model_validate(r) for r in rows]

    def update_chat_folder_id_by_id_and_user_id(
        self, id: str, user_id: str, folder_id: str
    ) -> Optional[ChatModel]:
        """Move a chat into a folder (also unpins it)."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.folder_id = folder_id
                row.updated_at = _now_ts()
                row.pinned = False
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    # -- Tag queries --------------------------------------------------------

    def get_chat_tags_by_id_and_user_id(self, id: str, user_id: str) -> list[TagModel]:
        """Resolve the tag models stored in ``meta.tags`` for a chat."""
        with get_db() as db:
            row = _validate_chat_row(db, id)
            return [
                Tags.get_tag_by_name_and_user_id(t, user_id)
                for t in row.meta.get("tags", [])
            ]

    def get_chat_list_by_user_id_and_tag_name(
        self, user_id: str, tag_name: str, skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        """Return all chats that carry the given tag."""
        with get_db() as db:
            tag_id = _normalize_tag(tag_name)
            query = db.query(Chat).filter_by(user_id=user_id)

            dialect = db.bind.dialect.name
            log.info("Tag search on dialect %s", dialect)
            query = query.filter(
                _build_tag_filter_fragment(dialect, tag_id, "tag_id")
            ).params(tag_id=tag_id)

            rows = query.all()
            log.debug("Tag search returned %d chats", len(rows))
            return [ChatModel.model_validate(r) for r in rows]

    def add_chat_tag_by_id_and_user_id_and_tag_name(
        self, id: str, user_id: str, tag_name: str
    ) -> Optional[ChatModel]:
        """Attach a tag to a chat, creating the tag row if necessary."""
        tag = Tags.get_tag_by_name_and_user_id(tag_name, user_id)
        if tag is None:
            tag = Tags.insert_new_tag(tag_name, user_id)
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                existing_tags = row.meta.get("tags", [])
                if tag.id not in existing_tags:
                    row.meta = {
                        **row.meta,
                        "tags": list(set(existing_tags + [tag.id])),
                    }
                db.commit()
                db.refresh(row)
                return ChatModel.model_validate(row)
        except Exception:
            return None

    def count_chats_by_tag_name_and_user_id(self, tag_name: str, user_id: str) -> int:
        """Count non-archived chats that carry the given tag."""
        with get_db() as db:
            tag_id = _normalize_tag(tag_name)
            dialect = db.bind.dialect.name
            query = db.query(Chat).filter_by(user_id=user_id, archived=False)
            query = query.filter(
                _build_tag_filter_fragment(dialect, tag_id, "tag_id")
            ).params(tag_id=tag_id)

            count = query.count()
            log.info("Count for tag '%s': %d", tag_name, count)
            return count

    def delete_tag_by_id_and_user_id_and_tag_name(
        self, id: str, user_id: str, tag_name: str
    ) -> bool:
        """Remove a single tag from a chat's ``meta.tags`` list."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                tag_id = _normalize_tag(tag_name)
                remaining = [t for t in row.meta.get("tags", []) if t != tag_id]
                row.meta = {**row.meta, "tags": list(set(remaining))}
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_tags_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        """Clear the entire ``meta.tags`` list on a chat."""
        try:
            with get_db() as db:
                row = _validate_chat_row(db, id)
                row.meta = {**row.meta, "tags": []}
                db.commit()
                return True
        except Exception:
            return False

    # -- Deletions ----------------------------------------------------------

    def delete_chat_by_id(self, id: str) -> bool:
        """Delete a chat and its shared copy."""
        try:
            with get_db() as db:
                _delete_chat_search_projection(db, [id])
                db.query(Chat).filter_by(id=id).delete(synchronize_session=False)
                db.commit()
                return True and self.delete_shared_chat_by_chat_id(id)
        except Exception:
            return False

    def delete_chat_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        """Delete a chat only if it belongs to *user_id*, plus shared copy."""
        try:
            with get_db() as db:
                owned = db.query(Chat.id).filter_by(id=id, user_id=user_id).first()
                _delete_chat_search_projection(db, [id] if owned else [])
                db.query(Chat).filter_by(id=id, user_id=user_id).delete(
                    synchronize_session=False
                )
                db.commit()
                return True and self.delete_shared_chat_by_chat_id(id)
        except Exception:
            return False

    def delete_chats_by_user_id(self, user_id: str) -> bool:
        """Delete all chats (including shared copies) for *user_id*."""
        try:
            with get_db() as db:
                self.delete_shared_chats_by_user_id(user_id)
                ids = [row[0] for row in db.query(Chat.id).filter_by(user_id=user_id)]
                _delete_chat_search_projection(db, ids)
                db.query(Chat).filter_by(user_id=user_id).delete(
                    synchronize_session=False
                )
                db.commit()
                return True
        except Exception:
            return False

    def delete_chats_by_user_id_and_folder_id(
        self, user_id: str, folder_id: str
    ) -> bool:
        """Delete all chats in a specific folder for *user_id*."""
        try:
            with get_db() as db:
                ids = [
                    row[0]
                    for row in db.query(Chat.id).filter_by(
                        user_id=user_id, folder_id=folder_id
                    )
                ]
                _delete_chat_search_projection(db, ids)
                db.query(Chat).filter_by(user_id=user_id, folder_id=folder_id).delete(
                    synchronize_session=False
                )
                db.commit()
                return True
        except Exception:
            return False

    def delete_shared_chats_by_user_id(self, user_id: str) -> bool:
        """Remove all shared copies derived from *user_id*'s chats."""
        try:
            with get_db() as db:
                user_chats = db.query(Chat).filter_by(user_id=user_id).all()
                shared_ids = [f"shared-{c.id}" for c in user_chats]
                projected_shared_ids = [
                    row[0]
                    for row in db.query(Chat.id).filter(Chat.user_id.in_(shared_ids))
                ]
                _delete_chat_search_projection(db, projected_shared_ids)
                db.query(Chat).filter(Chat.user_id.in_(shared_ids)).delete(
                    synchronize_session=False
                )
                db.commit()
                return True
        except Exception:
            return False

    # ── Data retention (open-moai adoption 2.4) ────────────────────────────
    # NOTE: Chat.created_at is epoch SECONDS (set via int(time.time())), unlike
    # audit/security timestamps which are milliseconds. Cutoffs use seconds.

    def delete_chats_older_than(self, days: int) -> int:
        """Hard-delete chats (and their shared copies) older than *days*.

        Returns the number of primary chat rows deleted. days<=0 is a no-op.
        """
        if not days or days <= 0:
            return 0
        try:
            cutoff = int(time.time() - days * 86400)
            with get_db() as db:
                old = db.query(Chat).filter(Chat.created_at < cutoff).all()
                shared_ids = [f"shared-{c.id}" for c in old]
                old_ids = [c.id for c in old]
                shared_chat_ids = [
                    row[0]
                    for row in db.query(Chat.id).filter(Chat.user_id.in_(shared_ids))
                ]
                _delete_chat_search_projection(db, old_ids + shared_chat_ids)
                deleted = (
                    db.query(Chat)
                    .filter(Chat.created_at < cutoff)
                    .delete(synchronize_session=False)
                )
                if shared_ids:
                    db.query(Chat).filter(Chat.user_id.in_(shared_ids)).delete(
                        synchronize_session=False
                    )
                db.commit()
                return int(deleted or 0)
        except Exception as e:
            log.exception("delete_chats_older_than failed: %s", e)
            return 0

    def anonymize_chats_older_than(self, days: int) -> int:
        """PII-mask chats older than *days* in place (GDPR/PIPA pre-purge).

        Masks the message tree + title with ``PIIScanner`` and flags the row as
        anonymized (idempotent — already-anonymized rows are skipped). Returns
        the number of rows newly anonymized. days<=0 is a no-op.
        """
        if not days or days <= 0:
            return 0
        try:
            from bcgpt.utils.security.pii import PIIScanner

            scanner = PIIScanner()
            cutoff = int(time.time() - days * 86400)
            count = 0
            with get_db() as db:
                rows = db.query(Chat).filter(Chat.created_at < cutoff).all()
                for row in rows:
                    meta = row.meta or {}
                    if meta.get("anonymized"):
                        continue
                    try:
                        row.chat = json.loads(scanner.mask(json.dumps(row.chat or {})))
                    except Exception:
                        pass  # keep original tree if (de)serialization fails
                    if row.title:
                        row.title = scanner.mask(row.title)
                    row.meta = {**meta, "anonymized": True}
                    _sync_chat_search_projection(db, row)
                    count += 1
                db.commit()
                return count
        except Exception as e:
            log.exception("anonymize_chats_older_than failed: %s", e)
            return 0


# Module-level singleton consumed throughout the application.
Chats = ChatTable()
