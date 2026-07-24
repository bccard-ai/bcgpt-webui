"""Deterministic citation-grounding audit. Algorithm re-implemented from open-moai
`lib/docmind/citation-audit.ts` (Apache-2.0). No LLM cost. Tokenization is CJK-aware
(Korean particle stripping + CJK character bigram fallback). Pairs with the LLM
answer-grounder as a cheap deterministic pre-filter.
"""

import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_KR_PARTICLES = re.compile(
    r"(?:은|는|이|가|을|를|의|에|도|에서|로|으로|와|과|에게|부터|까지|만)$"
)

# Covers CJK Unified Ideographs (U+4E00-U+9FFF) + Hangul syllables (AC00-D7A3)
# plus surrounding CJK blocks up to U+9FFF and full-width / Hangul Jamo
_CJK = re.compile(r"[　-鿿가-힣]")

_CITATION_RE = re.compile(r"\[(\d+)\]")

# Factual/numeric sentence detector
_NUMERIC_RE = re.compile(r"\d")

_FINANCE_KW = re.compile(
    r"""(?xi)
    revenue|profit|margin|growth|loss|earnings|dividend|asset|debt|equity|
    liabilit|cash\s*flow|operating|turnover|valuation|ebitda|eps|roe|roa|
    매출|영업이익|순이익|마진|수익률|배당|자산|부채|자본|현금|성장|영업|손익|
    이익|손실|비용|투자|주가|시가총액|당기|전년|분기|반기|연간|증가|감소|
    흑자|적자
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Sentence-ending punctuation (handles EN and KO)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[다요]\.)\s*|[\n\r]+")


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------


def _normalize_token(tok: str) -> str:
    """Lowercase and strip a trailing Korean particle from *tok*."""
    tok = tok.lower()
    tok = _KR_PARTICLES.sub("", tok)
    return tok


def tokenize(text: str) -> set[str]:
    """Whitespace tokens (normalized) PLUS, for any token containing CJK,
    add its character bigrams (and the single char if len==1). Returns a set.

    This is the CJK bigram fallback so unsegmented/particle-attached Korean
    still overlaps. Empty text -> empty set.
    """
    if not text:
        return set()

    tokens: set[str] = set()

    for raw in text.split():
        tok = _normalize_token(raw)
        if not tok:
            continue
        tokens.add(tok)

        # If the *raw* token (before particle-stripping) contains CJK chars,
        # emit character bigrams from the normalised form.
        if _CJK.search(raw):
            chars = tok  # already lowercased, particle stripped
            if len(chars) == 1:
                tokens.add(chars)
            else:
                for i in range(len(chars) - 1):
                    tokens.add(chars[i : i + 2])
                # Also add individual chars so single-char CJK concepts match
                for ch in chars:
                    if _CJK.match(ch):
                        tokens.add(ch)

    return tokens


def jaccard(a: set, b: set) -> float:
    """|a∩b| / |a∪b|; both empty -> 0.0"""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ---------------------------------------------------------------------------
# Sentence utilities
# ---------------------------------------------------------------------------


def split_sentences(text: str) -> list:
    """Split on ., !, ?, newline, and Korean sentence enders (다./요./. ).
    Keep non-empty trimmed sentences.
    """
    # Insert a split marker after Korean enders followed by optional whitespace
    text = re.sub(r"([다요]\.)", r"\1\n", text)
    # Split on end-of-sentence punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+|[\n\r]+", text)
    return [p.strip() for p in parts if p.strip()]


def is_factual_sentence(sent: str) -> bool:
    """True if sentence contains a digit/percent/currency OR a finance keyword
    (EN or KO).
    """
    if _NUMERIC_RE.search(sent):
        return True
    if _FINANCE_KW.search(sent):
        return True
    return False


def extract_citations(sent: str) -> list:
    """Return the [n] integers referenced in the sentence."""
    return [int(m) for m in _CITATION_RE.findall(sent)]


# ---------------------------------------------------------------------------
# Core audit functions
# ---------------------------------------------------------------------------


def compute_citation_coverage(answer: str) -> dict:
    """Among factual sentences, fraction that contain >=1 [n] citation.

    Returns:
        {
            "total_factual": int,
            "cited_factual": int,
            "coverage": float,          # 1.0 if no factual sentences
            "uncited_sentences": list[str],
        }
    """
    sentences = split_sentences(answer)
    factual = [s for s in sentences if is_factual_sentence(s)]

    if not factual:
        return {
            "total_factual": 0,
            "cited_factual": 0,
            "coverage": 1.0,
            "uncited_sentences": [],
        }

    cited = [s for s in factual if extract_citations(s)]
    uncited = [s for s in factual if not extract_citations(s)]

    coverage = len(cited) / len(factual)
    return {
        "total_factual": len(factual),
        "cited_factual": len(cited),
        "coverage": coverage,
        "uncited_sentences": uncited,
    }


def verify_citation_grounding(
    claim: str, evidence: str, threshold: float = 0.08
) -> dict:
    """Jaccard token overlap between claim and evidence. Weak if overlap < threshold.

    Returns {"overlap": float, "grounded": bool}
    """
    overlap = jaccard(tokenize(claim), tokenize(evidence))
    return {"overlap": overlap, "grounded": overlap >= threshold}


def audit_citations(answer: str, sources: list, threshold: float = 0.08) -> dict:
    """Full audit.

    For each factual sentence with citations, look up each cited source by
    1-based index in `sources`, compute grounding overlap vs that source's
    'document'; flag weak-grounding.

    Also report unsupported citation ids (cite index out of range) and unused
    source ids (sources never cited).

    Returns:
        {
            "coverage": float,
            "total_factual": int,
            "cited_factual": int,
            "weak_grounding": list[{"sentence": str, "source_id": int, "overlap": float}],
            "unsupported_ids": list[int],    # cited [n] where n > len(sources) or n < 1
            "unused_source_ids": list[int],  # 1-based source indices never cited
            "uncited_sentences": list[str],
        }
    """
    cov = compute_citation_coverage(answer)

    sentences = split_sentences(answer)
    factual_cited = [
        s for s in sentences if is_factual_sentence(s) and extract_citations(s)
    ]

    n_sources = len(sources)
    weak_grounding: list = []
    unsupported_ids_set: set = set()
    cited_ids_set: set = set()

    for sent in factual_cited:
        for sid in extract_citations(sent):
            if sid < 1 or sid > n_sources:
                unsupported_ids_set.add(sid)
                continue
            cited_ids_set.add(sid)
            doc = sources[sid - 1].get("document", "")
            result = verify_citation_grounding(sent, doc, threshold)
            if not result["grounded"]:
                weak_grounding.append(
                    {
                        "sentence": sent,
                        "source_id": sid,
                        "overlap": result["overlap"],
                    }
                )

    all_source_ids = set(range(1, n_sources + 1))
    unused_source_ids = sorted(all_source_ids - cited_ids_set)

    return {
        "coverage": cov["coverage"],
        "total_factual": cov["total_factual"],
        "cited_factual": cov["cited_factual"],
        "weak_grounding": weak_grounding,
        "unsupported_ids": sorted(unsupported_ids_set),
        "unused_source_ids": unused_source_ids,
        "uncited_sentences": cov["uncited_sentences"],
    }
