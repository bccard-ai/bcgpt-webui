"""Token/cost usage aggregation API (FinOps, open-moai adoption 2.1).

Admin-only endpoints exposing single-round-trip GROUP BY aggregations over the
``llm_token_usage`` table, plus ``model_pricing`` management. All aggregation
queries are anti-N+1 (one query each).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from bcgpt.models.token_usage import TokenUsages, ModelPricings
from bcgpt.utils import get_admin_user

router = APIRouter()


@router.get("/by_user")
async def usage_by_user(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    return {"data": TokenUsages.usage_by_user(start_ts, end_ts)}


@router.get("/by_model")
async def usage_by_model(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    return {"data": TokenUsages.usage_by_model(start_ts, end_ts)}


@router.get("/by_agent")
async def usage_by_agent(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    return {"data": TokenUsages.usage_by_agent(start_ts, end_ts)}


@router.get("/by_day")
async def usage_by_day(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    return {"data": TokenUsages.usage_by_day(start_ts, end_ts)}


@router.get("/total")
async def usage_total(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    return TokenUsages.total_usage(start_ts, end_ts)


class PricingForm(BaseModel):
    model: str
    input_per_1k: float
    output_per_1k: float


@router.post("/pricing")
async def upsert_pricing(form: PricingForm, user=Depends(get_admin_user)):
    return ModelPricings.upsert_pricing(
        form.model, form.input_per_1k, form.output_per_1k
    )


@router.post("/pricing/seed")
async def seed_pricing(user=Depends(get_admin_user)):
    return {"seeded": ModelPricings.seed_defaults()}
