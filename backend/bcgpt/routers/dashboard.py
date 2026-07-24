# backend/bcgpt/routers/dashboard.py
"""Admin monitoring dashboard API.

Thin fan-out over existing aggregation helpers; response is assembled by pure
functions in bcgpt.utils.dashboard. Every domain is wrapped so one failing
query degrades only its own section. Admin-only (get_admin_user).
"""

import time

from fastapi import APIRouter, Depends, Query, Request

from bcgpt.utils import get_admin_user
from bcgpt.utils.dashboard import assemble_overview, assemble_realtime

from bcgpt.models.token_usage import TokenUsages
from bcgpt.models.audit_log import AuditLogs
from bcgpt.models.security_events import SecurityEvents
from bcgpt.models.handoff_requests import HandoffRequests
from bcgpt.models.users import Users
from bcgpt.models.chats import Chats
from bcgpt.models.feedbacks import Feedbacks

router = APIRouter()


def _flags(request: Request) -> dict:
    cfg = request.app.state.config
    return {
        "token_usage_persist_enabled": bool(cfg.TOKEN_USAGE_PERSIST_ENABLED),
        "ai_interaction_audit_enabled": bool(cfg.AI_INTERACTION_AUDIT_ENABLED),
    }


@router.get("/overview")
async def overview(
    request: Request,
    period: str = Query("7d"),
    user=Depends(get_admin_user),
):
    flags = _flags(request)
    now_ms = int(time.time() * 1000)
    from bcgpt.utils.dashboard import resolve_window

    win = resolve_window(period, now_ms=now_ms)
    start, end = win["start_ts"], win["end_ts"]
    prev_start, prev_end = win["prev_start_ts"], win["prev_end_ts"]
    s, e = win["start_ts_s"], win["end_ts_s"]
    ps, pe = win["prev_start_ts_s"], win["prev_end_ts_s"]
    flags_on = flags["token_usage_persist_enabled"]

    def fetch(key):
        if key == "users_total":
            return Users.get_num_users() or 0
        if key == "signups":
            return (
                sum(p["value"] for p in Users.signups_by_day(s, e)),
                sum(p["value"] for p in Users.signups_by_day(ps, pe)) or None,
            )
        if key == "active":
            return (
                sum(p["value"] for p in Users.active_users_by_day(s, e)),
                sum(p["value"] for p in Users.active_users_by_day(ps, pe)) or None,
            )
        if key == "chats_new":
            return (
                sum(p["value"] for p in Chats.new_chats_by_day(s, e)),
                sum(p["value"] for p in Chats.new_chats_by_day(ps, pe)) or None,
            )
        if key == "chats_series":
            return Chats.new_chats_by_day(s, e)
        if key == "signups_series":
            return Users.signups_by_day(s, e)
        if key == "active_series":
            return Users.active_users_by_day(s, e)
        if key == "audit_stats":
            return AuditLogs.get_stats()
        if key == "audit_series":
            # audit timeline is hours-based; bucket to day via gap_fill on epoch-day
            return _timeline_to_days(
                AuditLogs.get_timeline_data(
                    hours=max(1, (end - start) // 86_400_000) * 24, interval="hour"
                ),
                start,
                end,
            )
        if key == "security_stats":
            stats = SecurityEvents.get_event_stats(start, end) or {}
            stats["by_direction"] = (
                SecurityEvents.get_direction_breakdown(start, end) or {}
            )
            return stats
        if key == "security_series":
            return _timeline_to_days(
                SecurityEvents.get_timeline_data(start, end, granularity="hour"),
                start,
                end,
            )
        if key == "security_prev":
            prev = SecurityEvents.get_event_stats(prev_start, prev_end)
            return prev.get("total")
        if key == "top_security":
            rows = SecurityEvents.get_top_users(start, end, limit=5) or []
            return [
                {
                    "user_id": r.get("user_id", "?"),
                    "name": "",
                    "events": int(r.get("event_count", 0)),
                    "blocked": 0,
                }
                for r in rows
            ]
        if key == "handoff":
            h = HandoffRequests.get_handoff_stats() or {}
            return {
                "pending": (h.get("by_status") or {}).get("pending", 0),
                "total": h.get("total", 0),
                "avg_resolution_ms": h.get("avg_resolution_time_ms"),
            }
        if key == "feedback":
            return Feedbacks.rating_distribution(s, e)
        if key == "usage_total":
            return TokenUsages.total_usage(start, end) if flags_on else None
        if key == "usage_prev":
            return TokenUsages.total_usage(prev_start, prev_end) if flags_on else None
        if key == "tokens_series":
            if not flags_on:
                return []
            return [
                {
                    "day": int(r.get("day", 0)),
                    "prompt": int(r.get("prompt_tokens", 0)),
                    "completion": int(r.get("completion_tokens", 0)),
                    "total": int(r.get("total_tokens", 0)),
                    "cost": round(float(r.get("cost", 0.0)), 6),
                }
                for r in (TokenUsages.usage_by_day(start, end) or [])
            ]
        if key == "models":
            return (
                _models_breakdown(TokenUsages.usage_by_model(start, end))
                if flags_on
                else []
            )
        if key == "top_users_usage":
            return _top_users(TokenUsages.usage_by_user(start, end)) if flags_on else []
        if key == "heatmap_cells":
            return _heatmap_cells(Chats.new_chats_by_day(s, e))
        if key == "anomalies":
            return AuditLogs.get_anomalies(hours=24 * win["days"])
        if key == "recent_critical":
            return _recent_critical()
        raise KeyError(key)

    return assemble_overview(period, flags=flags, now_ms=now_ms, fetch=fetch)


# ---- small pure shapers (kept here; tested via the router/assemble path) ----


def _timeline_to_days(timeline, start_ms, end_ms):
    """Convert audit/security hour-bucket timeline → epoch-day series.

    Audit entries carry ``count``; security entries carry ``total`` — we accept
    either and re-bucket by epoch-day.
    """
    from collections import defaultdict

    by_day = defaultdict(int)
    for entry in timeline or []:
        ts = entry.get("timestamp") or entry.get("ts") or 0
        c = entry.get("count", entry.get("total", 0))
        by_day[ts // 86_400_000] += int(c or 0)
    return [{"day": d, "value": v} for d, v in sorted(by_day.items())]


def _models_breakdown(rows):
    total = sum(int((r or {}).get("total_tokens", 0)) for r in rows) or 1
    out = []
    for r in rows:
        tok = int(r.get("total_tokens", 0))
        out.append(
            {
                "model": r.get("model", "?"),
                "tokens": tok,
                "cost": round(float(r.get("cost", 0.0)), 4),
                "requests": int(r.get("count", 0)),
                "pct": round(tok / total * 100.0, 1),
            }
        )
    return sorted(out, key=lambda x: x["tokens"], reverse=True)


def _top_users(rows):
    out = []
    for r in rows:
        out.append(
            {
                "user_id": r.get("user_id", "?"),
                "name": "",
                "tokens": int(r.get("total_tokens", 0)),
                "cost": round(float(r.get("cost", 0.0)), 4),
                "requests": int(r.get("count", 0)),
            }
        )
    return sorted(out, key=lambda x: x["tokens"], reverse=True)[:10]


def _heatmap_cells(series):
    """Placeholder: daily chat counts rendered as a day-of-week × hour grid
    cannot be derived from day-totals alone; we emit an empty grid and let the
    frontend show 'no hourly data'. (A real hourly source can be wired later.)"""
    return []


def _recent_critical():
    try:
        from bcgpt.models.audit_log import AuditLog
        from bcgpt.internal import get_db

        with get_db() as db:
            rows = (
                db.query(AuditLog)
                .filter(AuditLog.severity == "CRITICAL")
                .order_by(AuditLog.timestamp.desc())
                .limit(10)
                .all()
            )
            return [
                {
                    "timestamp": r.timestamp,
                    "action": r.action,
                    "user_email": r.user_email,
                    "severity": r.severity,
                    "resource_name": r.resource_name,
                }
                for r in rows
            ]
    except Exception:
        return []


@router.get("/realtime")
async def realtime(request: Request, user=Depends(get_admin_user)):
    flags = _flags(request)
    now_ms = int(time.time() * 1000)
    min_ms = 60_000
    five_min_ms = 5 * min_ms
    hour_ms = 60 * min_ms

    def fetch(key):
        if key == "active_users_5m":
            return _distinct_users_since(now_ms - five_min_ms, now_ms)
        if key == "ai_responses_1m":
            return _usage_count_since(now_ms - min_ms, now_ms)
        if key == "tokens_1m":
            return _usage_tokens_since(now_ms - min_ms, now_ms)
        if key == "guardrail_events_5m":
            return SecurityEvents.count_events(
                start_ts=now_ms - five_min_ms, end_ts=now_ms
            )
        if key == "guardrail_blocks_1m":
            stats = SecurityEvents.get_event_stats(now_ms - min_ms, now_ms)
            return (stats or {}).get("blocked_count", 0)
        if key == "pending_handoffs":
            return (
                (HandoffRequests.get_handoff_stats() or {})
                .get("by_status", {})
                .get("pending", 0)
            )
        if key == "critical_audit_1h":
            # TRUE 1h count. AuditLogs.get_stats()["recent_critical_count"] is a
            # 24h figure (models/audit_log.py hardcodes 24h) — don't reuse it
            # under a "1h" label.
            return _critical_audit_count_since(now_ms - hour_ms, now_ms)
        if key == "audit_events_1h":
            tl = AuditLogs.get_timeline_data(hours=1, interval="hour")
            return sum(int((e or {}).get("count", 0)) for e in (tl or []))
        raise KeyError(key)

    return assemble_realtime(flags=flags, now_ms=now_ms, fetch=fetch)


def _distinct_users_since(start_ms, end_ms):
    try:
        from bcgpt.models.audit_log import AuditLog
        from bcgpt.internal import get_db
        from sqlalchemy import func

        with get_db() as db:
            return (
                db.query(func.count(func.distinct(AuditLog.user_id)))
                .filter(AuditLog.timestamp >= start_ms, AuditLog.timestamp <= end_ms)
                .scalar()
                or 0
            )
    except Exception:
        return 0


def _critical_audit_count_since(start_ms: int, end_ms: int) -> int:
    """Count CRITICAL audit entries in [start_ms, end_ms] (parameterized ORM).

    AuditLogs.get_stats()["recent_critical_count"] is a 24h figure, so it cannot
    back the "Critical (1h)" realtime card — this gives a true windowed count.
    """
    try:
        from bcgpt.models.audit_log import AuditLog
        from bcgpt.internal import get_db

        with get_db() as db:
            return (
                db.query(AuditLog)
                .filter(
                    AuditLog.severity == "CRITICAL",
                    AuditLog.timestamp >= start_ms,
                    AuditLog.timestamp <= end_ms,
                )
                .count()
            ) or 0
    except Exception:
        return 0


def _usage_count_since(start_ms, end_ms):
    try:
        return (TokenUsages.total_usage(start_ms, end_ms) or {}).get("count", 0)
    except Exception:
        return None


def _usage_tokens_since(start_ms, end_ms):
    try:
        return (TokenUsages.total_usage(start_ms, end_ms) or {}).get("total_tokens", 0)
    except Exception:
        return None
