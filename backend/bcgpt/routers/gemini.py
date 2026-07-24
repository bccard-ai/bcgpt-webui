"""
Gemini API endpoints – admin config, verify, models.

Mounted at /gemini in main.py.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.providers.gemini import GeminiProvider

log = logging.getLogger(__name__)

router = APIRouter()


class GeminiConfigForm(BaseModel):
    ENABLE_GEMINI_API: Optional[bool] = None
    GEMINI_API_KEYS: list[str]
    GEMINI_API_BASE_URL: Optional[str] = None
    GEMINI_API_CONFIGS: dict


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ENABLE_GEMINI_API": request.app.state.config.ENABLE_GEMINI_API,
        "GEMINI_API_KEYS": request.app.state.config.GEMINI_API_KEYS,
        "GEMINI_API_BASE_URL": request.app.state.config.GEMINI_API_BASE_URL,
        "GEMINI_API_CONFIGS": request.app.state.config.GEMINI_API_CONFIGS,
    }


@router.post("/config/update")
async def update_config(
    request: Request, form_data: GeminiConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.ENABLE_GEMINI_API = form_data.ENABLE_GEMINI_API
    request.app.state.config.GEMINI_API_KEYS = form_data.GEMINI_API_KEYS
    request.app.state.config.GEMINI_API_BASE_URL = form_data.GEMINI_API_BASE_URL or ""
    request.app.state.config.GEMINI_API_CONFIGS = form_data.GEMINI_API_CONFIGS
    return {"status": True}


@router.post("/verify")
async def verify_connection(request: Request, user=Depends(get_admin_user)):
    provider = GeminiProvider(request.app.state.config)
    return await provider.verify_connection(request, user)


@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    provider = GeminiProvider(request.app.state.config)
    models = await provider.get_models(request, user=user)
    return {"data": models}
