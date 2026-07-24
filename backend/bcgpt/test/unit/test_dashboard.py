# backend/bcgpt/test/unit/test_dashboard.py
"""Unit tests for dashboard pure helpers (window/delta/gap-fill)."""

import sys, types

import pytest
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# utils/dashboard.py imports only stdlib, so no conftest DB needed.
from bcgpt.utils import get_admin_user
from bcgpt.utils.dashboard import (
    resolve_window,
    delta_pct,
    gap_fill,
    assemble_overview,
    assemble_realtime,
)


def test_resolve_window_7d_returns_current_and_previous_equal_window():
    NOW = 1_700_000_000_000  # arbitrary fixed now (ms)
    w = resolve_window("7d", now_ms=NOW)
    assert w["end_ts"] == NOW
    assert w["start_ts"] == NOW - 7 * 86_400_000
    assert w["prev_end_ts"] == w["start_ts"]
    assert w["prev_start_ts"] == w["start_ts"] - 7 * 86_400_000
    # seconds variants for chat/user tables (epoch-seconds)
    assert w["start_ts_s"] == w["start_ts"] // 1000


def test_resolve_window_unknown_period_defaults_to_7d():
    w = resolve_window("bogus", now_ms=1_700_000_000_000)
    assert w["days"] == 7


def test_delta_pct_handles_null_and_zero_prev():
    assert delta_pct(10, 5) == 100.0
    assert delta_pct(5, 10) == -50.0
    assert delta_pct(10, 0) is None
    assert delta_pct(None, 5) is None
    assert delta_pct(10, None) is None


def test_gap_fill_adds_zero_days_and_converts_day_int_to_date():
    # one known point on day D, window covers D-1..D+1
    DAY = 19_628  # epoch-day int
    points = [{"day": DAY, "value": 5}]
    start_ms = (DAY - 1) * 86_400_000
    end_ms = DAY * 86_400_000
    out = gap_fill(points, start_ms, end_ms, value_keys=("value",))
    assert len(out) == 2
    assert out[0]["value"] == 0  # gap-filled previous day
    assert out[1]["value"] == 5
    assert "date" in out[0] and len(out[0]["date"]) == 10  # YYYY-MM-DD


def test_gap_fill_preserves_extra_keys_for_tokens_series():
    DAY = 19_628
    points = [{"day": DAY, "prompt": 1, "completion": 2, "total": 3, "cost": 0.1}]
    out = gap_fill(
        points,
        (DAY - 1) * 86_400_000,
        DAY * 86_400_000,
        value_keys=("prompt", "completion", "total", "cost"),
    )
    assert out[0]["prompt"] == 0 and out[0]["cost"] == 0
    assert out[1]["total"] == 3


# ---------------------------------------------------------------------------
# Task 4: assemble_overview (pure) + /overview router (TestClient)
# ---------------------------------------------------------------------------


def _fakes():
    """Canned helper outputs (shape only) to drive assemble_overview."""
    return {
        "users_total": 120,
        "signups": (8, 5),  # (current, prev)
        "active": (42, 30),
        "chats_new": (350, 300),
        "chats_series": [{"day": 19628, "value": 50}],
        "signups_series": [{"day": 19628, "value": 2}],
        "active_series": [{"day": 19628, "value": 18}],
        "audit_stats": {
            "by_severity": {"INFO": 10, "WARNING": 2, "CRITICAL": 1},
            "recent_critical_count": 1,
            "total_logs": 100,
            "active_users_today": 5,
        },
        "audit_series": [{"day": 19628, "value": 10}],
        "audit_prev": 80,
        "security_stats": {
            "total": 88,
            "by_scanner": {"s1": 50},
            "by_threat_type": {"t1": 30},
            "by_direction": {"inbound": 40, "outbound": 48},
            "blocked_count": 12,
            "shadow_count": 5,
        },
        "security_series": [{"day": 19628, "value": 9}],
        "security_prev": 70,
        "top_security": [{"user_id": "u1", "name": "A", "events": 9, "blocked": 3}],
        "handoff": {"pending": 3, "total": 20, "avg_resolution_ms": 5400000},
        "feedback": {"1": 0, "2": 0, "3": 1, "4": 4, "5": 5, "count": 10, "avg": 4.4},
        # usage (flag-aware) — None when flag off:
        "usage_total": None,
        "usage_prev": None,
        "tokens_series": [],
        "models": [],
        "top_users_usage": [],
    }


def test_assemble_overview_includes_kpis_series_breakdowns_and_flags():
    flags = {
        "token_usage_persist_enabled": False,
        "ai_interaction_audit_enabled": False,
    }
    out = assemble_overview(
        "7d", flags=flags, now_ms=1_700_000_000_000, fetch=lambda key: _fakes()[key]
    )
    assert out["period"] == "7d"
    assert out["flags"] == flags
    # deltas computed
    assert out["kpis"]["chats"]["delta_pct"] == pytest.approx(16.7, abs=0.1)
    assert out["kpis"]["users"]["value"] == 8
    # usage flag-off → available False
    assert out["kpis"]["tokens"]["available"] is False
    assert out["kpis"]["cost"]["available"] is False
    assert out["series"]["tokens_by_day"] == []
    # series gap-filled to 8 days
    assert len(out["series"]["chats_by_day"]) == 8
    # breakdowns present
    assert out["breakdowns"]["audit_by_severity"]["CRITICAL"] == 1


def test_assemble_overview_resilient_to_one_domain_failure():
    flags = {"token_usage_persist_enabled": True, "ai_interaction_audit_enabled": True}

    def fetch(key):
        if key == "security_stats":
            raise RuntimeError("boom")
        return _fakes()[key]

    out = assemble_overview("7d", flags=flags, now_ms=1_700_000_000_000, fetch=fetch)
    # security section degraded but payload intact
    assert out["breakdowns"]["security_by_scanner"] == {}
    assert out["kpis"]["guardrail"]["events"] == 0
    assert out["kpis"]["chats"]["value"] == 350  # other domains still present


def _client(admin=True):
    app = FastAPI()
    from bcgpt.routers import dashboard as dash

    app.include_router(dash.router, prefix="/api/v1/dashboard")
    app.state.config = SimpleNamespace(
        TOKEN_USAGE_PERSIST_ENABLED=False, AI_INTERACTION_AUDIT_ENABLED=False
    )

    async def _fake_user():
        # Mirror the real get_admin_user contract: admins pass through, any
        # other role is rejected with 401. (Always-returning would make the
        # non-admin test unable to observe the gate.)
        if not admin:
            raise HTTPException(status_code=401, detail="not admin")
        return SimpleNamespace(role="admin", id="u")

    app.dependency_overrides[get_admin_user] = _fake_user
    # monkeypatch the table classes the router references
    for name, obj in [
        (
            "TokenUsages",
            SimpleNamespace(
                usage_by_day=lambda *a: [],
                total_usage=lambda *a: {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "count": 0,
                },
                usage_by_model=lambda *a: [],
                usage_by_user=lambda *a: [],
            ),
        ),
        (
            "AuditLogs",
            SimpleNamespace(
                get_stats=lambda: _fakes()["audit_stats"],
                get_timeline_data=lambda **k: [],
                get_anomalies=lambda **k: [],
            ),
        ),
        (
            "SecurityEvents",
            SimpleNamespace(
                get_event_stats=lambda *a: _fakes()["security_stats"],
                get_direction_breakdown=lambda *a: _fakes()["security_stats"][
                    "by_direction"
                ],
                get_timeline_data=lambda *a, **k: [],
                get_top_users=lambda *a, **k: [],
            ),
        ),
        (
            "HandoffRequests",
            # Real helper shape: {total, by_status, avg_resolution_time_ms}.
            # (Route adapts this to {pending, total, avg_resolution_ms}.)
            SimpleNamespace(
                get_handoff_stats=lambda: {
                    "total": 20,
                    "by_status": {"pending": 3, "resolved": 17},
                    "avg_resolution_time_ms": 5400000,
                }
            ),
        ),
        (
            "Users",
            SimpleNamespace(
                get_num_users=lambda: 120,
                signups_by_day=lambda *a: [],
                active_users_by_day=lambda *a: [],
            ),
        ),
        (
            "Chats",
            SimpleNamespace(new_chats_by_day=lambda *a: _fakes()["chats_series"]),
        ),
        (
            "Feedbacks",
            SimpleNamespace(rating_distribution=lambda *a: _fakes()["feedback"]),
        ),
    ]:
        setattr(dash, name, obj)
    return TestClient(app)


def test_overview_route_returns_200_with_payload_for_admin():
    c = _client(admin=True)
    r = c.get("/api/v1/dashboard/overview?period=7d")
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == "7d"
    assert "kpis" in body and "series" in body and "breakdowns" in body
    assert body["flags"]["token_usage_persist_enabled"] is False


def test_overview_route_401_for_non_admin():
    c = _client(admin=False)
    r = c.get("/api/v1/dashboard/overview?period=7d")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Shape-realistic regression test: monkeypatch the table classes with the REAL
# helper return shapes (verified against model source) and assert the router
# fan-out adapts them to the output contract.
# ---------------------------------------------------------------------------


def _realistic_client(now_ms: int):
    """Like _client but fakes return the real helper shapes + usage flag ON."""
    app = FastAPI()
    from bcgpt.routers import dashboard as dash

    app.include_router(dash.router, prefix="/api/v1/dashboard")
    app.state.config = SimpleNamespace(
        TOKEN_USAGE_PERSIST_ENABLED=True, AI_INTERACTION_AUDIT_ENABLED=True
    )

    async def _fake_user():
        return SimpleNamespace(role="admin", id="u")

    app.dependency_overrides[get_admin_user] = _fake_user

    day = now_ms // 86_400_000
    for name, obj in [
        (
            "TokenUsages",
            SimpleNamespace(
                usage_by_day=lambda *a: [
                    {
                        "day": day,
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                        "cost": 0.5,
                        "count": 2,
                    }
                ],
                total_usage=lambda *a: {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "cost": 0.5,
                    "count": 2,
                },
                usage_by_model=lambda *a: [],
                usage_by_user=lambda *a: [],
            ),
        ),
        (
            "AuditLogs",
            SimpleNamespace(
                get_stats=lambda: {
                    "by_severity": {"INFO": 1},
                    "recent_critical_count": 0,
                    "total_logs": 1,
                },
                get_timeline_data=lambda **k: [],
                get_anomalies=lambda **k: [],
            ),
        ),
        (
            "SecurityEvents",
            SimpleNamespace(
                # Real shape: NO by_direction key here (Fix 4 merges it).
                get_event_stats=lambda *a: {
                    "total": 0,
                    "by_scanner": {},
                    "by_severity": {},
                    "by_threat_type": {},
                    "blocked_count": 0,
                    "shadow_count": 0,
                },
                get_direction_breakdown=lambda *a: {"input": 3, "output": 4},
                # Real shape: uses 'total', NOT 'count' (Fix 3).
                get_timeline_data=lambda *a, **k: [
                    {
                        "timestamp": now_ms,
                        "total": 7,
                        "blocked": 1,
                        "by_severity": {},
                    }
                ],
                # Real shape: {user_id, event_count, latest_event} (Fix 5).
                get_top_users=lambda *a, **k: [
                    {"user_id": "u1", "event_count": 9, "latest_event": 1}
                ],
            ),
        ),
        (
            "HandoffRequests",
            # Real shape: {total, by_status, avg_resolution_time_ms} (Fix 1).
            SimpleNamespace(
                get_handoff_stats=lambda: {
                    "total": 5,
                    "by_status": {"pending": 2, "resolved": 3},
                    "avg_resolution_time_ms": 1000.0,
                }
            ),
        ),
        (
            "Users",
            SimpleNamespace(
                get_num_users=lambda: 120,
                signups_by_day=lambda *a: [],
                active_users_by_day=lambda *a: [],
            ),
        ),
        ("Chats", SimpleNamespace(new_chats_by_day=lambda *a: [])),
        (
            "Feedbacks",
            SimpleNamespace(
                rating_distribution=lambda *a: {
                    "1": 0,
                    "2": 0,
                    "3": 0,
                    "4": 0,
                    "5": 0,
                    "count": 0,
                    "avg": 0.0,
                }
            ),
        ),
    ]:
        setattr(dash, name, obj)
    return TestClient(app)


def test_overview_route_adapts_real_helper_shapes(monkeypatch):
    NOW = 1_700_000_000_000  # fixed now (ms) so the day we feed is in-window
    day = NOW // 86_400_000
    from bcgpt.routers import dashboard as dash

    # Pin the router's clock to NOW so the 7d window covers `day`.
    monkeypatch.setattr(dash.time, "time", lambda: NOW / 1000)

    c = _realistic_client(NOW)
    r = c.get("/api/v1/dashboard/overview?period=7d")
    assert r.status_code == 200
    body = r.json()

    # Fix 1 — handoff: by_status.pending + avg_resolution_time_ms adapted.
    assert body["kpis"]["handoff"]["pending"] == 2
    assert body["kpis"]["handoff"]["total"] == 5
    assert body["kpis"]["handoff"]["avg_resolution_ms"] == 1000.0

    # Fix 2 — tokens_by_day: prompt_tokens/total_tokens → bare prompt/total.
    tok = [d for d in body["series"]["tokens_by_day"] if d.get("day") == day][0]
    assert tok["prompt"] == 10
    assert tok["completion"] == 20
    assert tok["total"] == 30
    assert tok["cost"] == 0.5

    # Fix 3 — security timeline: 'total' key tolerated (not just 'count').
    sec = [d for d in body["series"]["security_by_day"] if d.get("day") == day][0]
    assert sec["value"] == 7

    # Fix 4 — security_by_direction merged from get_direction_breakdown.
    assert body["breakdowns"]["security_by_direction"] == {
        "input": 3,
        "output": 4,
    }

    # Fix 5 — top_users_security: event_count → events.
    assert body["top_users_security"][0]["user_id"] == "u1"
    assert body["top_users_security"][0]["events"] == 9


# ---------------------------------------------------------------------------
# Task 5: /realtime router (TestClient) — payload shape + flag-off nulls.
# ---------------------------------------------------------------------------


def test_realtime_route_returns_payload():
    c = _client(admin=True)
    r = c.get("/api/v1/dashboard/realtime")
    assert r.status_code == 200
    body = r.json()
    for k in (
        "active_users_5m",
        "guardrail_events_5m",
        "guardrail_blocks_1m",
        "pending_handoffs",
        "critical_audit_1h",
        "audit_events_1h",
    ):
        assert k in body
    # Fix A regression guard: by_status.pending must be read (not the
    # non-existent top-level "pending"). Old buggy code returned 0 here.
    assert body["pending_handoffs"] == 3
    # flag off → usage-derived fields null
    assert body["ai_responses_1m"] is None
    assert body["tokens_1m"] is None
