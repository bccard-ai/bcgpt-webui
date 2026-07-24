"""Embedding generation utilities.

Handles OpenAI-compatible, Ollama, and local sentence-transformers embedding
backends.  The public entry points are:

* ``generate_embeddings``           – dispatch to the right backend
* ``generate_openai_batch_embeddings`` – raw OpenAI /v1/embeddings call
* ``generate_ollama_batch_embeddings`` – raw Ollama /api/embed call
* ``get_embedding_function``        – factory that returns a callable
* ``get_model_path``                – resolve / download a HuggingFace model
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union

import requests
from huggingface_hub import snapshot_download

from bcgpt.env import (
    SRC_LOG_LEVELS,
    ENABLE_FORWARD_USER_INFO_HEADERS,
)
from bcgpt.config import (
    RAG_EMBEDDING_QUERY_PREFIX,
    RAG_EMBEDDING_PREFIX_FIELD_NAME,
)
from bcgpt.models import UserModel

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

# ---------------------------------------------------------------------------
# User-info headers helper
# ---------------------------------------------------------------------------


def _user_headers(user: UserModel | None) -> dict[str, str]:
    """Return BCGPT user-identity headers when forwarding is enabled."""
    if ENABLE_FORWARD_USER_INFO_HEADERS and user:
        return {
            "X-BCGPT-User-Name": user.name,
            "X-BCGPT-User-Id": user.id,
            "X-BCGPT-User-Email": user.email,
            "X-BCGPT-User-Role": user.role,
        }
    return {}


# ---------------------------------------------------------------------------
# OpenAI-compatible batch embeddings
# ---------------------------------------------------------------------------


def generate_openai_batch_embeddings(
    model: str,
    texts: list[str],
    url: str = "https://api.openai.com/v1",
    key: str = "",
    prefix: str | None = None,
    user: UserModel | None = None,
) -> list[list[float]] | None:
    """Call an OpenAI-compatible ``/embeddings`` endpoint.

    Returns a list of embedding vectors (one per input text), or ``None`` on
    failure.
    """
    try:
        payload: dict[str, Any] = {"input": texts, "model": model}
        if isinstance(RAG_EMBEDDING_PREFIX_FIELD_NAME, str) and isinstance(prefix, str):
            payload[RAG_EMBEDDING_PREFIX_FIELD_NAME] = prefix

        resp = requests.post(
            f"{url}/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                **_user_headers(user),
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        if "data" in data:
            return [elem["embedding"] for elem in data["data"]]

        log.error("OpenAI embeddings response missing 'data' key")
        return None
    except Exception as exc:
        log.exception("Error generating OpenAI batch embeddings: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Ollama batch embeddings
# ---------------------------------------------------------------------------


def generate_ollama_batch_embeddings(
    model: str,
    texts: list[str],
    url: str,
    key: str = "",
    prefix: str | None = None,
    user: UserModel | None = None,
) -> list[list[float]] | None:
    """Call the Ollama ``/api/embed`` endpoint.

    Returns a list of embedding vectors, or ``None`` on failure.
    """
    try:
        payload: dict[str, Any] = {"input": texts, "model": model}
        if isinstance(RAG_EMBEDDING_PREFIX_FIELD_NAME, str) and isinstance(prefix, str):
            payload[RAG_EMBEDDING_PREFIX_FIELD_NAME] = prefix

        resp = requests.post(
            f"{url}/api/embed",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                **_user_headers(user),
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        if "embeddings" in data:
            return data["embeddings"]

        log.error("Ollama embeddings response missing 'embeddings' key")
        return None
    except Exception as exc:
        log.exception("Error generating Ollama batch embeddings: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Unified embedding dispatcher
# ---------------------------------------------------------------------------


def generate_embeddings(
    engine: str,
    model: str,
    text: Union[str, list[str]],
    prefix: Union[str, None] = None,
    **kwargs: Any,
) -> list[float] | list[list[float]] | None:
    """Generate embeddings via the specified *engine* (``"openai"`` or ``"ollama"``).

    Accepts a single string or a list of strings.  When a single string is
    passed the return value is a single embedding vector; when a list is
    passed it is a list of vectors.
    """
    url: str = kwargs.get("url", "")
    key: str = kwargs.get("key", "")
    user = kwargs.get("user")

    # Prepend prefix into text when the API doesn't natively support it.
    if prefix is not None and RAG_EMBEDDING_PREFIX_FIELD_NAME is None:
        if isinstance(text, list):
            text = [f"{prefix}{t}" for t in text]
        else:
            text = f"{prefix}{text}"

    single = isinstance(text, str)
    texts = [text] if single else text

    if engine == "ollama":
        embeddings = generate_ollama_batch_embeddings(
            model=model,
            texts=texts,
            url=url,
            key=key,
            prefix=prefix,
            user=user,
        )
    elif engine == "openai":
        embeddings = generate_openai_batch_embeddings(
            model=model,
            texts=texts,
            url=url,
            key=key,
            prefix=prefix,
            user=user,
        )
    else:
        raise ValueError(f"Unknown embedding engine: {engine}")

    if embeddings is None:
        return None
    return embeddings[0] if single else embeddings


# ---------------------------------------------------------------------------
# Embedding function factory
# ---------------------------------------------------------------------------


def get_embedding_function(
    embedding_engine: str,
    embedding_model: str,
    embedding_function: Any,
    url: str,
    key: str,
    embedding_batch_size: int,
):
    """Return a callable ``f(query, prefix=None, user=None)`` that produces
    embedding vectors for the given *embedding_engine*.

    * ``""`` (empty string) – use the local sentence-transformers model
      provided via *embedding_function*.
    * ``"ollama"`` / ``"openai"`` – call the corresponding API with batching.
    """

    if embedding_engine == "":
        if embedding_function is None:
            return None
        return lambda query, prefix=None, user=None: embedding_function.encode(
            query, prompt=prefix if prefix else None
        ).tolist()

    if embedding_engine in ("ollama", "openai"):
        api_func = lambda query, prefix=None, user=None: generate_embeddings(
            engine=embedding_engine,
            model=embedding_model,
            text=query,
            prefix=prefix,
            url=url,
            key=key,
            user=user,
        )

        def _batched_wrapper(query, prefix, user, _func=api_func):
            if isinstance(query, list):
                embeddings: list = []
                for i in range(0, len(query), embedding_batch_size):
                    embeddings.extend(
                        _func(
                            query[i : i + embedding_batch_size],
                            prefix=prefix,
                            user=user,
                        )
                    )
                return embeddings
            return _func(query, prefix, user)

        return lambda query, prefix=None, user=None: _batched_wrapper(
            query, prefix, user
        )

    raise ValueError(f"Unknown embedding engine: {embedding_engine}")


# ---------------------------------------------------------------------------
# HuggingFace model path resolution
# ---------------------------------------------------------------------------


def get_model_path(model: str, update_model: bool = False) -> str:
    """Resolve *model* to a local filesystem path.

    If *model* is a short name (e.g. ``"all-MiniLM-L6-v2"``) the
    ``sentence-transformers`` org prefix is added automatically.  Offline mode
    is respected – when ``OFFLINE_MODE`` is set no network calls are made.
    """
    from bcgpt.env import OFFLINE_MODE

    cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME")
    local_files_only = not update_model or OFFLINE_MODE

    log.debug(
        "model: %s  cache_dir=%s  local_files_only=%s",
        model,
        cache_dir,
        local_files_only,
    )

    # Already a valid local path?
    if os.path.exists(model) or (
        ("\\" in model or model.count("/") > 1) and local_files_only
    ):
        return model

    # Short name → sentence-transformers org.
    if "/" not in model:
        model = f"sentence-transformers/{model}"

    try:
        path = snapshot_download(
            repo_id=model,
            cache_dir=cache_dir,
            local_files_only=local_files_only,
        )
        log.debug("model_repo_path: %s", path)
        return path
    except Exception as exc:
        log.exception("Cannot determine model snapshot path: %s", exc)
        return model
