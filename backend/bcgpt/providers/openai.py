"""
OpenAI-compatible provider – wraps the existing routers/openai.py logic.

This delegates to the existing `generate_chat_completion` and `get_all_models`
functions so that all current OpenAI-compatible endpoints (OpenAI, Azure,
OpenRouter, any OpenAI-compatible server) continue to work unchanged.
"""

import logging
from typing import Any, Optional

from fastapi import Request

from bcgpt.models import UserModel
from bcgpt.providers.base import BaseLLMProvider

from bcgpt.routers.openai import (
    generate_chat_completion as _openai_generate,
    get_all_models as _openai_get_models,
    verify_connection as _openai_verify,
)

log = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    provider_name = "openai"

    async def chat_completions(
        self,
        request: Request,
        form_data: dict,
        user: UserModel,
        *,
        bypass_filter: bool = False,
    ) -> Any:
        return await _openai_generate(
            request=request,
            form_data=form_data,
            user=user,
            bypass_filter=bypass_filter,
        )

    async def get_models(
        self, request: Request, user: Optional[UserModel] = None
    ) -> list[dict]:
        result = await _openai_get_models(request, user=user or UserModel())
        if isinstance(result, dict):
            return result.get("data", [])
        return []

    async def verify_connection(self, request: Request, user: UserModel) -> dict:
        return await _openai_verify(request=request, user=user)
