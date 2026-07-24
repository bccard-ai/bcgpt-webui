"""
Base class for all LLM providers.

Every provider must implement:
  - chat_completions()  : OpenAI-compatible chat completion (streaming + non-streaming)
  - get_models()        : List available models
  - verify_connection() : Test API connectivity

Providers receive config at init time and use the shared aiohttp session
from bcgpt.utils.http_client for connection pooling.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi import Request

from bcgpt.models import UserModel


class BaseLLMProvider(ABC):
    provider_name: str = ""

    def __init__(self, config: Any):
        self.config = config

    @abstractmethod
    async def chat_completions(
        self,
        request: Request,
        form_data: dict,
        user: UserModel,
        *,
        bypass_filter: bool = False,
    ) -> Any:
        """Return either a dict (non-streaming) or StreamingResponse (streaming)."""

    @abstractmethod
    async def get_models(
        self, request: Request, user: Optional[UserModel] = None
    ) -> list[dict]:
        """Return a list of model dicts compatible with OpenAI model listing."""

    @abstractmethod
    async def verify_connection(self, request: Request, user: UserModel) -> dict:
        """Verify API connectivity. Return success dict or raise HTTPException."""

    def get_owned_by(self) -> str:
        """Value used in model['owned_by'] to identify this provider."""
        return self.provider_name
