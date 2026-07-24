"""Configuration management router for bcgpt.

Handles import/export of full config and CRUD for individual config sections:
direct connections, models, prompt suggestions, and banners.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from bcgpt.config import BannerModel, get_config, save_config
from bcgpt.utils import get_admin_user, get_verified_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class ImportConfigForm(BaseModel):
    config: dict


class DirectConnectionsConfigForm(BaseModel):
    ENABLE_DIRECT_CONNECTIONS: bool


class ModelsConfigForm(BaseModel):
    DEFAULT_MODELS: Optional[str] = None
    MODEL_ORDER_LIST: Optional[list[str]] = None


class PromptSuggestion(BaseModel):
    title: list[str]
    content: str


class SetDefaultSuggestionsForm(BaseModel):
    suggestions: list[PromptSuggestion]


class SetBannersForm(BaseModel):
    banners: list[BannerModel]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app_config(request: Request):
    """Return the runtime application config object from app state."""
    return request.app.state.config


# ---------------------------------------------------------------------------
# Full Config Import / Export
# ---------------------------------------------------------------------------


@router.post("/import", response_model=dict)
async def import_config(
    form_data: ImportConfigForm,
    user=Depends(get_admin_user),
):
    """Replace the entire configuration with the provided dict."""
    save_config(form_data.config)
    return get_config()


@router.get("/export", response_model=dict)
async def export_config(user=Depends(get_admin_user)):
    """Return the full configuration as a dict."""
    return get_config()


# ---------------------------------------------------------------------------
# Direct Connections
# ---------------------------------------------------------------------------


@router.get("/direct_connections", response_model=DirectConnectionsConfigForm)
async def get_direct_connections_config(
    request: Request,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    return {"ENABLE_DIRECT_CONNECTIONS": cfg.ENABLE_DIRECT_CONNECTIONS}


@router.post("/direct_connections", response_model=DirectConnectionsConfigForm)
async def set_direct_connections_config(
    request: Request,
    form_data: DirectConnectionsConfigForm,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    cfg.ENABLE_DIRECT_CONNECTIONS = form_data.ENABLE_DIRECT_CONNECTIONS
    return {"ENABLE_DIRECT_CONNECTIONS": cfg.ENABLE_DIRECT_CONNECTIONS}


# ---------------------------------------------------------------------------
# MCP Servers
# ---------------------------------------------------------------------------


class McpServersConfigForm(BaseModel):
    ENABLE_MCP_SERVERS: bool
    MCP_SERVERS: list[dict]
    MCP_ALLOWED_HOSTS: list[str]
    MCP_BUILTINS_ENABLED: list[str]


@router.get("/mcp_servers", response_model=McpServersConfigForm)
async def get_mcp_servers_config(
    request: Request,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    return {
        "ENABLE_MCP_SERVERS": cfg.ENABLE_MCP_SERVERS,
        "MCP_SERVERS": cfg.MCP_SERVERS,
        "MCP_ALLOWED_HOSTS": cfg.MCP_ALLOWED_HOSTS,
        "MCP_BUILTINS_ENABLED": cfg.MCP_BUILTINS_ENABLED,
    }


@router.post("/mcp_servers", response_model=McpServersConfigForm)
async def set_mcp_servers_config(
    request: Request,
    form_data: McpServersConfigForm,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    cfg.ENABLE_MCP_SERVERS = form_data.ENABLE_MCP_SERVERS
    cfg.MCP_SERVERS = form_data.MCP_SERVERS
    cfg.MCP_ALLOWED_HOSTS = form_data.MCP_ALLOWED_HOSTS
    cfg.MCP_BUILTINS_ENABLED = form_data.MCP_BUILTINS_ENABLED
    return {
        "ENABLE_MCP_SERVERS": cfg.ENABLE_MCP_SERVERS,
        "MCP_SERVERS": cfg.MCP_SERVERS,
        "MCP_ALLOWED_HOSTS": cfg.MCP_ALLOWED_HOSTS,
        "MCP_BUILTINS_ENABLED": cfg.MCP_BUILTINS_ENABLED,
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@router.get("/models", response_model=ModelsConfigForm)
async def get_models_config(
    request: Request,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    return {
        "DEFAULT_MODELS": cfg.DEFAULT_MODELS,
        "MODEL_ORDER_LIST": cfg.MODEL_ORDER_LIST,
    }


@router.post("/models", response_model=ModelsConfigForm)
async def set_models_config(
    request: Request,
    form_data: ModelsConfigForm,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    cfg.DEFAULT_MODELS = form_data.DEFAULT_MODELS
    cfg.MODEL_ORDER_LIST = form_data.MODEL_ORDER_LIST
    return {
        "DEFAULT_MODELS": cfg.DEFAULT_MODELS,
        "MODEL_ORDER_LIST": cfg.MODEL_ORDER_LIST,
    }


# ---------------------------------------------------------------------------
# Prompt Suggestions
# ---------------------------------------------------------------------------


@router.post("/suggestions", response_model=list[PromptSuggestion])
async def set_default_suggestions(
    request: Request,
    form_data: SetDefaultSuggestionsForm,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    cfg.DEFAULT_PROMPT_SUGGESTIONS = form_data.model_dump()["suggestions"]
    return cfg.DEFAULT_PROMPT_SUGGESTIONS


# ---------------------------------------------------------------------------
# Banners
# ---------------------------------------------------------------------------


@router.post("/banners", response_model=list[BannerModel])
async def set_banners(
    request: Request,
    form_data: SetBannersForm,
    user=Depends(get_admin_user),
):
    cfg = _app_config(request)
    cfg.BANNERS = form_data.model_dump()["banners"]
    return cfg.BANNERS


@router.get("/banners", response_model=list[BannerModel])
async def get_banners(
    request: Request,
    user=Depends(get_verified_user),
):
    return _app_config(request).BANNERS
