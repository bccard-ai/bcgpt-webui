"""
Provider Registry – maps owned_by tags to provider instances.

Usage:
    from bcgpt.providers import get_provider

    provider = get_provider(model_dict)
    if provider:
        response = await provider.chat_completions(request, form_data, user)
"""

import logging
from typing import Optional

from bcgpt.providers.base import BaseLLMProvider
from bcgpt.providers.openai import OpenAIProvider
from bcgpt.providers.ollama import OllamaProvider
from bcgpt.providers.gemini import GeminiProvider
from bcgpt.providers.claude import ClaudeProvider

log = logging.getLogger(__name__)

_PROVIDERS: dict[str, BaseLLMProvider] = {}


def init_providers(config) -> None:
    """Initialize all provider instances with the given app config.

    Call once at app startup (in main.py lifespan or after config load).
    """
    global _PROVIDERS
    _PROVIDERS = {
        "ollama": OllamaProvider(config),
        "openai": OpenAIProvider(config),
        "gemini": GeminiProvider(config),
        "claude": ClaudeProvider(config),
    }
    log.info(f"Initialized providers: {list(_PROVIDERS.keys())}")


def get_provider(model: dict) -> Optional[BaseLLMProvider]:
    """Look up the provider for a given model dict.

    The model dict should have an 'owned_by' key set by the frontend
    or by the model listing endpoint (e.g. 'ollama', 'openai', 'gemini', 'claude').
    """
    owned_by = model.get("owned_by", "")
    if owned_by in ("", "arena"):
        return None
    provider = _PROVIDERS.get(owned_by)
    if provider is None:
        log.warning(
            f"No provider registered for owned_by='{owned_by}', falling back to openai"
        )
        provider = _PROVIDERS.get("openai")
    return provider


def get_all_providers() -> dict[str, BaseLLMProvider]:
    return _PROVIDERS


def get_provider_names() -> list[str]:
    return list(_PROVIDERS.keys())
