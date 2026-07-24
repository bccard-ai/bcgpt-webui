"""
RAG retrieval router — vector DB management, embedding/reranking config,
document processing, and query endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter
from pydantic import BaseModel
import tiktoken

from bcgpt.config import (
    ENV,
    RAG_EMBEDDING_CONTENT_PREFIX,
    RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,
    RAG_EMBEDDING_QUERY_PREFIX,
    RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,
    UPLOAD_DIR,
    DEFAULT_LOCALE,
    VECTOR_DB,
)
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import DEVICE_TYPE, DOCKER, SRC_LOG_LEVELS
from bcgpt.models import FileModel, Files, Knowledges
from bcgpt.retrieval import VECTOR_DB_CLIENT
from bcgpt.retrieval.lifecycle import check_collection_access
from bcgpt.retrieval.vector.corpus import DEFAULT_WORKSPACE_ID
from bcgpt.retrieval import (
    Loader,
    SearchResult,
    YoutubeLoader,
    get_web_loader,
    search_bocha,
    search_brave,
    search_duckduckgo,
    search_exa,
    search_google_pse,
    search_jina,
    search_kagi,
    search_mojeek,
    search_naver,
    search_perplexity,
    search_searchapi,
    search_searxng,
    search_serper,
    search_serply,
    search_serpapi,
    search_serpstack,
    search_tavily,
    search_bing,
)
from bcgpt.retrieval.advanced.pipeline import search_with_advanced_pipeline
from bcgpt.retrieval.utils import (
    ExternalReranker,
    get_embedding_function,
    get_model_path,
    query_collection,
    query_collection_with_hybrid_search,
    query_doc,
    query_doc_with_hybrid_search,
)
from bcgpt.storage import Storage
from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.utils.access_control import has_access
from bcgpt.utils.misc import calculate_sha256_string

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers — app state access
# ---------------------------------------------------------------------------


def _cfg(request: Request):
    """Shorthand for the app-level config object."""
    return request.app.state.config


def _embedding_fn(request: Request):
    """Return the current embedding function or None."""
    return getattr(request.app.state, "EMBEDDING_FUNCTION", None)


# ---------------------------------------------------------------------------
# Helpers — embedding / reranking model loaders
# ---------------------------------------------------------------------------


def get_ef(
    engine: str,
    embedding_model: str,
    auto_update: bool = False,
    uri: str = "",
):
    """Load a local SentenceTransformer embedding model (engine == "")."""
    if uri or not embedding_model or engine != "":
        return None
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(
            get_model_path(embedding_model, auto_update),
            device=DEVICE_TYPE,
            trust_remote_code=RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,
        )
    except Exception as exc:
        log.error("Failed to load SentenceTransformer embedding model: %s", exc)
        return None


def get_rf(
    reranking_model: str,
    auto_update: bool = False,
    uri: str = "",
    api_key: str = "",
):
    """Load a reranking model — either external API, ColBERT, or CrossEncoder."""
    if not reranking_model:
        return None

    if uri:
        return ExternalReranker(uri, api_key, reranking_model)

    if "jinaai/jina-colbert-v2" in reranking_model:
        from bcgpt.retrieval import ColBERT

        try:
            return ColBERT(
                get_model_path(reranking_model, auto_update),
                env="docker" if DOCKER else None,
            )
        except Exception as exc:
            log.error("ColBERT: %s", exc)
            raise Exception(ERROR_MESSAGES.DEFAULT(exc)) from exc

    import sentence_transformers

    try:
        return sentence_transformers.CrossEncoder(
            get_model_path(reranking_model, auto_update),
            device=DEVICE_TYPE,
            trust_remote_code=RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,
        )
    except Exception as exc:
        log.error("CrossEncoder error: %s", exc)
        raise Exception(ERROR_MESSAGES.DEFAULT("CrossEncoder error")) from exc


def is_embedding_ready(request: Request) -> bool:
    """True if the configured embedding function can produce vectors.

    Covers all backends: local SentenceTransformer, legacy direct URI, the old
    explicit engine+endpoint, and model-id routing through a configured
    connection. In every case ``_rebuild_embedding_function`` leaves
    ``EMBEDDING_FUNCTION`` set iff the backend is usable, so that alone is the
    source of truth — the ``ef`` attribute is only populated for the local
    SentenceTransformer path.
    """
    return _embedding_fn(request) is not None


# ---------------------------------------------------------------------------
# Helpers — embedding function (re)initialization
# ---------------------------------------------------------------------------


def _resolve_embedding_endpoint(request: Request, model_id: str):
    """Resolve a model id to the ``(engine, url, key)`` of the connection that
    serves it.

    The embedding model is selected from the models exposed by the configured
    Connections (OpenAI/Ollama). This maps that model id back to the connection
    that owns it, so embeddings can be called without a separate "embedding
    connection" setup. Returns the ``(engine, url, key)`` tuple, or ``None``
    when the model isn't served by any connection (→ fall back to a local
    SentenceTransformer).
    """
    model_id = (model_id or "").strip()
    if not model_id:
        return None

    cfg = _cfg(request)

    # 1) OpenAI-compatible connections — each model carries its urlIdx.
    openai_models = getattr(request.app.state, "OPENAI_MODELS", {}) or {}
    entry = openai_models.get(model_id)
    if entry:
        url_idx = entry.get("urlIdx", 0)
        urls = cfg.OPENAI_API_BASE_URLS or []
        keys = cfg.OPENAI_API_KEYS or []
        if 0 <= url_idx < len(urls):
            key = keys[url_idx] if url_idx < len(keys) else ""
            return ("openai", urls[url_idx], key)

    # 2) Ollama connections — each model lists the instance indices serving it.
    ollama_models = getattr(request.app.state, "OLLAMA_MODELS", {}) or {}
    entry = ollama_models.get(model_id)
    if entry:
        idxs = entry.get("urls") or []
        url_idx = idxs[0] if idxs else 0
        urls = cfg.OLLAMA_BASE_URLS or []
        if 0 <= url_idx < len(urls):
            url = urls[url_idx]
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            configs = cfg.OLLAMA_API_CONFIGS or {}
            cfg_entry = configs.get(str(url_idx), configs.get(base, {})) or {}
            return ("ollama", url, cfg_entry.get("key", ""))

    return None


def _rebuild_embedding_function(request: Request) -> None:
    """Rebuild request.app.state.EMBEDDING_FUNCTION from current config.

    Resolution order:
      1. Legacy direct URI override (``RAG_EMBEDDING_MODEL_URI``).
      2. Route the selected model id through the connection that serves it.
      3. Legacy explicit engine + RAG-specific endpoint (old Embedding
         Connection UI) — kept so previously saved configs keep working.
      4. Local SentenceTransformer fallback.
    """
    cfg = _cfg(request)

    # 1) Legacy direct URI override.
    if getattr(cfg, "RAG_EMBEDDING_MODEL_URI", ""):
        request.app.state.ef = None
        request.app.state.EMBEDDING_FUNCTION = get_embedding_function(
            "openai",
            cfg.RAG_EMBEDDING_MODEL,
            None,
            cfg.RAG_EMBEDDING_MODEL_URI,
            cfg.RAG_EMBEDDING_MODEL_API_KEY,
            cfg.RAG_EMBEDDING_BATCH_SIZE,
        )
        return

    model_id = cfg.RAG_EMBEDDING_MODEL

    # 2) Route via the connection that owns the selected model.
    endpoint = _resolve_embedding_endpoint(request, model_id)
    if endpoint is not None:
        engine, url, key = endpoint
        request.app.state.ef = None
        request.app.state.EMBEDDING_FUNCTION = get_embedding_function(
            engine,
            model_id,
            None,
            url,
            key,
            cfg.RAG_EMBEDDING_BATCH_SIZE,
        )
        return

    # 3) Legacy explicit engine + RAG-specific endpoint.
    engine = (cfg.RAG_EMBEDDING_ENGINE or "").strip()
    if engine in ("openai", "ollama"):
        if engine == "openai":
            url = cfg.RAG_OPENAI_API_BASE_URL
            key = cfg.RAG_OPENAI_API_KEY
        else:
            url = cfg.RAG_OLLAMA_BASE_URL
            key = cfg.RAG_OLLAMA_API_KEY
        if url:
            request.app.state.ef = None
            request.app.state.EMBEDDING_FUNCTION = get_embedding_function(
                engine,
                model_id,
                None,
                url,
                key,
                cfg.RAG_EMBEDDING_BATCH_SIZE,
            )
            return

    # 4) Local SentenceTransformer fallback.
    ef = get_ef("", model_id)
    request.app.state.ef = ef

    if ef is None:
        log.warning(
            "Embedding model '%s' is not served by any configured connection "
            "and could not be loaded locally. Vector DB features will be "
            "unavailable until a valid embedding model is selected.",
            model_id,
        )
        request.app.state.EMBEDDING_FUNCTION = None
        return

    request.app.state.EMBEDDING_FUNCTION = get_embedding_function(
        "",
        model_id,
        ef,
        "",
        "",
        cfg.RAG_EMBEDDING_BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# Helpers — config serialization
# ---------------------------------------------------------------------------


def _serialize_embedding_config(request: Request) -> dict:
    cfg = _cfg(request)
    return {
        "status": True,
        "embedding_engine": cfg.RAG_EMBEDDING_ENGINE,
        "embedding_model": cfg.RAG_EMBEDDING_MODEL,
        "embedding_batch_size": cfg.RAG_EMBEDDING_BATCH_SIZE,
        "openai_config": {
            "url": cfg.RAG_OPENAI_API_BASE_URL,
            "key": cfg.RAG_OPENAI_API_KEY,
        },
        "ollama_config": {
            "url": cfg.RAG_OLLAMA_BASE_URL,
            "key": cfg.RAG_OLLAMA_API_KEY,
        },
    }


def _serialize_rag_config(request: Request) -> dict:
    cfg = _cfg(request)
    return {
        "status": True,
        "pdf_extract_images": cfg.PDF_EXTRACT_IMAGES,
        "RAG_FULL_CONTEXT": cfg.RAG_FULL_CONTEXT,
        "BYPASS_EMBEDDING_AND_RETRIEVAL": cfg.BYPASS_EMBEDDING_AND_RETRIEVAL,
        "enable_google_drive_integration": cfg.ENABLE_GOOGLE_DRIVE_INTEGRATION,
        "enable_onedrive_integration": cfg.ENABLE_ONEDRIVE_INTEGRATION,
        "qdrant_url": cfg.QDRANT_URL,
        "qdrant_api_key": cfg.QDRANT_API_KEY,
        "embedding_model": cfg.RAG_EMBEDDING_MODEL,
        "cleansing_enabled": cfg.CLEANSING_ENABLED,
        "cleansing_model": cfg.CLEANSING_MODEL,
        "summary_enabled": cfg.SUMMARY_ENABLED,
        "summary_model": cfg.SUMMARY_MODEL,
        "content_extraction": {
            "engine": cfg.CONTENT_EXTRACTION_ENGINE,
            "tika_server_url": cfg.TIKA_SERVER_URL,
            "docling_server_url": cfg.DOCLING_SERVER_URL,
            "document_intelligence_config": {
                "endpoint": cfg.DOCUMENT_INTELLIGENCE_ENDPOINT,
                "key": cfg.DOCUMENT_INTELLIGENCE_KEY,
            },
        },
        "chunk": {
            "text_splitter": cfg.TEXT_SPLITTER,
            "chunk_size": cfg.CHUNK_SIZE,
            "chunk_overlap": cfg.CHUNK_OVERLAP,
        },
        "file": {
            "max_size": cfg.FILE_MAX_SIZE,
            "max_count": cfg.FILE_MAX_COUNT,
        },
        "youtube": {
            "language": cfg.YOUTUBE_LOADER_LANGUAGE,
            "translation": request.app.state.YOUTUBE_LOADER_TRANSLATION,
            "proxy_url": cfg.YOUTUBE_LOADER_PROXY_URL,
        },
        "web": _serialize_web_config(cfg, request.app.state),
    }


def _serialize_web_config(cfg, app_state) -> dict:
    return {
        "ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION": cfg.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
        "BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL": cfg.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL,
        "search": {
            "enabled": cfg.ENABLE_RAG_WEB_SEARCH,
            "drive": cfg.ENABLE_GOOGLE_DRIVE_INTEGRATION,
            "onedrive": cfg.ENABLE_ONEDRIVE_INTEGRATION,
            "engine": cfg.RAG_WEB_SEARCH_ENGINE,
            "searxng_query_url": cfg.SEARXNG_QUERY_URL,
            "google_pse_api_key": cfg.GOOGLE_PSE_API_KEY,
            "google_pse_engine_id": cfg.GOOGLE_PSE_ENGINE_ID,
            "brave_search_api_key": cfg.BRAVE_SEARCH_API_KEY,
            "naver_client_id": cfg.NAVER_CLIENT_ID,
            "naver_client_secret": cfg.NAVER_CLIENT_SECRET,
            "naver_search_endpoints": cfg.NAVER_SEARCH_ENDPOINTS,
            "kagi_search_api_key": cfg.KAGI_SEARCH_API_KEY,
            "mojeek_search_api_key": cfg.MOJEEK_SEARCH_API_KEY,
            "bocha_search_api_key": cfg.BOCHA_SEARCH_API_KEY,
            "serpstack_api_key": cfg.SERPSTACK_API_KEY,
            "serpstack_https": cfg.SERPSTACK_HTTPS,
            "serper_api_key": cfg.SERPER_API_KEY,
            "serply_api_key": cfg.SERPLY_API_KEY,
            "tavily_api_key": cfg.TAVILY_API_KEY,
            "searchapi_api_key": cfg.SEARCHAPI_API_KEY,
            "searchapi_engine": cfg.SEARCHAPI_ENGINE,
            "serpapi_api_key": cfg.SERPAPI_API_KEY,
            "serpapi_engine": cfg.SERPAPI_ENGINE,
            "jina_api_key": cfg.JINA_API_KEY,
            "bing_search_v7_endpoint": cfg.BING_SEARCH_V7_ENDPOINT,
            "bing_search_v7_subscription_key": cfg.BING_SEARCH_V7_SUBSCRIPTION_KEY,
            "exa_api_key": cfg.EXA_API_KEY,
            "perplexity_api_key": cfg.PERPLEXITY_API_KEY,
            "result_count": cfg.RAG_WEB_SEARCH_RESULT_COUNT,
            "trust_env": cfg.RAG_WEB_SEARCH_TRUST_ENV,
            "concurrent_requests": cfg.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
            "query_rewrite_enabled": cfg.RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED,
            "query_rewrite_model": cfg.RAG_WEB_SEARCH_QUERY_REWRITE_MODEL,
            "concurrent_queries": cfg.RAG_WEB_SEARCH_CONCURRENT_QUERIES,
            "domain_filter_list": cfg.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
        },
    }


def _serialize_advanced_config(cfg) -> dict:
    return {
        "status": True,
        "contextual_retrieval": {
            "enabled": cfg.RAG_CONTEXTUAL_RETRIEVAL_ENABLED,
            "model": cfg.RAG_CONTEXTUAL_RETRIEVAL_MODEL,
            "max_context_tokens": cfg.RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS,
            "batch_size": cfg.RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE,
        },
        "cross_encoder": {
            "enabled": cfg.RAG_CROSS_ENCODER_RERANKING_ENABLED,
            "model": cfg.RAG_CROSS_ENCODER_MODEL,
            "max_length": cfg.RAG_CROSS_ENCODER_MAX_LENGTH,
            "top_k": cfg.RAG_CROSS_ENCODER_TOP_K,
        },
        "graph": {
            "enabled": cfg.RAG_GRAPH_ENABLED,
            "entity_extraction_model": cfg.RAG_GRAPH_ENTITY_EXTRACTION_MODEL,
            "max_entities": cfg.RAG_GRAPH_MAX_ENTITIES,
            "max_relations": cfg.RAG_GRAPH_MAX_RELATIONS,
            "community_detection_enabled": cfg.RAG_GRAPH_COMMUNITY_DETECTION_ENABLED,
            "max_hops": cfg.RAG_GRAPH_MAX_HOPS,
        },
        "evaluation": {
            "enabled": cfg.RAG_EVALUATION_ENABLED,
            "model": cfg.RAG_EVALUATION_MODEL,
            "metrics": cfg.RAG_EVALUATION_METRICS,
            "log_results": cfg.RAG_EVALUATION_LOG_RESULTS,
        },
    }


# ---------------------------------------------------------------------------
# Helpers — config deserialization (web search)
# ---------------------------------------------------------------------------


def _apply_web_search_config(cfg, web_cfg: "WebSearchConfig") -> None:
    """Apply web search config fields to the app config object."""
    cfg.ENABLE_RAG_WEB_SEARCH = web_cfg.enabled
    cfg.RAG_WEB_SEARCH_ENGINE = web_cfg.engine
    cfg.SEARXNG_QUERY_URL = web_cfg.searxng_query_url
    cfg.GOOGLE_PSE_API_KEY = web_cfg.google_pse_api_key
    cfg.GOOGLE_PSE_ENGINE_ID = web_cfg.google_pse_engine_id
    cfg.BRAVE_SEARCH_API_KEY = web_cfg.brave_search_api_key
    cfg.NAVER_CLIENT_ID = web_cfg.naver_client_id
    cfg.NAVER_CLIENT_SECRET = web_cfg.naver_client_secret
    cfg.NAVER_SEARCH_ENDPOINTS = web_cfg.naver_search_endpoints
    cfg.KAGI_SEARCH_API_KEY = web_cfg.kagi_search_api_key
    cfg.MOJEEK_SEARCH_API_KEY = web_cfg.mojeek_search_api_key
    cfg.BOCHA_SEARCH_API_KEY = web_cfg.bocha_search_api_key
    cfg.SERPSTACK_API_KEY = web_cfg.serpstack_api_key
    cfg.SERPSTACK_HTTPS = web_cfg.serpstack_https
    cfg.SERPER_API_KEY = web_cfg.serper_api_key
    cfg.SERPLY_API_KEY = web_cfg.serply_api_key
    cfg.TAVILY_API_KEY = web_cfg.tavily_api_key
    cfg.SEARCHAPI_API_KEY = web_cfg.searchapi_api_key
    cfg.SEARCHAPI_ENGINE = web_cfg.searchapi_engine
    cfg.SERPAPI_API_KEY = web_cfg.serpapi_api_key
    cfg.SERPAPI_ENGINE = web_cfg.serpapi_engine
    cfg.JINA_API_KEY = web_cfg.jina_api_key
    cfg.BING_SEARCH_V7_ENDPOINT = web_cfg.bing_search_v7_endpoint
    cfg.BING_SEARCH_V7_SUBSCRIPTION_KEY = web_cfg.bing_search_v7_subscription_key
    cfg.EXA_API_KEY = web_cfg.exa_api_key
    cfg.PERPLEXITY_API_KEY = web_cfg.perplexity_api_key
    cfg.RAG_WEB_SEARCH_RESULT_COUNT = web_cfg.result_count
    cfg.RAG_WEB_SEARCH_CONCURRENT_REQUESTS = web_cfg.concurrent_requests
    cfg.RAG_WEB_SEARCH_TRUST_ENV = web_cfg.trust_env
    cfg.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST = web_cfg.domain_filter_list
    cfg.RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED = web_cfg.query_rewrite_enabled
    cfg.RAG_WEB_SEARCH_QUERY_REWRITE_MODEL = web_cfg.query_rewrite_model
    cfg.RAG_WEB_SEARCH_CONCURRENT_QUERIES = web_cfg.concurrent_queries


# ---------------------------------------------------------------------------
# Helpers — metadata sanitization
# ---------------------------------------------------------------------------


def _sanitize_metadata(metadata: dict) -> dict:
    """Convert datetime/list/dict values to strings for vector DB compatibility."""
    for key, value in metadata.items():
        if isinstance(value, (datetime, list, dict)):
            metadata[key] = str(value)
    return metadata


# ---------------------------------------------------------------------------
# Helpers — collection ownership checks
# ---------------------------------------------------------------------------


def _check_collection_access(collection_name: str, user) -> None:
    """Raise 403 if the user cannot access the given collection.

    Thin alias for the canonical ``check_collection_access`` in
    ``bcgpt.retrieval.lifecycle`` (imported above); retained so existing call
    sites in this router read naturally. New code should call the lifecycle
    helper directly.
    """
    return check_collection_access(collection_name, user)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CollectionNameForm(BaseModel):
    collection_name: Optional[str] = None


class ProcessUrlForm(CollectionNameForm):
    url: str


class SearchForm(CollectionNameForm):
    query: str


class CreateCollectionForm(BaseModel):
    name: str


class CollectionSearchForm(BaseModel):
    query: str
    limit: Optional[int] = 20


class OpenAIConfigForm(BaseModel):
    url: str
    key: str


class OllamaConfigForm(BaseModel):
    url: str
    key: str


class EmbeddingModelUpdateForm(BaseModel):
    openai_config: Optional[OpenAIConfigForm] = None
    ollama_config: Optional[OllamaConfigForm] = None
    embedding_engine: str
    embedding_model: str
    embedding_batch_size: Optional[int] = 1


class RerankingModelUpdateForm(BaseModel):
    reranking_model: str


class FileConfig(BaseModel):
    max_size: Optional[int] = None
    max_count: Optional[int] = None


class DocumentIntelligenceConfigForm(BaseModel):
    endpoint: str
    key: str


class ContentExtractionConfig(BaseModel):
    engine: str = ""
    tika_server_url: Optional[str] = None
    docling_server_url: Optional[str] = None
    document_intelligence_config: Optional[DocumentIntelligenceConfigForm] = None


class ChunkParamUpdateForm(BaseModel):
    text_splitter: Optional[str] = None
    chunk_size: int
    chunk_overlap: int


class YoutubeLoaderConfig(BaseModel):
    language: list[str]
    translation: Optional[str] = None
    proxy_url: str = ""


class WebSearchConfig(BaseModel):
    enabled: bool
    engine: Optional[str] = None
    searxng_query_url: Optional[str] = None
    google_pse_api_key: Optional[str] = None
    google_pse_engine_id: Optional[str] = None
    brave_search_api_key: Optional[str] = None
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None
    naver_search_endpoints: Optional[str] = None
    kagi_search_api_key: Optional[str] = None
    mojeek_search_api_key: Optional[str] = None
    bocha_search_api_key: Optional[str] = None
    serpstack_api_key: Optional[str] = None
    serpstack_https: Optional[bool] = None
    serper_api_key: Optional[str] = None
    serply_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    searchapi_api_key: Optional[str] = None
    searchapi_engine: Optional[str] = None
    serpapi_api_key: Optional[str] = None
    serpapi_engine: Optional[str] = None
    jina_api_key: Optional[str] = None
    bing_search_v7_endpoint: Optional[str] = None
    bing_search_v7_subscription_key: Optional[str] = None
    exa_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    result_count: Optional[int] = None
    concurrent_requests: Optional[int] = None
    trust_env: Optional[bool] = None
    query_rewrite_enabled: Optional[bool] = None
    query_rewrite_model: Optional[str] = None
    concurrent_queries: Optional[bool] = None
    domain_filter_list: Optional[List[str]] = []


class WebConfig(BaseModel):
    search: WebSearchConfig
    ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION: Optional[bool] = None
    BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL: Optional[bool] = None


class ConfigUpdateForm(BaseModel):
    RAG_FULL_CONTEXT: Optional[bool] = None
    BYPASS_EMBEDDING_AND_RETRIEVAL: Optional[bool] = None
    pdf_extract_images: Optional[bool] = None
    enable_google_drive_integration: Optional[bool] = None
    enable_onedrive_integration: Optional[bool] = None
    file: Optional[FileConfig] = None
    content_extraction: Optional[ContentExtractionConfig] = None
    chunk: Optional[ChunkParamUpdateForm] = None
    youtube: Optional[YoutubeLoaderConfig] = None
    web: Optional[WebConfig] = None
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    embedding_model: Optional[str] = None
    cleansing_enabled: Optional[bool] = None
    cleansing_model: Optional[str] = None
    summary_enabled: Optional[bool] = None
    summary_model: Optional[str] = None


class AdvancedRAGContextualRetrievalForm(BaseModel):
    enabled: bool
    model: str
    max_context_tokens: int
    batch_size: int


class AdvancedRAGCrossEncoderForm(BaseModel):
    enabled: bool
    model: str
    max_length: int
    top_k: int


class AdvancedRAGGraphForm(BaseModel):
    enabled: bool
    entity_extraction_model: str
    max_entities: int
    max_relations: int
    community_detection_enabled: bool
    max_hops: int


class AdvancedRAGEvaluationForm(BaseModel):
    enabled: bool
    model: str
    metrics: str
    log_results: bool


class AdvancedRAGConfigForm(BaseModel):
    contextual_retrieval: AdvancedRAGContextualRetrievalForm
    cross_encoder: AdvancedRAGCrossEncoderForm
    graph: AdvancedRAGGraphForm
    evaluation: AdvancedRAGEvaluationForm


class QuerySettingsForm(BaseModel):
    k: Optional[int] = None
    k_reranker: Optional[int] = None
    r: Optional[float] = None
    template: Optional[str] = None
    hybrid: Optional[bool] = None


class ProcessFileForm(BaseModel):
    file_id: str
    content: Optional[str] = None
    collection_name: Optional[str] = None


class ProcessTextForm(BaseModel):
    name: str
    content: str
    collection_name: Optional[str] = None


class QueryDocForm(BaseModel):
    collection_name: str
    query: str
    k: Optional[int] = None
    k_reranker: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


class QueryCollectionsForm(BaseModel):
    collection_names: list[str]
    query: str
    k: Optional[int] = None
    k_reranker: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


class DeleteForm(BaseModel):
    collection_name: str
    file_id: str


class BatchProcessFilesForm(BaseModel):
    files: List[FileModel]
    collection_name: str


class BatchProcessFilesResult(BaseModel):
    file_id: str
    status: str
    error: Optional[str] = None


class BatchProcessFilesResponse(BaseModel):
    results: List[BatchProcessFilesResult]
    errors: List[BatchProcessFilesResult]


# ===========================================================================
#
#  ROUTES — Status & Vector DB Collections
#
# ===========================================================================


@router.get("/")
async def get_status(request: Request):
    cfg = _cfg(request)
    return {
        "status": True,
        "chunk_size": cfg.CHUNK_SIZE,
        "chunk_overlap": cfg.CHUNK_OVERLAP,
        "template": cfg.RAG_TEMPLATE,
        "embedding_engine": cfg.RAG_EMBEDDING_ENGINE,
        "embedding_model": cfg.RAG_EMBEDDING_MODEL,
        "reranking_model": cfg.RAG_RERANKING_MODEL,
        "embedding_batch_size": cfg.RAG_EMBEDDING_BATCH_SIZE,
    }


@router.get("/db/status")
async def get_vector_db_status(request: Request, user=Depends(get_admin_user)):
    from bcgpt.retrieval.vector.main import VectorDBStatus

    cfg = _cfg(request)
    embedding_engine = cfg.RAG_EMBEDDING_ENGINE
    embedding_model = cfg.RAG_EMBEDDING_MODEL
    total_vectors = 0
    cluster_status = None

    try:
        collections = await asyncio.to_thread(VECTOR_DB_CLIENT.list_collections)

        if hasattr(VECTOR_DB_CLIENT, "get_db_stats"):
            stats = await asyncio.to_thread(VECTOR_DB_CLIENT.get_db_stats)
            total_vectors = stats.get("total_vectors", 0)
            cluster_status = stats.get("cluster_status")

        return VectorDBStatus(
            backend=VECTOR_DB,
            connected=True,
            collections=collections,
            embedding_engine=embedding_engine,
            embedding_model=embedding_model,
            total_vectors=total_vectors,
            cluster_status=cluster_status,
            embedding_loaded=is_embedding_ready(request),
        )
    except Exception as exc:
        log.error("Vector DB status check failed: %s", exc)
        return VectorDBStatus(
            backend=VECTOR_DB if "VECTOR_DB" in dir() else "unknown",
            connected=False,
            collections=[],
            embedding_engine=embedding_engine,
            embedding_model=embedding_model,
            embedding_loaded=is_embedding_ready(request),
        )


@router.get("/db/collections")
async def get_vector_db_collections(user=Depends(get_admin_user)):
    return await asyncio.to_thread(VECTOR_DB_CLIENT.list_collections)


@router.delete("/db/collections/{collection_name}")
async def delete_vector_db_collection(
    collection_name: str, user=Depends(get_admin_user)
):
    try:
        exists = await asyncio.to_thread(
            VECTOR_DB_CLIENT.has_collection, collection_name=collection_name
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Collection not found")

        await asyncio.to_thread(
            VECTOR_DB_CLIENT.delete_collection, collection_name=collection_name
        )
        return {"status": True}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to delete collection '%s': %s", collection_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


class ConsolidateCorpusForm(BaseModel):
    """Payload for the corpus-consolidation admin migration (P1.5)."""

    dry_run: bool = False
    page_size: int = 200


@router.post("/db/consolidate")
async def consolidate_vector_db_corpus(
    request: Request,
    form_data: ConsolidateCorpusForm,
    user=Depends(get_admin_user),
):
    """Admin: migrate legacy per-file/KB collections into the shared corpus.

    Vector-preserving copy (no re-embedding). Same-dimension collections are
    folded into the corpus (one per embedding-model config); dim-mismatched
    ones are left in place as dual-read targets. Safe to re-run (idempotent —
    point ids are preserved). Set ``dry_run`` to preview without writing.
    """
    from bcgpt.retrieval.migrations.consolidate_corpus import consolidate_corpus

    try:
        return await asyncio.to_thread(
            lambda: consolidate_corpus(
                request,
                dry_run=form_data.dry_run,
                page_size=form_data.page_size,
            )
        )
    except Exception as exc:
        log.exception("consolidate_corpus failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/db/collections")
async def create_vector_db_collection(
    request: Request,
    form_data: CreateCollectionForm,
    user=Depends(get_admin_user),
):
    collection_name = form_data.name.strip()
    if not collection_name:
        raise HTTPException(status_code=400, detail="Collection name is required")

    exists = await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=collection_name
    )
    if exists:
        raise HTTPException(
            status_code=409, detail=f"Collection '{collection_name}' already exists"
        )

    if not is_embedding_ready(request):
        raise HTTPException(
            status_code=503,
            detail="Embedding model is not available — it may have failed to load. "
            "Check the embedding model configuration in Admin Settings > Documents.",
        )

    embedding_function = _embedding_fn(request)

    # Probe dimension
    try:
        embeddings = await asyncio.to_thread(
            embedding_function,
            "dimension_probe",
            prefix=RAG_EMBEDDING_QUERY_PREFIX,
            user=user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "Embedding probe failed for collection '%s': %s", collection_name, exc
        )
        raise HTTPException(
            status_code=503,
            detail="Embedding model failed to produce an embedding — "
            "check the embedding model configuration in Admin Settings > Documents.",
        )

    if not embeddings:
        raise HTTPException(
            status_code=422,
            detail="Failed to generate embedding for dimension detection. "
            "Check embedding model configuration.",
        )

    dimension = len(embeddings)

    try:
        if hasattr(VECTOR_DB_CLIENT, "_create_collection"):
            await asyncio.to_thread(
                VECTOR_DB_CLIENT._create_collection,
                collection_name=collection_name,
                dimension=dimension,
            )
        else:
            dummy_item = {
                "id": "__create_probe__",
                "text": "",
                "vector": [0.0] * dimension,
                "metadata": {"__probe__": True},
            }
            await asyncio.to_thread(
                VECTOR_DB_CLIENT.insert,
                collection_name=collection_name,
                items=[dummy_item],
            )
            await asyncio.to_thread(
                VECTOR_DB_CLIENT.delete,
                collection_name=collection_name,
                filter={"id": "__create_probe__"},
            )

        log.info(
            "Created empty collection '%s' with dimension %d",
            collection_name,
            dimension,
        )
        return {"status": True, "name": collection_name, "dimension": dimension}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to create collection '%s': %s", collection_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/db/collections/{collection_name}/info")
async def get_vector_db_collection_info(
    collection_name: str, user=Depends(get_admin_user)
):
    name = collection_name.strip()
    exists = await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=name
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Collection not found")

    info = None
    if hasattr(VECTOR_DB_CLIENT, "get_collection_info"):
        try:
            info = await asyncio.to_thread(VECTOR_DB_CLIENT.get_collection_info, name)
        except Exception as exc:
            log.warning("get_collection_info failed for '%s': %s", name, exc)

    if info is None:
        info = {
            "points_count": None,
            "dimension": None,
            "distance": None,
            "status": None,
        }

    return {"name": name, **info}


@router.get("/db/collections/{collection_name}/points")
async def list_vector_db_collection_points(
    collection_name: str,
    limit: int = 50,
    offset: Optional[str] = None,
    user=Depends(get_admin_user),
):
    name = collection_name.strip()
    limit = max(1, min(limit, 500))

    exists = await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=name
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Native cursor pagination (Qdrant scroll)
    if hasattr(VECTOR_DB_CLIENT, "list_points"):
        result = await asyncio.to_thread(
            VECTOR_DB_CLIENT.list_points, name, limit, offset
        )
        result = result or {"points": [], "next_offset": None}
        return {**result, "limit": limit}

    # Generic fallback: fetch all, slice by integer offset
    try:
        start = int(offset) if offset else 0
    except (TypeError, ValueError):
        start = 0

    get_result = await asyncio.to_thread(VECTOR_DB_CLIENT.get, name)
    ids = (get_result.ids[0] if get_result and get_result.ids else []) or []
    documents = (
        get_result.documents[0] if get_result and get_result.documents else []
    ) or []
    metadatas = (
        get_result.metadatas[0] if get_result and get_result.metadatas else []
    ) or []

    end = start + limit
    points = [
        {
            "id": str(ids[i]),
            "text": documents[i] if i < len(documents) else "",
            "metadata": metadatas[i] if i < len(metadatas) else {},
        }
        for i in range(start, min(end, len(ids)))
    ]
    next_offset = str(end) if end < len(ids) else None
    return {"points": points, "next_offset": next_offset, "limit": limit}


@router.post("/db/collections/{collection_name}/search")
async def search_vector_db_collection(
    request: Request,
    collection_name: str,
    form_data: CollectionSearchForm,
    user=Depends(get_admin_user),
):
    name = collection_name.strip()
    exists = await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=name
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Collection not found")

    query = (form_data.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query is required")

    embedding_function = _embedding_fn(request)
    if embedding_function is None:
        raise HTTPException(
            status_code=500,
            detail="Embedding model is not configured. Check embedding model configuration.",
        )

    limit = max(1, min(form_data.limit or 20, 100))

    try:
        config = _cfg(request)
        return await search_with_advanced_pipeline(
            request=request,
            query=query,
            collection_names=[name],
            user=user,
            k=limit,
            enable_hyde=getattr(config, "RAG_HYDE_ENABLED", False),
            enable_expansion=getattr(config, "RAG_QUERY_EXPANSION_ENABLED", False),
            enable_step_back=getattr(config, "RAG_STEP_BACK_ENABLED", False),
        )
    except Exception as exc:
        log.exception("Search failed for collection '%s': %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/db/collections/{collection_name}/points/{point_id}")
async def delete_vector_db_collection_point(
    collection_name: str, point_id: str, user=Depends(get_admin_user)
):
    name = collection_name.strip()
    exists = await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=name
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Collection not found")

    if not hasattr(VECTOR_DB_CLIENT, "delete_points"):
        raise HTTPException(
            status_code=501,
            detail="Point deletion is not supported for this vector DB backend.",
        )

    try:
        await asyncio.to_thread(VECTOR_DB_CLIENT.delete_points, name, [point_id])
    except Exception as exc:
        log.error("Failed to delete point '%s' from '%s': %s", point_id, name, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": True}


# ===========================================================================
#
#  ROUTES — Embedding & Reranking Configuration
#
# ===========================================================================


@router.get("/embedding")
async def get_embedding_config(request: Request, user=Depends(get_admin_user)):
    return _serialize_embedding_config(request)


@router.get("/reranking")
async def get_reraanking_config(request: Request, user=Depends(get_admin_user)):
    return {
        "status": True,
        "reranking_model": _cfg(request).RAG_RERANKING_MODEL,
    }


@router.post("/embedding/update")
async def update_embedding_config(
    request: Request, form_data: EmbeddingModelUpdateForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)
    log.info(
        "Updating embedding model: %s to %s",
        cfg.RAG_EMBEDDING_MODEL,
        form_data.embedding_model,
    )
    try:
        cfg.RAG_EMBEDDING_ENGINE = form_data.embedding_engine
        cfg.RAG_EMBEDDING_MODEL = form_data.embedding_model

        if cfg.RAG_EMBEDDING_ENGINE in ("ollama", "openai"):
            if form_data.openai_config is not None:
                cfg.RAG_OPENAI_API_BASE_URL = form_data.openai_config.url
                cfg.RAG_OPENAI_API_KEY = form_data.openai_config.key
            if form_data.ollama_config is not None:
                cfg.RAG_OLLAMA_BASE_URL = form_data.ollama_config.url
                cfg.RAG_OLLAMA_API_KEY = form_data.ollama_config.key
            cfg.RAG_EMBEDDING_BATCH_SIZE = form_data.embedding_batch_size

        _rebuild_embedding_function(request)
        return _serialize_embedding_config(request)
    except Exception as exc:
        log.exception("Problem updating embedding model: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.post("/reranking/update")
async def update_reranking_config(
    request: Request, form_data: RerankingModelUpdateForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)
    log.info(
        "Updating reranking model: %s to %s",
        cfg.RAG_RERANKING_MODEL,
        form_data.reranking_model,
    )
    try:
        cfg.RAG_RERANKING_MODEL = form_data.reranking_model

        try:
            reranking_uri = cfg.RAG_RERANKING_MODEL_URI
            reranking_api_key = cfg.RAG_RERANKING_MODEL_API_KEY
            request.app.state.rf = get_rf(
                cfg.RAG_RERANKING_MODEL,
                True,
                uri=reranking_uri,
                api_key=reranking_api_key,
            )
        except Exception as exc:
            log.error("Error loading reranking model: %s", exc)
            cfg.ENABLE_RAG_HYBRID_SEARCH = False

        return {
            "status": True,
            "reranking_model": cfg.RAG_RERANKING_MODEL,
        }
    except Exception as exc:
        log.exception("Problem updating reranking model: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


# ===========================================================================
#
#  ROUTES — RAG Configuration
#
# ===========================================================================


@router.get("/config")
async def get_rag_config(request: Request, user=Depends(get_admin_user)):
    return _serialize_rag_config(request)


@router.post("/config/update")
async def update_rag_config(
    request: Request, form_data: ConfigUpdateForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)

    # Simple boolean / scalar fields
    _set_if_not_none(cfg, "PDF_EXTRACT_IMAGES", form_data.pdf_extract_images)
    _set_if_not_none(cfg, "RAG_FULL_CONTEXT", form_data.RAG_FULL_CONTEXT)
    _set_if_not_none(
        cfg, "BYPASS_EMBEDDING_AND_RETRIEVAL", form_data.BYPASS_EMBEDDING_AND_RETRIEVAL
    )
    _set_if_not_none(
        cfg,
        "ENABLE_GOOGLE_DRIVE_INTEGRATION",
        form_data.enable_google_drive_integration,
    )
    _set_if_not_none(
        cfg, "ENABLE_ONEDRIVE_INTEGRATION", form_data.enable_onedrive_integration
    )
    _set_if_not_none(cfg, "CLEANSING_ENABLED", form_data.cleansing_enabled)
    _set_if_not_none(cfg, "CLEANSING_MODEL", form_data.cleansing_model)
    _set_if_not_none(cfg, "SUMMARY_ENABLED", form_data.summary_enabled)
    _set_if_not_none(cfg, "SUMMARY_MODEL", form_data.summary_model)

    # File config
    if form_data.file is not None:
        cfg.FILE_MAX_SIZE = form_data.file.max_size
        cfg.FILE_MAX_COUNT = form_data.file.max_count

    # Content extraction
    if form_data.content_extraction is not None:
        log.info(
            "Updating content extraction: %s to %s",
            cfg.CONTENT_EXTRACTION_ENGINE,
            form_data.content_extraction.engine,
        )
        cfg.CONTENT_EXTRACTION_ENGINE = form_data.content_extraction.engine
        cfg.TIKA_SERVER_URL = form_data.content_extraction.tika_server_url
        cfg.DOCLING_SERVER_URL = form_data.content_extraction.docling_server_url
        if form_data.content_extraction.document_intelligence_config is not None:
            cfg.DOCUMENT_INTELLIGENCE_ENDPOINT = (
                form_data.content_extraction.document_intelligence_config.endpoint
            )
            cfg.DOCUMENT_INTELLIGENCE_KEY = (
                form_data.content_extraction.document_intelligence_config.key
            )

    # Chunk config
    if form_data.chunk is not None:
        cfg.TEXT_SPLITTER = form_data.chunk.text_splitter
        cfg.CHUNK_SIZE = form_data.chunk.chunk_size
        cfg.CHUNK_OVERLAP = form_data.chunk.chunk_overlap

    # Qdrant reconnection
    qdrant_changed = False
    if form_data.qdrant_url is not None:
        cfg.QDRANT_URL = form_data.qdrant_url
        qdrant_changed = True
    if form_data.qdrant_api_key is not None:
        cfg.QDRANT_API_KEY = form_data.qdrant_api_key
        qdrant_changed = True
    if qdrant_changed and hasattr(VECTOR_DB_CLIENT, "reinitialize"):
        VECTOR_DB_CLIENT.reinitialize()

    # Embedding model reinit
    if form_data.embedding_model is not None:
        cfg.RAG_EMBEDDING_MODEL = form_data.embedding_model
        try:
            _rebuild_embedding_function(request)
            if request.app.state.EMBEDDING_FUNCTION is not None:
                log.info(
                    "Embedding function reinitialized for model: %s",
                    cfg.RAG_EMBEDDING_MODEL,
                )
        except Exception as exc:
            log.error("Failed to reinitialize embedding function: %s", exc)
            request.app.state.EMBEDDING_FUNCTION = None

    # YouTube loader
    if form_data.youtube is not None:
        cfg.YOUTUBE_LOADER_LANGUAGE = form_data.youtube.language
        cfg.YOUTUBE_LOADER_PROXY_URL = form_data.youtube.proxy_url
        request.app.state.YOUTUBE_LOADER_TRANSLATION = form_data.youtube.translation

    # Web config
    if form_data.web is not None:
        cfg.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = (
            form_data.web.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION
        )
        cfg.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL = (
            form_data.web.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL
        )
        _apply_web_search_config(cfg, form_data.web.search)

    return _serialize_rag_config(request)


def _set_if_not_none(obj, attr: str, value) -> None:
    """Set obj.attr = value only if value is not None."""
    if value is not None:
        setattr(obj, attr, value)


# ===========================================================================
#
#  ROUTES — Advanced RAG Configuration
#
# ===========================================================================


@router.get("/advanced/config")
async def get_advanced_rag_config(request: Request, user=Depends(get_admin_user)):
    return _serialize_advanced_config(_cfg(request))


@router.post("/advanced/config/update")
async def update_advanced_rag_config(
    request: Request, form_data: AdvancedRAGConfigForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)

    cfg.RAG_CONTEXTUAL_RETRIEVAL_ENABLED = form_data.contextual_retrieval.enabled
    cfg.RAG_CONTEXTUAL_RETRIEVAL_MODEL = form_data.contextual_retrieval.model
    cfg.RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS = (
        form_data.contextual_retrieval.max_context_tokens
    )
    cfg.RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE = form_data.contextual_retrieval.batch_size

    cfg.RAG_CROSS_ENCODER_RERANKING_ENABLED = form_data.cross_encoder.enabled
    cfg.RAG_CROSS_ENCODER_MODEL = form_data.cross_encoder.model
    cfg.RAG_CROSS_ENCODER_MAX_LENGTH = form_data.cross_encoder.max_length
    cfg.RAG_CROSS_ENCODER_TOP_K = form_data.cross_encoder.top_k

    cfg.RAG_GRAPH_ENABLED = form_data.graph.enabled
    cfg.RAG_GRAPH_ENTITY_EXTRACTION_MODEL = form_data.graph.entity_extraction_model
    cfg.RAG_GRAPH_MAX_ENTITIES = form_data.graph.max_entities
    cfg.RAG_GRAPH_MAX_RELATIONS = form_data.graph.max_relations
    cfg.RAG_GRAPH_COMMUNITY_DETECTION_ENABLED = (
        form_data.graph.community_detection_enabled
    )
    cfg.RAG_GRAPH_MAX_HOPS = form_data.graph.max_hops

    cfg.RAG_EVALUATION_ENABLED = form_data.evaluation.enabled
    cfg.RAG_EVALUATION_MODEL = form_data.evaluation.model
    cfg.RAG_EVALUATION_METRICS = form_data.evaluation.metrics
    cfg.RAG_EVALUATION_LOG_RESULTS = form_data.evaluation.log_results

    return _serialize_advanced_config(cfg)


# ===========================================================================
#
#  ROUTES — Query Settings & Template
#
# ===========================================================================


@router.get("/template")
async def get_rag_template(request: Request, user=Depends(get_verified_user)):
    return {
        "status": True,
        "template": _cfg(request).RAG_TEMPLATE,
    }


@router.get("/query/settings")
async def get_query_settings(request: Request, user=Depends(get_admin_user)):
    cfg = _cfg(request)
    return {
        "status": True,
        "template": cfg.RAG_TEMPLATE,
        "k": cfg.TOP_K,
        "k_reranker": cfg.TOP_K_RERANKER,
        "r": cfg.RELEVANCE_THRESHOLD,
        "hybrid": cfg.ENABLE_RAG_HYBRID_SEARCH,
    }


@router.post("/query/settings/update")
async def update_query_settings(
    request: Request, form_data: QuerySettingsForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)
    cfg.RAG_TEMPLATE = form_data.template
    cfg.TOP_K = form_data.k if form_data.k else 4
    cfg.TOP_K_RERANKER = form_data.k_reranker or 4
    cfg.RELEVANCE_THRESHOLD = form_data.r if form_data.r else 0.0
    cfg.ENABLE_RAG_HYBRID_SEARCH = form_data.hybrid if form_data.hybrid else False

    return {
        "status": True,
        "template": cfg.RAG_TEMPLATE,
        "k": cfg.TOP_K,
        "k_reranker": cfg.TOP_K_RERANKER,
        "r": cfg.RELEVANCE_THRESHOLD,
        "hybrid": cfg.ENABLE_RAG_HYBRID_SEARCH,
    }


# ===========================================================================
#
#  DOCUMENT PROCESSING — save_docs_to_vector_db
#
# ===========================================================================


def save_docs_to_vector_db(
    request: Request,
    docs,
    collection_name,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    split: bool = True,
    add: bool = False,
    user=None,
) -> bool:
    """Split documents, embed, and persist to the vector DB."""
    log.info(
        "save_docs_to_vector_db: document %s %s",
        _docs_info(docs),
        collection_name,
    )

    # Deduplicate by hash
    if metadata and "hash" in metadata:
        result = VECTOR_DB_CLIENT.query(
            collection_name=collection_name,
            filter={"hash": metadata["hash"]},
        )
        if result is not None:
            existing_doc_ids = result.ids[0]
            if existing_doc_ids:
                log.info("Document with hash %s already exists", metadata["hash"])
                raise ValueError(ERROR_MESSAGES.DUPLICATE_CONTENT)

    # Split documents
    if split:
        docs = _split_docs(request, docs)

    if not docs:
        log.info("save_docs_to_vector_db: no documents to save after splitting")
        return False

    cfg = _cfg(request)

    # Parent-child chunking
    parent_child_enabled = (
        split
        and hasattr(cfg, "RAG_PARENT_CHILD_ENABLED")
        and cfg.RAG_PARENT_CHILD_ENABLED
    )

    if parent_child_enabled:
        from bcgpt.retrieval.parent_child import create_parent_child_chunks

        parent_size = getattr(cfg, "RAG_PARENT_CHILD_PARENT_SIZE", 2000)
        child_size = getattr(cfg, "RAG_PARENT_CHILD_CHILD_SIZE", 200)

        parent_chunks, child_chunks = create_parent_child_chunks(
            docs,
            parent_chunk_size=parent_size,
            parent_chunk_overlap=200,
            child_chunk_size=child_size,
            child_chunk_overlap=20,
        )

        texts = [c["text"] for c in child_chunks]
        metadatas = [
            _sanitize_metadata(
                {
                    **c["metadata"],
                    **(metadata if metadata else {}),
                    "embedding_config": json.dumps(
                        {
                            "engine": cfg.RAG_EMBEDDING_ENGINE,
                            "model": cfg.RAG_EMBEDDING_MODEL,
                        }
                    ),
                }
            )
            for c in child_chunks
        ]
    else:
        texts = [doc.page_content for doc in docs]
        metadatas = [
            _sanitize_metadata(
                {
                    **doc.metadata,
                    **(metadata if metadata else {}),
                    "embedding_config": json.dumps(
                        {
                            "engine": cfg.RAG_EMBEDDING_ENGINE,
                            "model": cfg.RAG_EMBEDDING_MODEL,
                        }
                    ),
                }
            )
            for doc in docs
        ]

    # Ingestion-time chunk-quality filter (GIGO mitigation, 2.6). Drops 'reject'
    # chunks (too short / repetitive / low-information); 'review' is kept.
    if getattr(cfg, "RAG_CHUNK_QUALITY_ENABLED", False) and texts:
        from bcgpt.retrieval.chunk_quality import filter_chunks

        _before = len(texts)
        _fc = filter_chunks(texts, metadatas)
        if _fc["accepted_texts"]:
            if _fc["rejected"]:
                log.info(
                    "Chunk-quality filter dropped %d/%d low-quality chunks",
                    len(_fc["rejected"]),
                    _before,
                )
            texts = _fc["accepted_texts"]
            metadatas = _fc["accepted_metadatas"]
        else:
            log.warning(
                "Chunk-quality filter would reject all %d chunks; "
                "keeping them (fail-open)",
                _before,
            )

    try:
        if VECTOR_DB_CLIENT.has_collection(collection_name=collection_name):
            log.info("collection %s already exists", collection_name)
            if overwrite:
                VECTOR_DB_CLIENT.delete_collection(collection_name=collection_name)
                log.info("deleting existing collection %s", collection_name)
            elif not add:
                log.info(
                    "collection %s already exists, overwrite=False and add=False",
                    collection_name,
                )
                return True

        log.info("adding to collection %s", collection_name)
        embedding_function = _embedding_fn(request)
        if embedding_function is None:
            raise ValueError(
                "Embedding model is not configured. Select an embedding model "
                "in Admin Settings → Documents."
            )

        embeddings = embedding_function(
            [t.replace("\n", " ") for t in texts],
            prefix=RAG_EMBEDDING_CONTENT_PREFIX,
            user=user,
        )

        # Late chunking (local engine only)
        if (
            split
            and getattr(cfg, "RAG_LATE_CHUNKING_ENABLED", False)
            and cfg.RAG_EMBEDDING_ENGINE == ""
            and request.app.state.ef is not None
        ):
            embeddings = _apply_late_chunking(
                request, docs, texts, embeddings, embedding_function, user
            )

        items = [
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "vector": embeddings[idx],
                "metadata": metadatas[idx],
            }
            for idx, text in enumerate(texts)
        ]

        # P1.4: when writing to a corpus collection, ensure it exists with the
        # payload indexes (filtered ANN) before insert. The corpus naming
        # convention is the trigger — only corpus-mode callers pass such a name.
        if collection_name and collection_name.startswith("corpus_") and items:
            _ensure = getattr(VECTOR_DB_CLIENT, "ensure_corpus_collection", None)
            if _ensure is not None:
                try:
                    _ensure(
                        collection_name=collection_name,
                        dimension=len(items[0]["vector"]),
                    )
                except Exception as exc:
                    log.debug("ensure_corpus_collection failed: %s", exc)

        VECTOR_DB_CLIENT.insert(collection_name=collection_name, items=items)

        # GraphRAG: build/persist a co-occurrence knowledge graph from the
        # ingested chunks (deterministic, no-LLM; opt-in via RAG_GRAPH_ENABLED).
        # Sync + thread-safe so it is safe from every save_docs call site. 3.1
        if getattr(request.app.state.config, "RAG_GRAPH_ENABLED", False) and texts:
            try:
                from bcgpt.retrieval.graph.graph_builder import (
                    build_graph_from_chunks,
                )

                _doc_id = (metadata or {}).get("file_id") or collection_name
                _chunk_ids = [it["id"] for it in items]
                _cap = (
                    int(
                        getattr(request.app.state.config, "RAG_GRAPH_MAX_ENTITIES", 0)
                        or 0
                    )
                    or None
                )
                _min_docs = int(
                    getattr(request.app.state.config, "RAG_GRAPH_MIN_ENTITY_DOCS", 1)
                    or 0
                )
                _nodes = build_graph_from_chunks(
                    _doc_id,
                    _chunk_ids,
                    texts,
                    max_entities_per_chunk=_cap,
                    min_entity_docs=_min_docs,
                )
                log.info("GraphRAG: knowledge graph now has %d nodes", _nodes)
            except Exception as exc:
                log.warning("GraphRAG build failed (non-fatal): %s", exc)

        # Parent-child docstore
        if parent_child_enabled:
            _save_parent_chunks_to_docstore(
                parent_chunks, collection_name, metadata, embeddings
            )

        return True
    except Exception as exc:
        log.exception("save_docs_to_vector_db failed: %s", exc)
        raise


def _docs_info(docs: list[Document]) -> str:
    """Extract identifying names from document metadata."""
    names = set()
    for doc in docs:
        md = getattr(doc, "metadata", {})
        for key in ("name", "title", "source"):
            if md.get(key):
                names.add(md[key])
                break
    return ", ".join(names)


def _split_docs(request: Request, docs: list[Document]) -> list[Document]:
    """Split documents using the configured text splitter."""
    cfg = _cfg(request)
    if cfg.TEXT_SPLITTER in ("", "character"):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.CHUNK_SIZE,
            chunk_overlap=cfg.CHUNK_OVERLAP,
            add_start_index=True,
        )
    elif cfg.TEXT_SPLITTER == "token":
        tiktoken.get_encoding(str(cfg.TIKTOKEN_ENCODING_NAME))
        splitter = TokenTextSplitter(
            encoding_name=str(cfg.TIKTOKEN_ENCODING_NAME),
            chunk_size=cfg.CHUNK_SIZE,
            chunk_overlap=cfg.CHUNK_OVERLAP,
            add_start_index=True,
        )
    else:
        raise ValueError(ERROR_MESSAGES.DEFAULT("Invalid text splitter"))
    return splitter.split_documents(docs)


def _apply_late_chunking(request, docs, texts, embeddings, embedding_function, user):
    """Apply late chunking for context-aware embeddings."""
    try:
        from bcgpt.retrieval.chunking import LateChunker

        late_chunker = LateChunker(request.app.state.ef)

        source_groups: dict[str, list[int]] = {}
        for idx, doc in enumerate(docs):
            source_key = doc.metadata.get("source", f"__doc_{idx}")
            source_groups.setdefault(source_key, []).append(idx)

        embeddings = [None] * len(texts)

        for source_key, chunk_indices in source_groups.items():
            chunk_indices.sort(key=lambda i: docs[i].metadata.get("start_index", 0))
            full_text = "\n".join(docs[i].page_content for i in chunk_indices)

            offset = 0
            adjusted_spans = []
            for i in chunk_indices:
                chunk_len = len(docs[i].page_content)
                adjusted_spans.append((offset, offset + chunk_len))
                offset += chunk_len + 1

            if full_text and adjusted_spans:
                chunk_vecs = late_chunker.embed_with_spans(full_text, adjusted_spans)
                for j, ci in enumerate(chunk_indices):
                    if j < len(chunk_vecs):
                        embeddings[ci] = chunk_vecs[j]

        # Fill in any None with normal embeddings
        normal_embeddings = embedding_function(
            [t.replace("\n", " ") for t in texts],
            prefix=RAG_EMBEDDING_CONTENT_PREFIX,
            user=user,
        )
        for i in range(len(embeddings)):
            if embeddings[i] is None:
                embeddings[i] = normal_embeddings[i]

        log.info(
            "Late chunking produced %d contextual chunk embeddings for %d chunks",
            sum(1 for e in embeddings if e is not None),
            len(texts),
        )
        return embeddings
    except Exception as exc:
        log.warning("Late chunking failed, falling back to normal embeddings: %s", exc)
        return embedding_function(
            [t.replace("\n", " ") for t in texts],
            prefix=RAG_EMBEDDING_CONTENT_PREFIX,
            user=user,
        )


def _save_parent_chunks_to_docstore(
    parent_chunks, collection_name, metadata, embeddings
):
    """Store parent chunks in a separate docstore collection."""
    from bcgpt.retrieval.parent_child import get_docstore_collection_name

    docstore_name = get_docstore_collection_name(collection_name)
    embedding_dim = len(embeddings[0])
    zero_vector = [0.0] * embedding_dim

    if VECTOR_DB_CLIENT.has_collection(collection_name=docstore_name):
        VECTOR_DB_CLIENT.delete_collection(collection_name=docstore_name)

    docstore_items = []
    for pc in parent_chunks:
        parent_meta = _sanitize_metadata(
            {
                **pc["metadata"],
                **(metadata if metadata else {}),
            }
        )
        docstore_items.append(
            {
                "id": pc["id"],
                "text": pc["text"],
                "vector": zero_vector,
                "metadata": parent_meta,
            }
        )

    if docstore_items:
        VECTOR_DB_CLIENT.insert(collection_name=docstore_name, items=docstore_items)
        log.info(
            "Stored %d parent chunks in docstore '%s'",
            len(docstore_items),
            docstore_name,
        )


# ===========================================================================
#
#  ROUTES — Document Processing Endpoints
#
# ===========================================================================


@router.post("/process/file")
def process_file(
    request: Request,
    form_data: ProcessFileForm,
    user=Depends(get_verified_user),
):
    # Authorization check (outside broad try/except so 403/404 is preserved)
    file = Files.get_file_by_id(form_data.file_id)
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    knowledge_base_id = file.meta.get("collection_name") if file.meta else None
    has_kb_access = False
    if knowledge_base_id:
        for kb in Knowledges.get_knowledge_bases_by_user_id(user.id, "read"):
            if kb.id == knowledge_base_id:
                has_kb_access = True
                break
    if not (file.user_id == user.id or user.role == "admin" or has_kb_access):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        # P1.4: under RAG_USE_CORPUS, route ingest to the shared corpus
        # collection (one per embedding-model config) instead of a per-file /
        # per-KB collection. KB scoping is preserved by the knowledge_id chunk
        # metadata (P1.1); the corpus collection + payload indexes are ensured
        # on insert in save_docs_to_vector_db.
        if bool(
            getattr(_cfg(request).RAG_USE_CORPUS, "value", _cfg(request).RAG_USE_CORPUS)
        ):
            from bcgpt.retrieval.vector.corpus import corpus_collection_name

            collection_name = corpus_collection_name(
                engine=_cfg(request).RAG_EMBEDDING_ENGINE,
                model=_cfg(request).RAG_EMBEDDING_MODEL,
            )
        else:
            collection_name = form_data.collection_name
            if collection_name is None:
                collection_name = f"file-{file.id}"

        if form_data.content:
            # Content update path — clear this file's prior vectors.
            if collection_name and collection_name.startswith("corpus_"):
                try:
                    VECTOR_DB_CLIENT.delete(
                        collection_name=collection_name,
                        filter={"file_id": file.id},
                    )
                except Exception:
                    pass
            else:
                try:
                    VECTOR_DB_CLIENT.delete_collection(
                        collection_name=f"file-{file.id}"
                    )
                except Exception:
                    pass

            docs = [
                Document(
                    page_content=form_data.content.replace("<br/>", "\n"),
                    metadata={
                        **file.meta,
                        "name": file.filename,
                        "created_by": file.user_id,
                        "file_id": file.id,
                        "source": file.filename,
                    },
                )
            ]
            text_content = form_data.content

        elif form_data.collection_name:
            # Re-process for knowledge base
            result = VECTOR_DB_CLIENT.query(
                collection_name=f"file-{file.id}", filter={"file_id": file.id}
            )
            if result is not None and len(result.ids[0]) > 0:
                docs = [
                    Document(
                        page_content=result.documents[0][idx],
                        metadata=result.metadatas[0][idx],
                    )
                    for idx in range(len(result.ids[0]))
                ]
            else:
                docs = [
                    Document(
                        page_content=file.data.get("content", ""),
                        metadata={
                            **file.meta,
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                ]
            text_content = file.data.get("content", "")

        else:
            # Initial file processing
            file_path = file.path
            if file_path:
                file_path = Storage.get_file(file_path)
                cfg = _cfg(request)
                loader = Loader(
                    engine=cfg.CONTENT_EXTRACTION_ENGINE,
                    TIKA_SERVER_URL=cfg.TIKA_SERVER_URL,
                    DOCLING_SERVER_URL=cfg.DOCLING_SERVER_URL,
                    PDF_EXTRACT_IMAGES=cfg.PDF_EXTRACT_IMAGES,
                    DOCUMENT_INTELLIGENCE_ENDPOINT=cfg.DOCUMENT_INTELLIGENCE_ENDPOINT,
                    DOCUMENT_INTELLIGENCE_KEY=cfg.DOCUMENT_INTELLIGENCE_KEY,
                    RAG_COLUMN_PROFILER_ENABLED=getattr(
                        cfg, "RAG_COLUMN_PROFILER_ENABLED", False
                    ),
                )
                docs = loader.load(
                    file.filename, file.meta.get("content_type"), file_path
                )
                docs = [
                    Document(
                        page_content=doc.page_content,
                        metadata={
                            **doc.metadata,
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                    for doc in docs
                ]
            else:
                docs = [
                    Document(
                        page_content=file.data.get("content", ""),
                        metadata={
                            **file.meta,
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                ]
            text_content = " ".join(doc.page_content for doc in docs)

        log.debug("text_content: %s", text_content)
        Files.update_file_data_by_id(file.id, {"content": text_content})

        hash = calculate_sha256_string(text_content)
        Files.update_file_hash_by_id(file.id, hash)

        if not _cfg(request).BYPASS_EMBEDDING_AND_RETRIEVAL:
            result = save_docs_to_vector_db(
                request,
                docs=docs,
                collection_name=collection_name,
                metadata={
                    "file_id": file.id,
                    "name": file.filename,
                    "hash": hash,
                    # P1.1: self-describing chunk metadata for corpus filtering.
                    # knowledge_id is the KB uuid when adding to a KB, else None
                    # (standalone upload). workspace_id is the forward-compatible
                    # partition key (no-op "default" until real tenancy).
                    "knowledge_id": form_data.collection_name,
                    "workspace_id": DEFAULT_WORKSPACE_ID,
                },
                add=(True if form_data.collection_name else False),
                user=user,
            )
            if result:
                Files.update_file_metadata_by_id(
                    file.id, {"collection_name": collection_name}
                )
                return {
                    "status": True,
                    "collection_name": collection_name,
                    "filename": file.filename,
                    "content": text_content,
                }
        else:
            return {
                "status": True,
                "collection_name": None,
                "filename": file.filename,
                "content": text_content,
            }

    except Exception as exc:
        log.exception("process_file failed: %s", exc)
        if "No pandoc was found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.PANDOC_NOT_INSTALLED,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post("/process/text")
def process_text(
    request: Request,
    form_data: ProcessTextForm,
    user=Depends(get_verified_user),
):
    collection_name = form_data.collection_name or calculate_sha256_string(
        form_data.content
    )

    docs = [
        Document(
            page_content=form_data.content,
            metadata={"name": form_data.name, "created_by": user.id},
        )
    ]
    text_content = form_data.content
    log.debug("text_content: %s", text_content)

    result = save_docs_to_vector_db(request, docs, collection_name, user=user)
    if result:
        return {
            "status": True,
            "collection_name": collection_name,
            "content": text_content,
        }
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ERROR_MESSAGES.DEFAULT(),
    )


@router.post("/process/youtube")
def process_youtube_video(
    request: Request, form_data: ProcessUrlForm, user=Depends(get_verified_user)
):
    try:
        collection_name = (
            form_data.collection_name or calculate_sha256_string(form_data.url)[:63]
        )
        cfg = _cfg(request)

        loader = YoutubeLoader(
            form_data.url,
            language=cfg.YOUTUBE_LOADER_LANGUAGE,
            proxy_url=cfg.YOUTUBE_LOADER_PROXY_URL,
        )
        docs = loader.load()
        content = " ".join(doc.page_content for doc in docs)
        log.debug("text_content: %s", content)

        save_docs_to_vector_db(
            request, docs, collection_name, overwrite=True, user=user
        )

        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
            "file": {
                "data": {"content": content},
                "meta": {"name": form_data.url},
            },
        }
    except Exception as exc:
        log.exception("process_youtube_video failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.post("/process/web")
def process_web(
    request: Request, form_data: ProcessUrlForm, user=Depends(get_verified_user)
):
    try:
        collection_name = (
            form_data.collection_name or calculate_sha256_string(form_data.url)[:63]
        )
        cfg = _cfg(request)

        loader = get_web_loader(
            form_data.url,
            verify_ssl=cfg.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            requests_per_second=cfg.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
        )
        docs = loader.load()
        content = " ".join(doc.page_content for doc in docs)
        log.debug("text_content: %s", content)

        if not cfg.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL:
            save_docs_to_vector_db(
                request, docs, collection_name, overwrite=True, user=user
            )
        else:
            collection_name = None

        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
            "file": {
                "data": {"content": content},
                "meta": {"name": form_data.url, "source": form_data.url},
            },
        }
    except Exception as exc:
        log.exception("process_web failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


# ===========================================================================
#
#  WEB SEARCH — engine dispatch
#
# ===========================================================================


def search_web(request: Request, engine: str, query: str) -> list[SearchResult]:
    """Dispatch web search to the configured engine."""
    cfg = _cfg(request)
    count = cfg.RAG_WEB_SEARCH_RESULT_COUNT
    domain_filter = cfg.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST

    engine_dispatch = {
        "searxng": lambda: (
            search_searxng(cfg.SEARXNG_QUERY_URL, query, count, domain_filter)
            if cfg.SEARXNG_QUERY_URL
            else _no_key("SEARXNG_QUERY_URL")
        ),
        "naver": lambda: (
            search_naver(
                cfg.NAVER_CLIENT_ID,
                cfg.NAVER_CLIENT_SECRET,
                query,
                count,
                domain_filter,
                cfg.NAVER_SEARCH_ENDPOINTS,
            )
            if (cfg.NAVER_CLIENT_ID and cfg.NAVER_CLIENT_SECRET)
            else _no_key("NAVER_CLIENT_ID/SECRET")
        ),
        "google_pse": lambda: (
            search_google_pse(
                cfg.GOOGLE_PSE_API_KEY,
                cfg.GOOGLE_PSE_ENGINE_ID,
                query,
                count,
                domain_filter,
            )
            if (cfg.GOOGLE_PSE_API_KEY and cfg.GOOGLE_PSE_ENGINE_ID)
            else _no_key("GOOGLE_PSE")
        ),
        "brave": lambda: (
            search_brave(cfg.BRAVE_SEARCH_API_KEY, query, count, domain_filter)
            if cfg.BRAVE_SEARCH_API_KEY
            else _no_key("BRAVE_SEARCH_API_KEY")
        ),
        "kagi": lambda: (
            search_kagi(cfg.KAGI_SEARCH_API_KEY, query, count, domain_filter)
            if cfg.KAGI_SEARCH_API_KEY
            else _no_key("KAGI_SEARCH_API_KEY")
        ),
        "mojeek": lambda: (
            search_mojeek(cfg.MOJEEK_SEARCH_API_KEY, query, count, domain_filter)
            if cfg.MOJEEK_SEARCH_API_KEY
            else _no_key("MOJEEK_SEARCH_API_KEY")
        ),
        "bocha": lambda: (
            search_bocha(cfg.BOCHA_SEARCH_API_KEY, query, count, domain_filter)
            if cfg.BOCHA_SEARCH_API_KEY
            else _no_key("BOCHA_SEARCH_API_KEY")
        ),
        "serpstack": lambda: (
            search_serpstack(
                cfg.SERPSTACK_API_KEY,
                query,
                count,
                domain_filter,
                https_enabled=cfg.SERPSTACK_HTTPS,
            )
            if cfg.SERPSTACK_API_KEY
            else _no_key("SERPSTACK_API_KEY")
        ),
        "serper": lambda: (
            search_serper(cfg.SERPER_API_KEY, query, count, domain_filter)
            if cfg.SERPER_API_KEY
            else _no_key("SERPER_API_KEY")
        ),
        "serply": lambda: (
            search_serply(cfg.SERPLY_API_KEY, query, count, domain_filter)
            if cfg.SERPLY_API_KEY
            else _no_key("SERPLY_API_KEY")
        ),
        "duckduckgo": lambda: search_duckduckgo(query, count, domain_filter),
        "tavily": lambda: (
            search_tavily(cfg.TAVILY_API_KEY, query, count, domain_filter)
            if cfg.TAVILY_API_KEY
            else _no_key("TAVILY_API_KEY")
        ),
        "searchapi": lambda: (
            search_searchapi(
                cfg.SEARCHAPI_API_KEY,
                cfg.SEARCHAPI_ENGINE,
                query,
                count,
                domain_filter,
            )
            if cfg.SEARCHAPI_API_KEY
            else _no_key("SEARCHAPI_API_KEY")
        ),
        "serpapi": lambda: (
            search_serpapi(
                cfg.SERPAPI_API_KEY,
                cfg.SERPAPI_ENGINE,
                query,
                count,
                domain_filter,
            )
            if cfg.SERPAPI_API_KEY
            else _no_key("SERPAPI_API_KEY")
        ),
        "jina": lambda: search_jina(cfg.JINA_API_KEY, query, count),
        "bing": lambda: search_bing(
            cfg.BING_SEARCH_V7_SUBSCRIPTION_KEY,
            cfg.BING_SEARCH_V7_ENDPOINT,
            str(DEFAULT_LOCALE),
            query,
            count,
            domain_filter,
        ),
        "exa": lambda: search_exa(cfg.EXA_API_KEY, query, count, domain_filter),
        "perplexity": lambda: search_perplexity(
            cfg.PERPLEXITY_API_KEY, query, count, domain_filter
        ),
    }

    handler = engine_dispatch.get(engine)
    if handler:
        return handler()
    raise Exception("No search engine API key found in environment variables")


def _no_key(name: str):
    raise Exception(f"No {name} found in environment variables")


@router.post("/process/web/search")
async def process_web_search(
    request: Request, form_data: SearchForm, user=Depends(get_verified_user)
):
    cfg = _cfg(request)
    engine = cfg.RAG_WEB_SEARCH_ENGINE
    query = form_data.query

    try:
        log.info("Web search: engine=%s query=%r", engine, query)
        web_results = search_web(request, engine, query)
    except Exception as exc:
        reason = str(exc) or exc.__class__.__name__
        log.warning(
            "Web search failed for engine=%s query=%r: %s", engine, query, reason
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.WEB_SEARCH_ERROR(reason),
        )

    if not web_results:
        reason = f"No web search results found for query: {query}"
        log.warning(
            "Web search returned no results for engine=%s query=%r", engine, query
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.WEB_SEARCH_ERROR(reason),
        )

    try:
        collection_name = form_data.collection_name
        if not collection_name:
            collection_name = f"web-search-{calculate_sha256_string(query)}"[:63]

        urls = [result.link for result in web_results]
        loader = get_web_loader(
            urls,
            verify_ssl=cfg.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            requests_per_second=cfg.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
            trust_env=cfg.RAG_WEB_SEARCH_TRUST_ENV,
        )
        docs = await loader.aload()

        if not any((doc.page_content or "").strip() for doc in docs):
            reason = "Web search returned URLs, but no page content could be loaded"
            log.warning(
                "Web search content loading failed for query=%r urls=%s", query, urls
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(reason),
            )

        if cfg.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL:
            return {
                "status": True,
                "collection_name": None,
                "filenames": urls,
                "docs": [
                    {"content": doc.page_content, "metadata": doc.metadata}
                    for doc in docs
                ],
                "loaded_count": len(docs),
            }

        saved = await run_in_threadpool(
            save_docs_to_vector_db,
            request,
            docs,
            collection_name,
            overwrite=True,
            user=user,
        )
        if saved is False:
            reason = "Web search content was empty after processing"
            log.warning(
                "Web search vector save skipped for query=%r collection=%s",
                query,
                collection_name,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(reason),
            )

        return {
            "status": True,
            "collection_name": collection_name,
            "filenames": urls,
            "loaded_count": len(docs),
        }
    except HTTPException:
        raise
    except Exception as exc:
        reason = str(exc) or exc.__class__.__name__
        log.warning(
            "Web search content processing failed for query=%r: %s", query, reason
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(reason),
        )


# ===========================================================================
#
#  ROUTES — Query Endpoints
#
# ===========================================================================


@router.post("/query/doc")
def query_doc_handler(
    request: Request,
    form_data: QueryDocForm,
    user=Depends(get_verified_user),
):
    _check_collection_access(form_data.collection_name, user)

    try:
        cfg = _cfg(request)
        if cfg.ENABLE_RAG_HYBRID_SEARCH:
            return query_doc_with_hybrid_search(
                collection_name=form_data.collection_name,
                query=form_data.query,
                embedding_function=lambda q, prefix: request.app.state.EMBEDDING_FUNCTION(
                    q, prefix=prefix, user=user
                ),
                k=form_data.k or cfg.TOP_K,
                reranking_function=request.app.state.rf,
                k_reranker=form_data.k_reranker or cfg.TOP_K_RERANKER,
                r=form_data.r if form_data.r else cfg.RELEVANCE_THRESHOLD,
                user=user,
            )
        else:
            return query_doc(
                collection_name=form_data.collection_name,
                query_embedding=request.app.state.EMBEDDING_FUNCTION(
                    form_data.query, prefix=RAG_EMBEDDING_QUERY_PREFIX, user=user
                ),
                k=form_data.k or cfg.TOP_K,
                user=user,
            )
    except Exception as exc:
        log.exception("query_doc failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.post("/query/collection")
def query_collection_handler(
    request: Request,
    form_data: QueryCollectionsForm,
    user=Depends(get_verified_user),
):
    for cn in form_data.collection_names:
        _check_collection_access(cn, user)

    try:
        cfg = _cfg(request)
        if cfg.ENABLE_RAG_HYBRID_SEARCH:
            return query_collection_with_hybrid_search(
                collection_names=form_data.collection_names,
                queries=[form_data.query],
                embedding_function=lambda q, prefix: request.app.state.EMBEDDING_FUNCTION(
                    q, prefix=prefix, user=user
                ),
                k=form_data.k or cfg.TOP_K,
                reranking_function=request.app.state.rf,
                k_reranker=form_data.k_reranker or cfg.TOP_K_RERANKER,
                r=form_data.r if form_data.r else cfg.RELEVANCE_THRESHOLD,
            )
        else:
            return query_collection(
                collection_names=form_data.collection_names,
                queries=[form_data.query],
                embedding_function=lambda q, prefix: request.app.state.EMBEDDING_FUNCTION(
                    q, prefix=prefix, user=user
                ),
                k=form_data.k or cfg.TOP_K,
            )
    except Exception as exc:
        log.exception("query_collection failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


# ===========================================================================
#
#  ROUTES — Vector DB Operations
#
# ===========================================================================


@router.post("/delete")
async def delete_entries_from_collection(
    form_data: DeleteForm, user=Depends(get_admin_user)
):
    try:
        exists = await asyncio.to_thread(
            VECTOR_DB_CLIENT.has_collection, collection_name=form_data.collection_name
        )
        if exists:
            file = await asyncio.to_thread(Files.get_file_by_id, form_data.file_id)
            await asyncio.to_thread(
                VECTOR_DB_CLIENT.delete,
                collection_name=form_data.collection_name,
                metadata={"hash": file.hash},
            )
            return {"status": True}
        return {"status": False}
    except Exception as exc:
        log.exception("delete_entries_from_collection failed: %s", exc)
        return {"status": False}


@router.post("/reset/db")
async def reset_vector_db(user=Depends(get_admin_user)):
    await asyncio.to_thread(VECTOR_DB_CLIENT.reset)
    await asyncio.to_thread(Knowledges.delete_all_knowledge)


@router.post("/reset/uploads")
async def reset_upload_dir(user=Depends(get_admin_user)) -> bool:
    folder = f"{UPLOAD_DIR}"
    try:
        await asyncio.to_thread(_cleanup_upload_dir, folder)
    except Exception as exc:
        log.exception("Failed to process the directory %s. Reason: %s", folder, exc)
    return True


def _cleanup_upload_dir(folder: str) -> None:
    """Sync helper for resetting upload directory."""
    if not os.path.exists(folder):
        log.warning("The directory %s does not exist", folder)
        return
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as exc:
            log.exception("Failed to delete %s. Reason: %s", file_path, exc)


# ===========================================================================
#
#  DEV ROUTES
#
# ===========================================================================

if ENV == "dev":

    @router.get("/ef/{text}")
    async def get_embeddings(request: Request, text: Optional[str] = "Hello World!"):
        return {
            "result": request.app.state.EMBEDDING_FUNCTION(
                text, prefix=RAG_EMBEDDING_QUERY_PREFIX
            )
        }


# ===========================================================================
#
#  BATCH PROCESSING
#
# ===========================================================================


@router.post("/process/files/batch")
def process_files_batch(
    request: Request,
    form_data: BatchProcessFilesForm,
    user=Depends(get_verified_user),
) -> BatchProcessFilesResponse:
    """Process a batch of files and save them to the vector database."""
    results: List[BatchProcessFilesResult] = []
    errors: List[BatchProcessFilesResult] = []
    collection_name = form_data.collection_name

    all_docs: List[Document] = []
    for file in form_data.files:
        try:
            if not (file.user_id == user.id or user.role == "admin"):
                errors.append(
                    BatchProcessFilesResult(
                        file_id=file.id, status="skipped", error="Access denied"
                    )
                )
                continue

            text_content = file.data.get("content", "")
            docs = [
                Document(
                    page_content=text_content.replace("<br/>", "\n"),
                    metadata={
                        **file.meta,
                        "name": file.filename,
                        "created_by": file.user_id,
                        "file_id": file.id,
                        "source": file.filename,
                    },
                )
            ]

            hash = calculate_sha256_string(text_content)
            Files.update_file_hash_by_id(file.id, hash)
            Files.update_file_data_by_id(file.id, {"content": text_content})

            all_docs.extend(docs)
            results.append(BatchProcessFilesResult(file_id=file.id, status="prepared"))

        except Exception as exc:
            log.error("process_files_batch: Error processing file %s: %s", file.id, exc)
            errors.append(
                BatchProcessFilesResult(
                    file_id=file.id, status="failed", error=str(exc)
                )
            )

    if all_docs:
        try:
            save_docs_to_vector_db(
                request=request,
                docs=all_docs,
                collection_name=collection_name,
                add=True,
                user=user,
            )
            for result in results:
                Files.update_file_metadata_by_id(
                    result.file_id, {"collection_name": collection_name}
                )
                result.status = "completed"
        except Exception as exc:
            log.error(
                "process_files_batch: Error saving documents to vector DB: %s", exc
            )
            for result in results:
                result.status = "failed"
                errors.append(
                    BatchProcessFilesResult(file_id=result.file_id, error=str(exc))
                )

    return BatchProcessFilesResponse(results=results, errors=errors)
