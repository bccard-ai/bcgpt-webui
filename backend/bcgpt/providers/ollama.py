"""
Ollama provider – wraps the existing routers/ollama.py logic.

The existing ollama router already handles chat completions, model listing,
and connection verification. We delegate to it and handle the OpenAI format
conversion that chat.py already performs.
"""

import logging
from typing import Any, Optional

from fastapi import Request
from starlette.responses import StreamingResponse

from bcgpt.models import UserModel
from bcgpt.providers.base import BaseLLMProvider
from bcgpt.utils import convert_payload_openai_to_ollama
from bcgpt.utils.response import (
    convert_response_ollama_to_openai,
    convert_streaming_response_ollama_to_openai,
)

from bcgpt.routers.ollama import (
    generate_chat_completion as _ollama_generate,
    get_all_models as _ollama_get_models,
    verify_connection as _ollama_verify,
)

log = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    provider_name = "ollama"

    async def chat_completions(
        self,
        request: Request,
        form_data: dict,
        user: UserModel,
        *,
        bypass_filter: bool = False,
    ) -> Any:
        ollama_payload = convert_payload_openai_to_ollama(form_data)
        response = await _ollama_generate(
            request=request,
            form_data=ollama_payload,
            user=user,
            bypass_filter=bypass_filter,
        )

        if form_data.get("stream", False):
            response.headers["content-type"] = "text/event-stream"
            return StreamingResponse(
                convert_streaming_response_ollama_to_openai(response),
                headers=dict(response.headers),
                background=response.background,
            )
        else:
            return convert_response_ollama_to_openai(response)

    async def get_models(
        self, request: Request, user: Optional[UserModel] = None
    ) -> list[dict]:
        result = await _ollama_get_models(request, user=user or UserModel())
        if isinstance(result, dict):
            return result.get("data", [])
        return []

    async def verify_connection(self, request: Request, user: UserModel) -> dict:
        return await _ollama_verify(request=request, user=user)
