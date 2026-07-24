"""Unit tests for the ingestion-time chunk quality scorer."""

from bcgpt.retrieval.chunk_quality import (
    score_chunk,
    filter_chunks,
    _is_cjk_heavy,
)


def test_normal_english_accepted():
    text = (
        "The quick brown fox jumps over the lazy dog near the riverbank "
        "in the early morning light."
    )
    r = score_chunk(text)
    assert r["verdict"] == "accept"
    assert r["score"] > 0.5


def test_empty_rejected():
    for t in ("", "   ", "\n\t  \n"):
        r = score_chunk(t)
        assert r["verdict"] == "reject"
        assert r["score"] == 0.0


def test_too_short_rejected():
    r = score_chunk("hi")
    assert r["verdict"] == "reject"
    assert any("short" in reason for reason in r["reasons"])


def test_repetitive_rejected():
    text = " ".join(["spam"] * 15)  # 74 chars, clearly over min length
    r = score_chunk(text)
    assert r["verdict"] == "reject"
    assert any("repetitive" in reason for reason in r["reasons"])


def test_symbol_soup_rejected():
    text = "@#$%^&*()_+=-{}[]|\\<>~`@#$%^&*()_+=-{}[]|\\<>~`@#$%^&*()"
    r = score_chunk(text)
    assert r["verdict"] == "reject"
    assert any("information" in reason or "symbol" in reason for reason in r["reasons"])


def test_cjk_heavy_detection_and_accept():
    assert (
        _is_cjk_heavy("이것은 한국어 문장입니다 충분히 긴 내용을 담고 있습니다") is True
    )
    assert _is_cjk_heavy("this is english text only") is False

    korean = (
        "이것은 한국어로 작성된 충분히 긴 문단입니다. 다양한 단어와 내용을 "
        "포함하고 있으며 검색 품질 평가를 위한 테스트 목적으로 사용됩니다."
    )
    r = score_chunk(korean)
    assert r["metrics"]["cjk_heavy"] is True
    # Must NOT be rejected merely for having few whitespace 'words'.
    assert r["verdict"] in ("accept", "review")
    assert r["verdict"] != "reject"


def test_filter_chunks_drops_rejected():
    texts = [
        "good long english sentence here with enough characters to pass cleanly",
        "hi",
    ]
    out = filter_chunks(texts)
    assert texts[0] in out["accepted_texts"]
    assert "hi" not in out["accepted_texts"]
    assert any(r["index"] == 1 for r in out["rejected"])


def test_filter_chunks_keeps_review():
    borderline = "This is a borderline chunk just over the minimum length."  # ~56 chars
    r = score_chunk(borderline)
    assert r["verdict"] == "review"  # borderline by length
    out = filter_chunks([borderline])
    assert borderline in out["accepted_texts"]
    assert out["rejected"] == []
    assert 0 in out["reviewed"]


def test_filter_chunks_metadata_alignment():
    texts = [
        "good long english sentence here with enough characters to pass cleanly",
        "hi",
        "another sufficiently long english sentence that should be accepted fine",
    ]
    metas = [{"i": 0}, {"i": 1}, {"i": 2}]
    out = filter_chunks(texts, metas)
    assert len(out["accepted_texts"]) == len(out["accepted_metadatas"])
    # index 1 ("hi") dropped, so metadata {"i":1} must be absent.
    assert {"i": 1} not in out["accepted_metadatas"]
    assert [m["i"] for m in out["accepted_metadatas"]] == [0, 2]
