"""Utility endpoints for format conversion, PDF generation, and admin exports."""

from __future__ import annotations

import logging

import black
import markdown
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from starlette.responses import FileResponse

from bcgpt.config import DATA_DIR, ENABLE_ADMIN_EXPORT
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import ChatTitleMessagesForm
from bcgpt.utils import (
    PDFGenerator,
    get_admin_user,
    get_gravatar_url,
    get_verified_user,
    has_permission,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CodeForm(BaseModel):
    """Code snippet submitted for auto-formatting."""

    code: str


class MarkdownForm(BaseModel):
    """Markdown source to convert to HTML."""

    md: str


class ChatForm(BaseModel):
    """Chat data for PDF export (deprecated – kept for backward compat)."""

    title: str
    messages: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/gravatar")
async def get_gravatar(email: str, user=Depends(get_verified_user)):
    """Return the Gravatar URL for the given *email* address."""
    return get_gravatar_url(email)


@router.post("/code/format")
async def format_code(form_data: CodeForm, user=Depends(get_verified_user)):
    """Auto-format Python source code using *black*."""
    try:
        formatted_code = black.format_str(form_data.code, mode=black.Mode())
        return {"code": formatted_code}
    except black.NothingChanged:
        return {"code": form_data.code}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/markdown")
async def get_html_from_markdown(
    form_data: MarkdownForm, user=Depends(get_verified_user)
):
    """Convert a Markdown string to HTML."""
    return {"html": markdown.markdown(form_data.md)}


@router.post("/pdf")
async def download_chat_as_pdf(
    form_data: ChatTitleMessagesForm, user=Depends(get_verified_user)
):
    """Generate a PDF from chat messages and return it as a download."""
    try:
        pdf_bytes = PDFGenerator(form_data).generate_chat_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment;filename=chat.pdf"},
        )
    except Exception as exc:
        log.exception("Error generating PDF: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    """Download the SQLite database file (admin-only, gated by config flag)."""
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    from bcgpt.internal import engine

    if engine.name != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )

    return FileResponse(
        engine.url.database,
        media_type="application/octet-stream",
        filename="bcgpt.db",
    )


@router.get("/litellm/config")
async def download_litellm_config_yaml(user=Depends(get_admin_user)):
    """Download the LiteLLM configuration YAML file."""
    return FileResponse(
        f"{DATA_DIR}/litellm/config.yaml",
        media_type="application/octet-stream",
        filename="config.yaml",
    )
