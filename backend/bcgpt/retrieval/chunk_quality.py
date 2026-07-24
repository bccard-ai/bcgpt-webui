"""Ingestion-time chunk quality scorer (accept/review/reject).

Re-implemented from open-moai chunk-quality heuristics (Apache-2.0). CJK
script-aware (a Korean chunk has few whitespace 'words' but many chars, so
word-count thresholds are wrong for it). Mitigates garbage-in/garbage-out in
the RAG ingest path.
"""

from __future__ import annotations

import re

# CJK ranges: CJK symbols/kana, CJK ideographs, Hangul, full-width forms.
_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿가-힣＀-￯]")


def _is_cjk_heavy(text: str) -> bool:
    """True if >= 30% of non-space chars are CJK — switch to char-based metrics."""
    if not text:
        return False
    non_space = [c for c in text if not c.isspace()]
    if not non_space:
        return False
    cjk = sum(1 for c in non_space if _CJK.match(c))
    return (cjk / len(non_space)) >= 0.30


def _alnum_ratio(text: str) -> float:
    """Ratio of alphanumeric + CJK chars to total chars (detects symbol soup).

    Empty -> 0.0.
    """
    if not text:
        return 0.0
    informative = sum(1 for c in text if c.isalnum() or _CJK.match(c))
    return informative / len(text)


def _tokens(text: str, cjk_heavy: bool) -> list[str]:
    """Tokenize for repetition analysis: CJK char-bigrams when CJK-heavy, else words."""
    if cjk_heavy:
        compact = re.sub(r"\s+", "", text)
        if len(compact) < 2:
            return [compact] if compact else []
        return [compact[i : i + 2] for i in range(len(compact) - 1)]
    return text.split()


def _repetition_ratio(text: str) -> float:
    """1 - (unique tokens / total tokens). High = very repetitive.

    Empty / single-token -> 0.0.
    """
    cjk_heavy = _is_cjk_heavy(text)
    toks = _tokens(text, cjk_heavy)
    if len(toks) <= 1:
        return 0.0
    return 1.0 - (len(set(toks)) / len(toks))


def score_chunk(
    text: str,
    *,
    min_chars: int = 50,
    max_repetition: float = 0.7,
    min_alnum: float = 0.35,
) -> dict:
    """Score a chunk and bucket it as accept / review / reject.

    Heuristics: empty -> reject; too short / too repetitive / low-information ->
    reject; borderline (near a threshold) -> review; else accept.

    Returns ``{"verdict", "score", "reasons", "metrics"}`` where ``score`` is a
    0-1 composite (1 = best). Never raises.
    """
    try:
        stripped = (text or "").strip()
        length = len(stripped)
        cjk_heavy = _is_cjk_heavy(text or "")
        metrics = {
            "length": length,
            "repetition": 0.0,
            "alnum_ratio": 0.0,
            "cjk_heavy": cjk_heavy,
        }

        if not stripped:
            return {
                "verdict": "reject",
                "score": 0.0,
                "reasons": ["empty"],
                "metrics": metrics,
            }

        rep = _repetition_ratio(text)
        alnum = _alnum_ratio(text)
        metrics["repetition"] = round(rep, 4)
        metrics["alnum_ratio"] = round(alnum, 4)

        reject_reasons: list[str] = []
        if length < min_chars:
            reject_reasons.append(f"too short ({length} < {min_chars} chars)")
        if rep > max_repetition:
            reject_reasons.append(f"too repetitive (repetition {rep:.2f})")
        if alnum < min_alnum:
            reject_reasons.append(f"low information / symbol soup (alnum {alnum:.2f})")

        # Composite score (computed regardless of verdict).
        length_score = min(1.0, length / (min_chars * 2))
        rep_score = max(0.0, 1.0 - rep)
        alnum_score = min(1.0, alnum / 0.7)
        score = round((length_score + rep_score + alnum_score) / 3.0, 4)

        if reject_reasons:
            return {
                "verdict": "reject",
                "score": score,
                "reasons": reject_reasons,
                "metrics": metrics,
            }

        review_reasons: list[str] = []
        if length < 1.5 * min_chars:
            review_reasons.append("short-ish (near minimum length)")
        if rep > (max_repetition - 0.15):
            review_reasons.append("somewhat repetitive")
        if alnum < (min_alnum + 0.1):
            review_reasons.append("borderline information density")

        if review_reasons:
            return {
                "verdict": "review",
                "score": score,
                "reasons": review_reasons,
                "metrics": metrics,
            }

        return {
            "verdict": "accept",
            "score": score,
            "reasons": [],
            "metrics": metrics,
        }
    except Exception:
        # Fail-open to 'review' so a scorer bug never silently drops content.
        return {
            "verdict": "review",
            "score": 0.0,
            "reasons": ["scorer error"],
            "metrics": {
                "length": 0,
                "repetition": 0.0,
                "alnum_ratio": 0.0,
                "cjk_heavy": False,
            },
        }


def filter_chunks(texts: list, metadatas: list | None = None, **kwargs) -> dict:
    """Score a parallel list of texts (+ optional metadatas) and split them.

    ``accept`` AND ``review`` verdicts are KEPT (review is flagged, not dropped);
    only ``reject`` is dropped. ``kwargs`` are forwarded to :func:`score_chunk`.
    Preserves order. Never raises.

    Returns ``{"accepted_texts", "accepted_metadatas", "rejected", "reviewed"}``.
    """
    accepted_texts: list = []
    accepted_metadatas: list = []
    rejected: list[dict] = []
    reviewed: list[int] = []
    has_meta = metadatas is not None

    for i, text in enumerate(texts or []):
        result = score_chunk(text, **kwargs)
        verdict = result["verdict"]
        if verdict == "reject":
            rejected.append(
                {"index": i, "verdict": verdict, "reasons": result["reasons"]}
            )
            continue
        if verdict == "review":
            reviewed.append(i)
        accepted_texts.append(text)
        if has_meta and i < len(metadatas):
            accepted_metadatas.append(metadatas[i])

    return {
        "accepted_texts": accepted_texts,
        "accepted_metadatas": accepted_metadatas,
        "rejected": rejected,
        "reviewed": reviewed,
    }
