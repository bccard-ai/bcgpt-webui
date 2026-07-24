"""Named-entity preservation invariant for query rewriting. Algorithm re-implemented from open-moai
`lib/websearch/query-rewriter.ts` extractExplicitQueryEntities/entityAppearsInText (Apache-2.0).
Korean chaebal/finance entity patterns. Ensures LLM rewrites don't silently drop subjects.
"""

import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Korean company/finance suffix patterns — matches a hangul/latin prefix + one of the known suffixes.
_KR_ENTITY_SUFFIX = re.compile(
    r"[가-힣A-Za-z]{1,12}"
    r"(?:금융지주|손해보험|자산운용|중공업|디스플레이|바이오|전자|증권|화학|그룹|지주|은행|카드|생명|화재|캐피탈|건설|제약|통신|전력)"
)

# KRX 6-digit stock codes
_KR_STOCK_CODE = re.compile(r"\b\d{6}\b")

# Uppercase tickers (1-5 caps only; filtered against stopwords below)
_US_TICKER = re.compile(r"\b[A-Z]{1,5}\b")

# Quoted strings (various quote styles, 2-40 chars inside)
_QUOTED = re.compile(r"""[\"'“”‘’]([^\"'“”‘’]{2,40})[\"'“”‘’]""")

# Capitalised English multi-word proper nouns
_PROPER_EN = re.compile(r"\b[A-Z][a-zA-Z0-9&.]+(?:\s+[A-Z][a-zA-Z0-9&.]+)*\b")

# Stopwords that look like tickers but aren't company names
_TICKER_STOPWORDS: frozenset = frozenset(
    {
        "I",
        "A",
        "AI",
        "CEO",
        "CFO",
        "IPO",
        "ETF",
        "GDP",
        "USD",
        "KRW",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "US",
        "UK",
        "EU",
        "VS",
        "AND",
        "OR",
        "THE",
    }
)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _normalise_ws(text: str) -> str:
    """Collapse internal whitespace to a single space and strip."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_query_entities(query: str) -> list[str]:
    """Extract distinct explicit named entities from a query.

    Extraction order / priority:
    1. Korean suffix-company names (e.g. 삼성전자, 미래에셋증권)
    2. 6-digit KRX stock codes (e.g. 005930)
    3. Uppercase tickers excluding _TICKER_STOPWORDS (e.g. AAPL, MSFT)
    4. Quoted strings (e.g. "삼성 바이오로직스")
    5. Capitalised English proper-noun phrases (len>=3 chars, not a solo stopword)

    De-duplicates preserving first-seen order. Empty / very-short (<2 chars) query → [].
    """
    if not query or len(query.strip()) < 2:
        return []

    seen: dict[str, None] = {}  # ordered-set via insertion-ordered dict

    def _add(entity: str) -> None:
        key = entity.strip()
        if key:
            seen.setdefault(key, None)

    # 1. Korean suffix companies
    for m in _KR_ENTITY_SUFFIX.finditer(query):
        _add(m.group())

    # 2. Stock codes
    for m in _KR_STOCK_CODE.finditer(query):
        _add(m.group())

    # 3. Uppercase tickers (exclude stopwords and pure-digit strings)
    for m in _US_TICKER.finditer(query):
        token = m.group()
        if token not in _TICKER_STOPWORDS and not token.isdigit():
            _add(token)

    # 4. Quoted strings
    for m in _QUOTED.finditer(query):
        _add(m.group(1))

    # 5. Capitalised English proper nouns (len >= 3, not solely a stopword)
    for m in _PROPER_EN.finditer(query):
        phrase = m.group()
        if len(phrase) >= 3 and phrase not in _TICKER_STOPWORDS:
            _add(phrase)

    return list(seen.keys())


def entity_appears_in_text(entity: str, text: str) -> bool:
    """Case-insensitive, whitespace-normalised containment check.

    Returns True if `entity` (or its compact / whitespace-collapsed form)
    appears anywhere in `text`.
    """
    if not entity or not text:
        return False
    norm_entity = _normalise_ws(entity).lower()
    norm_text = _normalise_ws(text).lower()
    # Direct containment (handles most cases)
    if norm_entity in norm_text:
        return True
    # Also try compact (no spaces) — useful for quoted multi-word vs joined form
    compact_entity = norm_entity.replace(" ", "")
    compact_text = norm_text.replace(" ", "")
    return compact_entity in compact_text


def validate_rewrite(original: str, rewritten: str) -> bool:
    """True iff EVERY entity extracted from `original` appears in `rewritten`.

    If `original` has no entities, returns True (nothing to protect).
    Empty `rewritten` with non-empty entities → False.
    """
    entities = extract_query_entities(original)
    if not entities:
        return True
    if not rewritten or not rewritten.strip():
        return False
    return all(entity_appears_in_text(e, rewritten) for e in entities)


def guard_rewrite(original: str, rewritten: str) -> tuple[str, bool]:
    """Return (rewritten, True) if validate_rewrite passes, else (original, False).

    Caller is responsible for logging the fallback case.
    A falsy `rewritten` always triggers the fallback.
    """
    if not rewritten:
        return (original, False)
    if validate_rewrite(original, rewritten):
        return (rewritten, True)
    return (original, False)
