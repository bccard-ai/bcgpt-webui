"""
Claude API endpoints – admin config, verify, models.

Mounted at /claude in main.py.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.providers.claude import ClaudeProvider

log = logging.getLogger(__name__)

router = APIRouter()


class ClaudeConfigForm(BaseModel):
    ENABLE_CLAUDE_API: Optional[bool] = None
    CLAUDE_API_KEYS: list[str]
    CLAUDE_API_BASE_URL: Optional[str] = None
    CLAUDE_API_CONFIGS: dict


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ENABLE_CLAUDE_API": request.app.state.config.ENABLE_CLAUDE_API,
        "CLAUDE_API_KEYS": request.app.state.config.CLAUDE_API_KEYS,
        "CLAUDE_API_BASE_URL": request.app.state.config.CLAUDE_API_BASE_URL,
        "CLAUDE_API_CONFIGS": request.app.state.config.CLAUDE_API_CONFIGS,
    }


@router.post("/config/update")
async def update_config(
    request: Request, form_data: ClaudeConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.ENABLE_CLAUDE_API = form_data.ENABLE_CLAUDE_API
    request.app.state.config.CLAUDE_API_KEYS = form_data.CLAUDE_API_KEYS
    request.app.state.config.CLAUDE_API_BASE_URL = form_data.CLAUDE_API_BASE_URL or ""
    request.app.state.config.CLAUDE_API_CONFIGS = form_data.CLAUDE_API_CONFIGS
    return {"status": True}


@router.post("/verify")
async def verify_connection(request: Request, user=Depends(get_admin_user)):
    provider = ClaudeProvider(request.app.state.config)
    return await provider.verify_connection(request, user)


@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    provider = ClaudeProvider(request.app.state.config)
    models = await provider.get_models(request, user=user)
    return {"data": models}
