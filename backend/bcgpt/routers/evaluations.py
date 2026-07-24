"""Evaluation and feedback router.

Manages evaluation arena configuration and user feedback CRUD operations.
Arena mode allows administrators to configure side-by-side model comparison,
while feedback endpoints let verified users submit, retrieve, update, and
delete their evaluation feedback.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.models import Users
from bcgpt.models.feedbacks import FeedbackForm, FeedbackModel, FeedbackResponse, Feedbacks
from bcgpt.utils import get_admin_user, get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class UpdateConfigForm(BaseModel):
    """Payload for updating evaluation arena configuration."""

    ENABLE_EVALUATION_ARENA_MODELS: Optional[bool] = None
    EVALUATION_ARENA_MODELS: Optional[list[dict]] = None


class FeedbackUserReponse(BaseModel):
    """User details embedded in feedback listings."""

    id: str
    name: str
    email: str
    role: str = "pending"
    last_active_at: int
    updated_at: int
    created_at: int


class FeedbackUserResponse(FeedbackResponse):
    """Feedback record with optional user information."""

    user: Optional[FeedbackUserReponse] = None


# ---------------------------------------------------------------------------
# Arena configuration
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """Return the current evaluation arena configuration."""
    return {
        "ENABLE_EVALUATION_ARENA_MODELS": request.app.state.config.ENABLE_EVALUATION_ARENA_MODELS,
        "EVALUATION_ARENA_MODELS": request.app.state.config.EVALUATION_ARENA_MODELS,
    }


@router.post("/config")
async def update_config(
    request: Request,
    form_data: UpdateConfigForm,
    user=Depends(get_admin_user),
):
    """Update evaluation arena configuration fields.

    Only fields present in the request body are applied; omitted fields
    retain their current values.
    """
    config = request.app.state.config
    if form_data.ENABLE_EVALUATION_ARENA_MODELS is not None:
        config.ENABLE_EVALUATION_ARENA_MODELS = form_data.ENABLE_EVALUATION_ARENA_MODELS
        log.info("Arena models toggle set to %s", config.ENABLE_EVALUATION_ARENA_MODELS)
    if form_data.EVALUATION_ARENA_MODELS is not None:
        config.EVALUATION_ARENA_MODELS = form_data.EVALUATION_ARENA_MODELS
        log.info("Arena models list updated with %d entries", len(config.EVALUATION_ARENA_MODELS))
    return {
        "ENABLE_EVALUATION_ARENA_MODELS": config.ENABLE_EVALUATION_ARENA_MODELS,
        "EVALUATION_ARENA_MODELS": config.EVALUATION_ARENA_MODELS,
    }


# ---------------------------------------------------------------------------
# Feedback – admin endpoints
# ---------------------------------------------------------------------------


@router.get("/feedbacks/all", response_model=list[FeedbackUserResponse])
async def get_all_feedbacks(user=Depends(get_admin_user)):
    """Retrieve every feedback record with the associated user profile.

    Only accessible to administrators.
    """
    feedbacks = Feedbacks.get_all_feedbacks()
    result: list[FeedbackUserResponse] = []
    for feedback in feedbacks:
        user_record = Users.get_user_by_id(feedback.user_id)
        result.append(
            FeedbackUserResponse(
                **feedback.model_dump(),
                user=FeedbackUserReponse(**user_record.model_dump()),
            )
        )
    return result


@router.delete("/feedbacks/all")
async def delete_all_feedbacks(user=Depends(get_admin_user)):
    """Delete every feedback record in the system.

    Only accessible to administrators.
    """
    return Feedbacks.delete_all_feedbacks()


@router.get("/feedbacks/all/export", response_model=list[FeedbackModel])
async def export_all_feedbacks(user=Depends(get_admin_user)):
    """Export all feedback records with full user details for analysis.

    Only accessible to administrators.
    """
    feedbacks = Feedbacks.get_all_feedbacks()
    return [
        FeedbackModel(**fb.model_dump(), user=Users.get_user_by_id(fb.user_id))
        for fb in feedbacks
    ]


# ---------------------------------------------------------------------------
# Feedback – per-user endpoints
# ---------------------------------------------------------------------------


@router.get("/feedbacks/user", response_model=list[FeedbackUserResponse])
async def get_feedbacks(user=Depends(get_verified_user)):
    """Retrieve all feedback submitted by the authenticated user."""
    return Feedbacks.get_feedbacks_by_user_id(user.id)


@router.delete("/feedbacks", response_model=bool)
async def delete_feedbacks(user=Depends(get_verified_user)):
    """Delete every feedback record owned by the authenticated user."""
    return Feedbacks.delete_feedbacks_by_user_id(user.id)


# ---------------------------------------------------------------------------
# Feedback – single-record endpoints
# ---------------------------------------------------------------------------


@router.post("/feedback", response_model=FeedbackModel)
async def create_feedback(
    request: Request,
    form_data: FeedbackForm,
    user=Depends(get_verified_user),
):
    """Create a new feedback entry for the authenticated user."""
    feedback = Feedbacks.insert_new_feedback(user_id=user.id, form_data=form_data)
    if not feedback:
        log.warning("Failed to create feedback for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )
    return feedback


@router.get("/feedback/{id}", response_model=FeedbackModel)
async def get_feedback_by_id(id: str, user=Depends(get_verified_user)):
    """Retrieve a single feedback record owned by the authenticated user."""
    feedback = Feedbacks.get_feedback_by_id_and_user_id(id=id, user_id=user.id)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return feedback


@router.post("/feedback/{id}", response_model=FeedbackModel)
async def update_feedback_by_id(
    id: str,
    form_data: FeedbackForm,
    user=Depends(get_verified_user),
):
    """Update a feedback record owned by the authenticated user."""
    feedback = Feedbacks.update_feedback_by_id_and_user_id(
        id=id,
        user_id=user.id,
        form_data=form_data,
    )
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return feedback


@router.delete("/feedback/{id}")
async def delete_feedback_by_id(id: str, user=Depends(get_verified_user)):
    """Delete a feedback record.

    Administrators may delete any record; regular users may only delete
    their own.
    """
    if user.role == "admin":
        success = Feedbacks.delete_feedback_by_id(id=id)
    else:
        success = Feedbacks.delete_feedback_by_id_and_user_id(id=id, user_id=user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return success
