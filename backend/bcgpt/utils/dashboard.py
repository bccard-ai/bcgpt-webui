# backend/bcgpt/utils/dashboard.py
"""Pure helpers for the admin dashboard.

No DB access here — these functions take already-aggregated numbers and
assemble the response, so they are fully unit-testable. Time-bucket math is
DB-agnostic (epoch-day via floor division), matching models/token_usage.py.
"""

import datetime as _dt
import time
from typing import Optional

_DAY_MS = 86_400_000
PERIOD_DAYS = {"today": 1, "7d": 7, "30d": 30, "90d": 90}


def resolve_window(period: str, now_ms: Optional[int] = None) -> dict:
    """Resolve [start, end] plus the previous equal-length window for deltas."""
    days = PERIOD_DAYS.get(period, 7)
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    if period == "today":
        start = (now // _DAY_MS) * _DAY_MS  # UTC midnight of today
    else:
        start = now - days * _DAY_MS
    prev_start = start - days * _DAY_MS
    prev_end = start
    return {
        "period": period,
        "days": days,
        "start_ts": start,
        "end_ts": now,
        "prev_start_ts": prev_start,
        "prev_end_ts": prev_end,
        # epoch-seconds variants for chat/user/feedback tables:
        "start_ts_s": start // 1000,
        "end_ts_s": now // 1000,
        "prev_start_ts_s": prev_start // 1000,
        "prev_end_ts_s": prev_end // 1000,
    }


def delta_pct(curr, prev) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / prev * 100.0, 1)


def _day_to_date(day_int: int) -> str:
    return _dt.datetime.fromtimestamp(day_int * 86400, _dt.timezone.utc).strftime(
        "%Y-%m-%d"
    )


def gap_fill(
    points: list[dict],
    start_ts_ms: int,
    end_ts_ms: int,
    value_keys: tuple = ("value",),
    default=0,
) -> list[dict]:
    """Fill one entry per day in [start_day, end_day], preserving extra keys.

    ``points`` entries carry an epoch-day int under ``day`` (mirrors
    ``TokenUsages.usage_by_day``). Returns entries with an added ``date``
    'YYYY-MM-DD' and ensures every ``value_keys`` field exists.
    """
    start_day = start_ts_ms // _DAY_MS
    end_day = end_ts_ms // _DAY_MS
    by_day = {p["day"]: p for p in points}
    out = []
    for d in range(start_day, end_day + 1):
        base = dict(by_day[d]) if d in by_day else {"day": d}
        base["date"] = _day_to_date(d)
        for k in value_keys:
            base.setdefault(k, default)
        out.append(base)
    return out


def _kpi(value, prev):
    return {"value": value, "prev": prev, "delta_pct": delta_pct(value, prev)}


def assemble_overview(period: str, *, flags: dict, now_ms: int, fetch) -> dict:
    """Compose the /overview payload from per-domain helper outputs.

    ``fetch(key)`` returns the already-aggregated value for a domain; raising
    from a single fetch degrades only that domain (resilience).
    """
    w = resolve_window(period, now_ms=now_ms)

    def safe(key, default):
        try:
            return fetch(key)
        except Exception:
            return default

    users_total = safe("users_total", 0)
    signups_cur, signups_prev = safe("signups", (0, None))
    active_cur, active_prev = safe("active", (0, None))
    chats_cur, chats_prev = safe("chats_new", (0, None))
    sec_prev = safe("security_prev", None)
    audit_stats = safe("audit_stats", {})
    sec_stats = safe("security_stats", {})
    handoff = safe("handoff", {})
    feedback = safe(
        "feedback", {"count": 0, "avg": 0.0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    )

    usage_on = bool(flags.get("token_usage_persist_enabled"))
    usage_total = safe("usage_total", None) if usage_on else None
    usage_prev = safe("usage_prev", None) if usage_on else None
    tokens_series = safe("tokens_series", []) if usage_on else []
    models = safe("models", []) if usage_on else []
    top_users_usage = safe("top_users_usage", []) if usage_on else []

    tokens_kpi = {"available": usage_on}
    cost_kpi = {"available": usage_on}
    if usage_on and usage_total:
        tokens_kpi.update(
            {
                "value": usage_total.get("total_tokens", 0),
                "prompt": usage_total.get("prompt_tokens", 0),
                "completion": usage_total.get("completion_tokens", 0),
                "prev": (usage_prev or {}).get("total_tokens"),
                "delta_pct": delta_pct(
                    usage_total.get("total_tokens", 0),
                    (usage_prev or {}).get("total_tokens"),
                ),
            }
        )
        cost_kpi.update(
            {
                "value": usage_total.get("cost", 0.0),
                "prev": (usage_prev or {}).get("cost"),
                "delta_pct": delta_pct(
                    usage_total.get("cost", 0.0), (usage_prev or {}).get("cost")
                ),
            }
        )

    ai_responses = (usage_total or {}).get("count") if usage_on else None

    guardrail_events = sec_stats.get("total", 0)
    blocked = sec_stats.get("blocked_count", 0)
    block_rate = (
        round(blocked / guardrail_events * 100.0, 1) if guardrail_events else 0.0
    )

    return {
        "period": w["period"],
        "generated_at": now_ms,
        "window": {
            k: w[k] for k in ("start_ts", "end_ts", "prev_start_ts", "prev_end_ts")
        },
        "flags": flags,
        "kpis": {
            "users": _kpi(signups_cur, signups_prev) | {"total": users_total},
            "active_users": _kpi(active_cur, active_prev),
            "chats": _kpi(chats_cur, chats_prev),
            "ai_responses": {
                "value": ai_responses,
                "prev": None,
                "available": usage_on,
            },
            "tokens": tokens_kpi,
            "cost": cost_kpi,
            "feedback": {
                "count": feedback.get("count", 0),
                "avg_rating": feedback.get("avg", 0.0),
            },
            "guardrail": {
                "events": guardrail_events,
                "blocked": blocked,
                "block_rate": block_rate,
                "shadow": sec_stats.get("shadow_count", 0),
                "prev_events": sec_prev,
            },
            "handoff": {
                "pending": handoff.get("pending", 0),
                "total": handoff.get("total", 0),
                "avg_resolution_ms": handoff.get("avg_resolution_ms"),
            },
            "audit": {
                "total_logs": audit_stats.get("total_logs", 0),
                "critical_24h": audit_stats.get("recent_critical_count", 0),
            },
        },
        "series": {
            "chats_by_day": gap_fill(
                safe("chats_series", []), w["start_ts"], w["end_ts"]
            ),
            "signups_by_day": gap_fill(
                safe("signups_series", []), w["start_ts"], w["end_ts"]
            ),
            "active_users_by_day": gap_fill(
                safe("active_series", []), w["start_ts"], w["end_ts"]
            ),
            "tokens_by_day": (
                gap_fill(
                    tokens_series,
                    w["start_ts"],
                    w["end_ts"],
                    value_keys=("prompt", "completion", "total", "cost"),
                )
                if usage_on
                else []
            ),
            "audit_by_day": gap_fill(
                safe("audit_series", []), w["start_ts"], w["end_ts"]
            ),
            "security_by_day": gap_fill(
                safe("security_series", []), w["start_ts"], w["end_ts"]
            ),
        },
        "breakdowns": {
            "models": models,
            "top_users_usage": top_users_usage,
            "audit_by_severity": audit_stats.get("by_severity", {}),
            "audit_by_action": audit_stats.get("by_action", {}),
            "audit_by_resource_type": audit_stats.get("by_resource_type", {}),
            "security_by_scanner": sec_stats.get("by_scanner", {}),
            "security_by_threat_type": sec_stats.get("by_threat_type", {}),
            "security_by_direction": sec_stats.get("by_direction", {}),
            "feedback_ratings": {
                k: feedback.get(k, 0) for k in ("1", "2", "3", "4", "5")
            },
        },
        "heatmap": {"source": "chats", "cells": safe("heatmap_cells", [])},
        "top_users_security": safe("top_security", []),
        "anomalies": safe("anomalies", []),
        "recent_critical": safe("recent_critical", []),
    }


def assemble_realtime(*, flags: dict, now_ms: int, fetch) -> dict:
    usage_on = bool(flags.get("token_usage_persist_enabled"))
    return {
        "generated_at": now_ms,
        "active_users_5m": fetch_safe(fetch, "active_users_5m", 0),
        "ai_responses_1m": (
            fetch_safe(fetch, "ai_responses_1m", None) if usage_on else None
        ),
        "tokens_1m": (fetch_safe(fetch, "tokens_1m", None) if usage_on else None),
        "guardrail_events_5m": fetch_safe(fetch, "guardrail_events_5m", 0),
        "guardrail_blocks_1m": fetch_safe(fetch, "guardrail_blocks_1m", 0),
        "pending_handoffs": fetch_safe(fetch, "pending_handoffs", 0),
        "critical_audit_1h": fetch_safe(fetch, "critical_audit_1h", 0),
        "audit_events_1h": fetch_safe(fetch, "audit_events_1h", 0),
    }


def fetch_safe(fetch, key, default):
    try:
        return fetch(key)
    except Exception:
        return default
