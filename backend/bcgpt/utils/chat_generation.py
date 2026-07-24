"""Validation and message-proof helpers for durable chat generation admission."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from bcgpt.models import Chats

GENERATION_REQUEST_FIELDS = (
    "generation_id",
    "turn_id",
    "client_message_id",
)


class ChatGenerationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ChatGenerationRequest:
    generation_id: str
    turn_id: str
    client_message_id: str
    assistant_message_id: str
    user_id: str
    chat_id: str
    model_id: str


def parse_uuid(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ChatGenerationValidationError(f"{field_name} must be a UUID")
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ChatGenerationValidationError(f"{field_name} must be a UUID") from exc
    if str(parsed) != value.lower():
        raise ChatGenerationValidationError(f"{field_name} must be a canonical UUID")
    return str(parsed)


def parse_chat_generation_request(
    form_data: dict, *, user_id: str, model_id: str
) -> ChatGenerationRequest | None:
    values = [form_data.get(field) for field in GENERATION_REQUEST_FIELDS]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ChatGenerationValidationError(
            "generation_id, turn_id, and client_message_id must be supplied together"
        )

    generation_id = parse_uuid(form_data.get("generation_id"), "generation_id")
    turn_id = parse_uuid(form_data.get("turn_id"), "turn_id")
    client_message_id = parse_uuid(
        form_data.get("client_message_id"), "client_message_id"
    )
    assistant_message_id = parse_uuid(form_data.get("id"), "id")
    chat_id = parse_uuid(form_data.get("chat_id"), "chat_id")

    if turn_id != client_message_id:
        raise ChatGenerationValidationError(
            "turn_id must match the admitted client message id"
        )

    return ChatGenerationRequest(
        generation_id=generation_id,
        turn_id=turn_id,
        client_message_id=client_message_id,
        assistant_message_id=assistant_message_id,
        user_id=str(user_id),
        chat_id=chat_id,
        model_id=str(model_id),
    )


def verify_chat_generation_message_proof(request: ChatGenerationRequest) -> None:
    chat = Chats.get_chat_by_id_and_user_id(request.chat_id, request.user_id)
    if chat is None:
        raise ChatGenerationValidationError("Chat generation authority was not found")

    messages = chat.chat.get("history", {}).get("messages", {})
    user_message = messages.get(request.client_message_id)
    assistant_message = messages.get(request.assistant_message_id)
    if not isinstance(user_message, dict) or user_message.get("role") != "user":
        raise ChatGenerationValidationError("Client message proof is invalid")
    if (
        not isinstance(assistant_message, dict)
        or assistant_message.get("role") != "assistant"
        or assistant_message.get("parentId") != request.client_message_id
    ):
        raise ChatGenerationValidationError("Assistant message proof is invalid")
    if assistant_message.get("model") not in (None, request.model_id):
        raise ChatGenerationValidationError("Assistant model proof is invalid")


def verify_assistant_message_authority(
    *, user_id: str, chat_id: str, assistant_message_id: str
) -> bool:
    chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if chat is None:
        return False
    message = chat.chat.get("history", {}).get("messages", {}).get(assistant_message_id)
    return isinstance(message, dict) and message.get("role") == "assistant"
