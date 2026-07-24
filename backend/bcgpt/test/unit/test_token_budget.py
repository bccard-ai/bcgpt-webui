"""Unit tests for the per-user token budget limiter (in-memory path)."""

from bcgpt.utils.per_user_rate_limit import TokenBudgetLimiter


def _fresh():
    lim = TokenBudgetLimiter()
    # Force the in-memory path regardless of any ambient REDIS_URL.
    lim._redis_tried = True
    lim._redis = None
    return lim


def test_no_caps_always_allowed():
    lim = _fresh()
    ok, msg = lim.check_token_budget("user:1", daily_cap=0, per_min_cap=0)
    assert ok is True and msg is None
    lim.record_token_usage("user:1", 10_000_000)
    ok, msg = lim.check_token_budget("user:1", 0, 0)
    assert ok is True


def test_daily_cap_blocks_after_exceed():
    lim = _fresh()
    ok, _ = lim.check_token_budget("user:1", daily_cap=100)
    assert ok is True  # nothing consumed yet
    lim.record_token_usage("user:1", 100)
    ok, msg = lim.check_token_budget("user:1", daily_cap=100)
    assert ok is False
    assert "Daily token budget exceeded" in msg


def test_per_minute_cap_blocks():
    lim = _fresh()
    lim.record_token_usage("user:2", 50)
    ok, msg = lim.check_token_budget("user:2", per_min_cap=50)
    assert ok is False
    assert "Per-minute token budget exceeded" in msg


def test_get_usage_accumulates():
    lim = _fresh()
    lim.record_token_usage("user:3", 30)
    lim.record_token_usage("user:3", 20)
    minute_used, day_used = lim.get_usage("user:3")
    assert minute_used == 50
    assert day_used == 50


def test_isolation_between_clients():
    lim = _fresh()
    lim.record_token_usage("user:a", 1000)
    ok, _ = lim.check_token_budget("user:b", daily_cap=100)
    assert ok is True  # user:b unaffected by user:a


def test_zero_and_negative_tokens_ignored():
    lim = _fresh()
    lim.record_token_usage("user:4", 0)
    lim.record_token_usage("user:4", -5)
    minute_used, day_used = lim.get_usage("user:4")
    assert minute_used == 0 and day_used == 0
