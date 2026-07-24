"""Unit tests for query_entity_guard — named-entity preservation invariant.

Self-contained; requires only stdlib re. Run from backend/:

    python -m pytest bcgpt/test/unit/test_query_entity_guard.py -q
"""

import pytest

from bcgpt.utils.query_entity_guard import (
    extract_query_entities,
    entity_appears_in_text,
    validate_rewrite,
    guard_rewrite,
)

# ---------------------------------------------------------------------------
# 1. Korean suffix entity extraction
# ---------------------------------------------------------------------------


def test_extract_samsung_from_vs_query():
    """삼성전자 must be extracted; SK하이닉스 may or may not match suffix table."""
    entities = extract_query_entities("삼성전자 vs SK하이닉스 마진 비교")
    assert "삼성전자" in entities, f"Expected 삼성전자 in {entities}"


# ---------------------------------------------------------------------------
# 2. Two-entity preservation — both present in rewrite
# ---------------------------------------------------------------------------


def test_validate_rewrite_both_entities_preserved():
    original = "삼성전자 마진과 현대차증권 실적"
    rewritten = "삼성전자 영업이익 마진 및 현대차증권 실적 분석"
    assert validate_rewrite(original, rewritten) is True


# ---------------------------------------------------------------------------
# 3. Subject-drop — rewrite silently drops both named entities
# ---------------------------------------------------------------------------


def test_validate_rewrite_subject_drop_fails():
    original = "삼성전자 vs 미래에셋증권 비교"
    rewritten = "증권사 마진 비교"
    # Both Samsung Electronics and Mirae Asset Securities are missing from rewritten → False
    assert validate_rewrite(original, rewritten) is False


# ---------------------------------------------------------------------------
# 4. Stock code (6-digit KRX)
# ---------------------------------------------------------------------------


def test_extract_stock_code():
    entities = extract_query_entities("종목 005930 분석")
    assert "005930" in entities, f"Expected 005930 in {entities}"


def test_validate_rewrite_stock_code_dropped():
    # 005930 is in original but rewritten replaces it with a company name only
    assert validate_rewrite("005930 실적", "삼성전자 실적") is False


# ---------------------------------------------------------------------------
# 5. US ticker extraction and rewrite validation
# ---------------------------------------------------------------------------


def test_extract_us_tickers():
    entities = extract_query_entities("Compare AAPL and MSFT margins")
    assert "AAPL" in entities, f"Expected AAPL in {entities}"
    assert "MSFT" in entities, f"Expected MSFT in {entities}"
    # Stopwords and articles must NOT be in results
    for stopword in ("I", "AI"):
        assert (
            stopword not in entities
        ), f"Stopword {stopword!r} should not appear in {entities}"


def test_validate_rewrite_tickers_preserved():
    assert validate_rewrite("AAPL vs MSFT", "AAPL versus MSFT comparison") is True


# ---------------------------------------------------------------------------
# 6. guard_rewrite fallback and pass-through
# ---------------------------------------------------------------------------


def test_guard_rewrite_fallback():
    result = guard_rewrite("삼성전자 실적", "실적 분석")
    assert result == ("삼성전자 실적", False), f"Unexpected: {result}"


def test_guard_rewrite_pass():
    result = guard_rewrite("삼성전자 실적", "삼성전자 최근 실적 분석")
    assert result == ("삼성전자 최근 실적 분석", True), f"Unexpected: {result}"


# ---------------------------------------------------------------------------
# 7. No-entity query — nothing to protect
# ---------------------------------------------------------------------------


def test_validate_rewrite_no_entities():
    assert (
        validate_rewrite("how does inflation work", "explain inflation mechanics")
        is True
    )


# ---------------------------------------------------------------------------
# 8. guard_rewrite with empty rewrite string
# ---------------------------------------------------------------------------


def test_guard_rewrite_empty_rewrite():
    result = guard_rewrite("삼성전자", "")
    assert result == ("삼성전자", False), f"Unexpected: {result}"
