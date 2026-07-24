"""Token/cost usage persistence + model pricing (FinOps backbone).

open-moai adoption 2.1. bcgpt previously recorded LLM tokens only as volatile
Prometheus counters; this persists them to ``llm_token_usage`` with a computed
cost (from ``model_pricing``) so usage/cost can be aggregated per user/model/
agent/day. All aggregation helpers use a single GROUP BY round-trip (anti-N+1).

PostgreSQL-compatible (DB-agnostic SQLAlchemy column types).
"""

import logging
import time
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    Integer,
    String,
    cast,
    func,
)
from pydantic import BaseModel, ConfigDict

from bcgpt.internal import Base, get_db
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


############################
# DB Schemas
############################


class LLMTokenUsage(Base):
    __tablename__ = "llm_token_usage"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True, index=True)
    model = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=True)
    agent_id = Column(String, nullable=True, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(BigInteger, nullable=False, index=True)


class ModelPricing(Base):
    __tablename__ = "model_pricing"

    model = Column(String, primary_key=True)
    input_per_1k = Column(Float, default=0.0)
    output_per_1k = Column(Float, default=0.0)
    updated_at = Column(BigInteger, nullable=False)


############################
# Pydantic models
############################


class LLMTokenUsageModel(BaseModel):
    id: str
    user_id: Optional[str] = None
    model: str
    provider: Optional[str] = None
    agent_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class ModelPricingModel(BaseModel):
    model: str
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


# Approximate seed pricing in USD per 1k tokens. Operators should override via
# the model_pricing table for accuracy; unknown models cost 0.0 (never a wrong
# non-zero estimate).
_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.0008, 0.004),
}


############################
# CRUD tables
############################


def _normalize_token_counts(prompt_tokens, completion_tokens) -> tuple[int, int]:
    """Coerce token counts to non-negative ints.

    Token counts are inherently non-negative quantities. Provider usage data is
    trusted in practice, but a malformed/attacked response carrying a negative
    count must not corrupt the aggregates/cost (which sum these columns), and
    the persistence path must stay consistent with the budget limiter (which
    already ignores non-positive tokens). ``None``, non-numeric, and negative
    values all map to 0.
    """

    def _norm(v) -> int:
        try:
            return max(0, int(v or 0))
        except (TypeError, ValueError):
            return 0

    return _norm(prompt_tokens), _norm(completion_tokens)


class ModelPricingTable:
    def get_pricing(self, model: str) -> Optional[ModelPricingModel]:
        if not model:
            return None
        try:
            with get_db() as db:
                row = db.query(ModelPricing).filter_by(model=model).first()
                return ModelPricingModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("Error reading model pricing: %s", e)
            return None

    def upsert_pricing(
        self, model: str, input_per_1k: float, output_per_1k: float
    ) -> Optional[ModelPricingModel]:
        # Pricing is inherently non-negative; clamp so an admin typo (or a
        # compromised admin) can't produce negative costs that mask usage.
        input_per_1k = max(0.0, float(input_per_1k or 0.0))
        output_per_1k = max(0.0, float(output_per_1k or 0.0))
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                row = db.query(ModelPricing).filter_by(model=model).first()
                if row:
                    row.input_per_1k = input_per_1k
                    row.output_per_1k = output_per_1k
                    row.updated_at = now
                else:
                    row = ModelPricing(
                        model=model,
                        input_per_1k=input_per_1k,
                        output_per_1k=output_per_1k,
                        updated_at=now,
                    )
                    db.add(row)
                db.commit()
                db.refresh(row)
                return ModelPricingModel.model_validate(row)
        except Exception as e:
            log.exception("Error upserting model pricing: %s", e)
            return None

    def seed_defaults(self) -> int:
        """Insert default pricing rows that don't already exist. Idempotent."""
        inserted = 0
        try:
            with get_db() as db:
                now = int(time.time() * 1000)
                for model, (inp, out) in _DEFAULT_PRICING.items():
                    if not db.query(ModelPricing).filter_by(model=model).first():
                        db.add(
                            ModelPricing(
                                model=model,
                                input_per_1k=inp,
                                output_per_1k=out,
                                updated_at=now,
                            )
                        )
                        inserted += 1
                db.commit()
        except Exception as e:
            log.exception("Error seeding model pricing: %s", e)
        return inserted

    def compute_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Cost in USD from per-1k pricing; 0.0 if the model is unpriced."""
        pricing = self.get_pricing(model)
        if not pricing:
            return 0.0
        return round(
            (prompt_tokens / 1000.0) * pricing.input_per_1k
            + (completion_tokens / 1000.0) * pricing.output_per_1k,
            6,
        )


class TokenUsagesTable:
    def insert_usage(
        self,
        user_id: Optional[str],
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        provider: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[LLMTokenUsageModel]:
        try:
            prompt_tokens, completion_tokens = _normalize_token_counts(
                prompt_tokens, completion_tokens
            )
            total = prompt_tokens + completion_tokens
            cost = ModelPricings.compute_cost(model, prompt_tokens, completion_tokens)
            with get_db() as db:
                row = LLMTokenUsage(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    model=model or "unknown",
                    provider=provider,
                    agent_id=agent_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total,
                    cost=cost,
                    created_at=int(time.time() * 1000),
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return LLMTokenUsageModel.model_validate(row)
        except Exception as e:
            log.exception("Error inserting token usage: %s", e)
            return None

    def _aggregate(
        self,
        group_col,
        group_key: str,
        start_ts: Optional[int],
        end_ts: Optional[int],
    ) -> list[dict]:
        """Single-round-trip GROUP BY aggregation (anti-N+1)."""
        try:
            with get_db() as db:
                q = db.query(
                    group_col,
                    func.sum(LLMTokenUsage.prompt_tokens),
                    func.sum(LLMTokenUsage.completion_tokens),
                    func.sum(LLMTokenUsage.total_tokens),
                    func.sum(LLMTokenUsage.cost),
                    func.count(LLMTokenUsage.id),
                )
                if start_ts is not None:
                    q = q.filter(LLMTokenUsage.created_at >= start_ts)
                if end_ts is not None:
                    q = q.filter(LLMTokenUsage.created_at <= end_ts)
                rows = q.group_by(group_col).all()
                return [
                    {
                        group_key: r[0],
                        "prompt_tokens": int(r[1] or 0),
                        "completion_tokens": int(r[2] or 0),
                        "total_tokens": int(r[3] or 0),
                        "cost": round(float(r[4] or 0.0), 6),
                        "count": int(r[5] or 0),
                    }
                    for r in rows
                ]
        except Exception as e:
            log.exception("Error aggregating token usage: %s", e)
            return []

    def usage_by_user(
        self, start_ts: Optional[int] = None, end_ts: Optional[int] = None
    ) -> list[dict]:
        return self._aggregate(LLMTokenUsage.user_id, "user_id", start_ts, end_ts)

    def usage_by_model(
        self, start_ts: Optional[int] = None, end_ts: Optional[int] = None
    ) -> list[dict]:
        return self._aggregate(LLMTokenUsage.model, "model", start_ts, end_ts)

    def usage_by_agent(
        self, start_ts: Optional[int] = None, end_ts: Optional[int] = None
    ) -> list[dict]:
        return self._aggregate(LLMTokenUsage.agent_id, "agent_id", start_ts, end_ts)

    def usage_by_day(
        self, start_ts: Optional[int] = None, end_ts: Optional[int] = None
    ) -> list[dict]:
        """Daily rollup. Buckets by epoch-day = floor(created_at_ms / 86_400_000).

        Uses float division + floor + integer cast so the bucket is a stable
        integer day on both PostgreSQL and SQLite (SQLite's ``/`` on integers is
        float division, which would otherwise split same-day rows by millisecond).
        """
        day_expr = cast(
            func.floor(LLMTokenUsage.created_at / 86400000.0), Integer
        ).label("day")
        return self._aggregate(day_expr, "day", start_ts, end_ts)

    def total_usage(
        self, start_ts: Optional[int] = None, end_ts: Optional[int] = None
    ) -> dict:
        try:
            with get_db() as db:
                q = db.query(
                    func.sum(LLMTokenUsage.prompt_tokens),
                    func.sum(LLMTokenUsage.completion_tokens),
                    func.sum(LLMTokenUsage.total_tokens),
                    func.sum(LLMTokenUsage.cost),
                    func.count(LLMTokenUsage.id),
                )
                if start_ts is not None:
                    q = q.filter(LLMTokenUsage.created_at >= start_ts)
                if end_ts is not None:
                    q = q.filter(LLMTokenUsage.created_at <= end_ts)
                r = q.one()
                return {
                    "prompt_tokens": int(r[0] or 0),
                    "completion_tokens": int(r[1] or 0),
                    "total_tokens": int(r[2] or 0),
                    "cost": round(float(r[3] or 0.0), 6),
                    "count": int(r[4] or 0),
                }
        except Exception as e:
            log.exception("Error computing total token usage: %s", e)
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "count": 0,
            }

    def purge_expired(self, days: int = 365) -> int:
        """Delete usage rows older than ``days`` (retention)."""
        try:
            cutoff = int((time.time() - days * 86400) * 1000)
            with get_db() as db:
                deleted = (
                    db.query(LLMTokenUsage)
                    .filter(LLMTokenUsage.created_at < cutoff)
                    .delete()
                )
                db.commit()
                return deleted
        except Exception as e:
            log.exception("Error purging token usage: %s", e)
            return 0


TokenUsages = TokenUsagesTable()
ModelPricings = ModelPricingTable()
