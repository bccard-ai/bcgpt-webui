"""Deterministic document structural-quality score (DocReward-style heuristic).
Re-implemented from open-moai `lib/docmind/doc-quality-score.ts` (Apache-2.0).
No LLM cost. Scores long-form markdown output on structure; pairs with the
citation audit as an output-quality gate.
"""

import re

_WEIGHTS = {
    "heading": 0.30,
    "section": 0.20,
    "emphasis": 0.15,
    "list": 0.15,
    "whitespace": 0.20,
}

_SUGGESTIONS = {
    "heading": "Add or fix markdown heading hierarchy (#, ##, ###).",
    "section": "Balance section lengths.",
    "emphasis": "Use bold/italic to emphasize key points.",
    "list": "Use bullet or numbered lists for enumerable content.",
    "whitespace": "Separate paragraphs with blank lines for readability.",
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)
_BOLD_RE = re.compile(r"(\*\*[^*\n]+\*\*|__[^_\n]+__)")
_ITALIC_RE = re.compile(
    r"(?<!\*)\*(?!\*)([^*\n]+)(?<!\*)\*(?!\*)|(?<!_)_(?!_)([^_\n]+)(?<!_)_(?!_)"
)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)


def _score_headings(text: str) -> float:
    """Reward presence of markdown headings (#, ##, ###) AND proper hierarchy (no jumping
    from # to ### without ##). 0 if no headings; ~1 if multiple well-nested headings."""
    matches = _HEADING_RE.findall(text)
    if not matches:
        return 0.0

    levels = [len(m) for m in matches]
    count = len(levels)

    # Base score from heading count (saturates at 5+)
    count_score = min(count / 5.0, 1.0)

    # Hierarchy penalty: detect skips (e.g. h1 -> h3 without h2)
    skip_penalty = 0.0
    for i in range(1, len(levels)):
        jump = levels[i] - levels[i - 1]
        if jump > 1:
            skip_penalty += (jump - 1) * 0.15

    hierarchy_score = max(0.0, 1.0 - skip_penalty)

    # Variety bonus: reward using more than one heading level
    variety = len(set(levels))
    variety_score = min(variety / 3.0, 1.0)

    return min(1.0, (count_score * 0.5 + hierarchy_score * 0.3 + variety_score * 0.2))


def _score_sections(text: str) -> float:
    """Split into sections by headings; reward balanced section lengths (low variance in
    words-per-section). If <2 sections return 0.5 (neutral). Reward 2+ roughly-balanced sections.
    """
    parts = _HEADING_RE.split(text)
    # _HEADING_RE.split on the full text gives alternating non-heading / heading-group pieces.
    # Simpler: split on heading lines directly.
    sections = re.split(r"(?m)^#{1,6}\s+\S[^\n]*\n?", text)
    # Drop leading empty section before first heading
    sections = [s.strip() for s in sections if s.strip()]

    if len(sections) < 2:
        return 0.5

    word_counts = [len(re.findall(r"\S+", s)) for s in sections]
    total = sum(word_counts)
    if total == 0:
        return 0.5

    mean = total / len(word_counts)
    if mean == 0:
        return 0.5

    # Coefficient of variation (lower = more balanced)
    variance = sum((w - mean) ** 2 for w in word_counts) / len(word_counts)
    std_dev = variance**0.5
    cv = std_dev / mean  # 0 = perfectly balanced

    # Map CV to score: CV=0 -> 1.0; CV>=2 -> 0.0
    balance_score = max(0.0, 1.0 - cv / 2.0)

    # Also reward having more sections (up to 5)
    count_score = min(len(sections) / 5.0, 1.0)

    return min(1.0, balance_score * 0.7 + count_score * 0.3)


def _score_emphasis(text: str) -> float:
    """Reward presence of bold (**x**/__x__) or italic (*x*/_x_) emphasis, scaled by document
    length. Cap at 1.0; 0 if none."""
    bold_count = len(_BOLD_RE.findall(text))
    italic_count = len(_ITALIC_RE.findall(text))
    total_emphasis = bold_count + italic_count

    if total_emphasis == 0:
        return 0.0

    word_count = len(re.findall(r"\S+", text))
    if word_count == 0:
        return 0.0

    # Expect roughly 1 emphasis per 50 words for a good score
    ratio = total_emphasis / (word_count / 50.0)
    return min(1.0, ratio)


def _score_lists(text: str) -> float:
    """Reward presence of bullet (-, *, +) or numbered (1.) list items. 0 if none, ~1 if several."""
    bullet_count = len(_BULLET_RE.findall(text))
    numbered_count = len(_NUMBERED_RE.findall(text))
    total = bullet_count + numbered_count

    if total == 0:
        return 0.0

    # Saturate at 5 list items
    return min(1.0, total / 5.0)


def _score_whitespace(text: str) -> float:
    """Reward paragraph separation (blank lines between blocks); penalize a single wall of text.
    Ratio of blank-line-separated blocks to total content lines."""
    lines = text.splitlines()
    if not lines:
        return 0.0

    content_lines = [l for l in lines if l.strip()]
    if not content_lines:
        return 0.0

    # Count blank-line-separated blocks
    blocks = re.split(r"\n\s*\n", text.strip())
    blocks = [b for b in blocks if b.strip()]
    num_blocks = len(blocks)

    if num_blocks <= 1:
        # Wall of text: single block
        return 0.0

    # Ratio: more blocks relative to content lines = better separation
    # Normalise: expect ~1 block per 5 content lines for a score of 1
    ratio = num_blocks / max(len(content_lines) / 5.0, 1.0)
    return min(1.0, ratio)


def score_document(text: str) -> dict:
    """Compute the overall structural quality score.

    Returns:
      {"score": float (0-100),
       "dimensions": {"heading": float, "section": float, "emphasis": float,
                      "list": float, "whitespace": float},  # each 0-1
       "suggestions": list[str]}   # one suggestion per dimension whose sub-score < 0.7
    Empty/whitespace text -> score 0.0, all dims 0.0, suggestions for all.
    Never raises.
    """
    try:
        if not text or not text.strip():
            return {
                "score": 0.0,
                "dimensions": {k: 0.0 for k in _WEIGHTS},
                "suggestions": [_SUGGESTIONS[k] for k in _WEIGHTS],
            }

        dims = {
            "heading": _score_headings(text),
            "section": _score_sections(text),
            "emphasis": _score_emphasis(text),
            "list": _score_lists(text),
            "whitespace": _score_whitespace(text),
        }

        # Clamp each dimension to [0, 1]
        dims = {k: max(0.0, min(1.0, v)) for k, v in dims.items()}

        raw = sum(_WEIGHTS[k] * dims[k] for k in _WEIGHTS)
        score = round(100.0 * raw, 10)  # keep as float, rounded to avoid float noise
        score = max(0.0, min(100.0, score))

        suggestions = [_SUGGESTIONS[k] for k, v in dims.items() if v < 0.7]

        return {"score": score, "dimensions": dims, "suggestions": suggestions}

    except Exception:
        return {
            "score": 0.0,
            "dimensions": {k: 0.0 for k in _WEIGHTS},
            "suggestions": [_SUGGESTIONS[k] for k in _WEIGHTS],
        }
