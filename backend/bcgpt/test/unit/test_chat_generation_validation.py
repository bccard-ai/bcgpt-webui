"""Request-shape and persisted-message proof tests for chat generation admission."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import bcgpt.utils.chat_generation as validation
from bcgpt.utils.chat_generation import (
    ChatGenerationValidationError,
    parse_chat_generation_request,
    verify_chat_generation_message_proof,
)


def valid_form() -> dict:
    user_message_id = str(uuid4())
    return {
        "generation_id": str(uuid4()),
        "turn_id": user_message_id,
        "client_message_id": user_message_id,
        "chat_id": str(uuid4()),
        "id": str(uuid4()),
    }


def test_generation_identifiers_are_all_or_nothing_and_canonical() -> None:
    assert (
        parse_chat_generation_request(
            {"chat_id": str(uuid4()), "id": str(uuid4())},
            user_id="owner-a",
            model_id="model-a",
        )
        is None
    )

    form = valid_form()
    form.pop("turn_id")
    with pytest.raises(ChatGenerationValidationError):
        parse_chat_generation_request(form, user_id="owner-a", model_id="model-a")

    form = valid_form()
    form["generation_id"] = "not-a-uuid"
    with pytest.raises(ChatGenerationValidationError):
        parse_chat_generation_request(form, user_id="owner-a", model_id="model-a")


def test_turn_id_must_match_client_message_id() -> None:
    form = valid_form()
    form["turn_id"] = str(uuid4())
    with pytest.raises(ChatGenerationValidationError, match="turn_id"):
        parse_chat_generation_request(form, user_id="owner-a", model_id="model-a")


def test_persisted_user_assistant_parent_and_model_proof(monkeypatch) -> None:
    form = valid_form()
    request = parse_chat_generation_request(form, user_id="owner-a", model_id="model-a")
    assert request is not None

    chat = SimpleNamespace(
        chat={
            "history": {
                "messages": {
                    request.client_message_id: {
                        "id": request.client_message_id,
                        "role": "user",
                    },
                    request.assistant_message_id: {
                        "id": request.assistant_message_id,
                        "role": "assistant",
                        "parentId": request.client_message_id,
                        "model": "model-a",
                    },
                }
            }
        }
    )
    monkeypatch.setattr(
        validation.Chats,
        "get_chat_by_id_and_user_id",
        lambda chat_id, user_id: chat,
    )
    verify_chat_generation_message_proof(request)

    chat.chat["history"]["messages"][request.assistant_message_id]["parentId"] = str(
        uuid4()
    )
    with pytest.raises(ChatGenerationValidationError, match="Assistant message proof"):
        verify_chat_generation_message_proof(request)
