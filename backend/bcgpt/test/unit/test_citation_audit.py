"""Unit tests for bcgpt.agent.quality.citation_audit (deterministic, no LLM)."""

import pytest

from bcgpt.agent.quality.citation_audit import (
    audit_citations,
    compute_citation_coverage,
    extract_citations,
    is_factual_sentence,
    jaccard,
    split_sentences,
    tokenize,
    verify_citation_grounding,
)

# ---------------------------------------------------------------------------
# Test 1: Full coverage — both factual sentences are cited
# ---------------------------------------------------------------------------


def test_full_coverage():
    answer = "Revenue grew 20% [1]. Margin rose to 15% [1]."
    sources = [{"document": "Revenue grew 20% and margin rose to 15% this year"}]
    result = compute_citation_coverage(answer)
    assert (
        result["coverage"] == 1.0
    ), f"Expected coverage 1.0, got {result['coverage']}. result={result}"
    assert result["total_factual"] == 2
    assert result["cited_factual"] == 2
    assert result["uncited_sentences"] == []


# ---------------------------------------------------------------------------
# Test 2: Weak grounding flagged — cited source is completely unrelated
# ---------------------------------------------------------------------------


def test_weak_grounding_flagged():
    answer = "Profit was 999 trillion dollars [1]."
    sources = [{"document": "The cat sat on the mat."}]
    result = audit_citations(answer, sources)
    assert result["weak_grounding"], f"Expected non-empty weak_grounding, got {result}"
    assert result["weak_grounding"][0]["source_id"] == 1


# ---------------------------------------------------------------------------
# Test 3: Uncited numeric claim → coverage < 1.0
# ---------------------------------------------------------------------------


def test_uncited_numeric_claim():
    answer = "Revenue grew 20%."
    result = compute_citation_coverage(answer)
    assert (
        result["coverage"] < 1.0
    ), f"Expected coverage < 1.0, got {result['coverage']}"
    # The uncited sentence should appear in uncited_sentences
    assert any(
        "Revenue grew 20%" in s for s in result["uncited_sentences"]
    ), f"Expected 'Revenue grew 20%' in uncited_sentences, got {result['uncited_sentences']}"


# ---------------------------------------------------------------------------
# Test 4: Korean CJK — grounded, full coverage
# ---------------------------------------------------------------------------


def test_korean_cjk_grounded():
    answer = "매출이 20% 증가했습니다 [1]."
    sources = [{"document": "매출이 20% 증가했습니다"}]
    result = audit_citations(answer, sources)
    assert (
        result["coverage"] == 1.0
    ), f"Expected coverage 1.0, got {result['coverage']}. result={result}"
    assert (
        result["weak_grounding"] == []
    ), f"Expected empty weak_grounding, got {result['weak_grounding']}"


# ---------------------------------------------------------------------------
# Test 5: Unsupported citation id (out of range)
# ---------------------------------------------------------------------------


def test_unsupported_citation_id():
    answer = "Profit rose 10% [3]."
    sources = [{"document": "Profit rose by 10 percent last quarter."}]
    result = audit_citations(answer, sources)
    assert result["unsupported_ids"] == [
        3
    ], f"Expected unsupported_ids=[3], got {result['unsupported_ids']}"


# ---------------------------------------------------------------------------
# Test 6: Unused source id
# ---------------------------------------------------------------------------


def test_unused_source_id():
    answer = "Revenue grew 20% [1]."
    sources = [
        {"document": "Revenue grew 20% this year."},
        {"document": "Margin improved significantly."},
    ]
    result = audit_citations(answer, sources)
    assert (
        2 in result["unused_source_ids"]
    ), f"Expected 2 in unused_source_ids, got {result['unused_source_ids']}"


# ---------------------------------------------------------------------------
# Test 7: Non-factual sentences are ignored
# ---------------------------------------------------------------------------


def test_non_factual_ignored():
    answer = "Hello there. How are you?"
    result = compute_citation_coverage(answer)
    assert (
        result["total_factual"] == 0
    ), f"Expected total_factual=0, got {result['total_factual']}"
    assert result["coverage"] == 1.0, f"Expected coverage=1.0, got {result['coverage']}"


# ---------------------------------------------------------------------------
# Test 8: tokenize CJK bigram and jaccard identity
# ---------------------------------------------------------------------------


def test_tokenize_cjk_bigram():
    tokens = tokenize("매출이")
    assert (
        "매출" in tokens
    ), f"Expected '매출' bigram in tokenize('매출이'), got {tokens}"


def test_jaccard_identity():
    a = tokenize("매출 증가")
    b = tokenize("매출 증가")
    assert (
        jaccard(a, b) == 1.0
    ), f"Expected jaccard=1.0 for identical sets, got {jaccard(a, b)}"


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_jaccard_empty():
    assert jaccard(set(), set()) == 0.0


def test_jaccard_disjoint():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial():
    score = jaccard({"a", "b"}, {"b", "c"})
    assert abs(score - 1 / 3) < 1e-9


def test_tokenize_empty():
    assert tokenize("") == set()


def test_extract_citations_multiple():
    assert extract_citations("See [1] and [2] for details.") == [1, 2]


def test_extract_citations_none():
    assert extract_citations("No citations here.") == []


def test_is_factual_with_digit():
    assert is_factual_sentence("Revenue grew 20%.")
    assert not is_factual_sentence("Hello world.")


def test_is_factual_finance_kw_en():
    assert is_factual_sentence("The margin improved significantly.")


def test_is_factual_finance_kw_ko():
    assert is_factual_sentence("영업이익이 증가했습니다.")


def test_split_sentences_basic():
    sents = split_sentences("Hello. World! How are you?")
    assert len(sents) >= 2


def test_split_sentences_korean():
    sents = split_sentences("매출이 증가했습니다. 영업이익도 늘었습니다.")
    assert any("매출" in s for s in sents)


def test_verify_citation_grounding_strong():
    result = verify_citation_grounding(
        "Revenue grew 20%",
        "Revenue grew 20% this quarter",
    )
    assert result["grounded"] is True


def test_verify_citation_grounding_weak():
    result = verify_citation_grounding(
        "Profit was 999 trillion dollars",
        "The cat sat on the mat",
    )
    assert result["grounded"] is False


def test_audit_no_sources():
    answer = "Revenue grew 20% [1]."
    result = audit_citations(answer, [])
    assert result["unsupported_ids"] == [1]
    assert result["unused_source_ids"] == []


def test_audit_full_pipeline():
    answer = "Revenue grew 20% [1]. The sky is blue."
    sources = [{"document": "Revenue increased by 20 percent year over year."}]
    result = audit_citations(answer, sources)
    # "The sky is blue." is non-factual → only 1 factual sentence
    assert result["total_factual"] == 1
    assert result["cited_factual"] == 1
    assert result["coverage"] == 1.0
    assert result["unused_source_ids"] == []
