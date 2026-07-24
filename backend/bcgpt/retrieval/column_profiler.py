"""Column data-type profiler (currency/percent/date/number/boolean/text) via majority vote.
Re-implemented from open-moai data-analysis column profiling (Apache-2.0).
Pure stdlib; gives the LLM structured column context before it reasons over tabular data.
"""

import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOLS = r"[\$€£¥₩]"
_CURRENCY_WORDS = r"(?:원|KRW|USD|EUR|GBP|JPY)"

# Currency: optional leading symbol/word, number body, optional trailing symbol/word
# e.g. $1,234.56  ₩1,000  KRW 1,000  USD 1,234
_CURRENCY_LEADING = re.compile(
    r"^\s*(?:"
    + _CURRENCY_SYMBOLS
    + r"|"
    + _CURRENCY_WORDS
    + r")\s*-?[\d,]+(?:\.\d+)?\s*$",
    re.IGNORECASE,
)
_CURRENCY_TRAILING = re.compile(
    r"^\s*-?[\d,]+(?:\.\d+)?\s*(?:"
    + _CURRENCY_SYMBOLS
    + r"|"
    + _CURRENCY_WORDS
    + r")\s*$",
    re.IGNORECASE,
)

# Percent: number (possibly with sign/parens) followed by % or the Korean word for percent
_PERCENT_RE = re.compile(
    r"^\s*-?[\d,]+(?:\.\d+)?\s*(?:%|퍼센트)\s*$",
    re.IGNORECASE,
)

# Boolean keywords
_BOOLEAN_VALUES = frozenset(["true", "false", "yes", "no", "y", "n", "예", "아니오"])

# Date formats (ordered most-specific first). Values must parse as real
# calendar dates; regex shape alone is not enough (e.g. 2026-13-45).
_DATE_FMTS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y.%m.%d",
]

_KOREAN_DATE_RE = re.compile(r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일$")

# Datetime patterns (for parseable common formats via strptime)
_DATETIME_FMTS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
]

# Number: int/float with optional thousands separators, optional leading minus or parens-negative
_NUMBER_RE = re.compile(r"^\s*(?:\([\d,]+(?:\.\d+)?\)|-?[\d,]+(?:\.\d+)?)\s*$")


def _is_valid_date(s: str) -> bool:
    for fmt in _DATE_FMTS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            pass

    match = _KOREAN_DATE_RE.match(s)
    if match:
        try:
            year, month, day = (int(group) for group in match.groups())
            datetime(year, month, day)
            return True
        except ValueError:
            pass

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_cell_type(value) -> str:
    """Classify a single cell into one of: 'currency','percent','date','number','boolean','empty','text'.
    - None or blank/whitespace -> 'empty'
    - currency: leading/trailing currency symbol ($ € £ ¥ ₩ or '원'/'KRW'/'USD') around a number,
      with optional thousands separators -> 'currency'
    - percent: number followed by '%' (or '퍼센트') -> 'percent'
    - boolean: true/false/yes/no/y/n/예/아니오 (case-insensitive) -> 'boolean'
    - date: ISO (YYYY-MM-DD), YYYY/MM/DD, DD-MM-YYYY, YYYY년 MM월 DD일, or parseable common formats -> 'date'
    - number: int/float incl. thousands separators and negatives/parentheses-negatives -> 'number'
    - otherwise -> 'text'
    Never raises."""
    try:
        if value is None:
            return "empty"
        s = str(value).strip()
        if not s:
            return "empty"

        # Currency (more specific than number)
        if _CURRENCY_LEADING.match(s) or _CURRENCY_TRAILING.match(s):
            return "currency"

        # Percent (more specific than number)
        if _PERCENT_RE.match(s):
            return "percent"

        # Boolean
        if s.lower() in _BOOLEAN_VALUES:
            return "boolean"

        # Date (calendar-validated date-only formats)
        if _is_valid_date(s):
            return "date"

        # Date (strptime fallback)
        for fmt in _DATETIME_FMTS:
            try:
                datetime.strptime(s, fmt)
                return "date"
            except ValueError:
                pass

        # Number
        if _NUMBER_RE.match(s):
            # Reject bare commas-only or edge cases like "1,2,3" (non-standard grouping)
            # Standard thousands: groups of 3 after optional leading digits
            # Strip sign/parens to check grouping
            inner = s.strip().lstrip("(").rstrip(")")
            inner = inner.lstrip("-").strip()
            if "," in inner:
                parts = inner.split(".")
                int_part = parts[0]
                groups = int_part.split(",")
                # First group can be 1-3 digits; rest must be exactly 3
                if all(len(g) == 3 for g in groups[1:]) and 1 <= len(groups[0]) <= 3:
                    return "number"
                # No comma grouping at all after split means it's fine (shouldn't reach here)
            else:
                return "number"

        return "text"
    except Exception:
        return "text"


def profile_column(values: list) -> dict:
    """Majority-vote the type of a column from its cell values (ignoring 'empty' cells for the vote,
    but counting them).
    Returns {"type": str, "confidence": float, "counts": dict[str,int], "non_empty": int, "empty": int}
    confidence = votes_for_winner / non_empty (1.0 if all non-empty agree; 'text' if column is all empty).
    """
    counts: dict[str, int] = {}
    empty_count = 0

    for v in values:
        t = detect_cell_type(v)
        if t == "empty":
            empty_count += 1
        else:
            counts[t] = counts.get(t, 0) + 1

    non_empty = sum(counts.values())

    if non_empty == 0:
        return {
            "type": "text",
            "confidence": 1.0,
            "counts": counts,
            "non_empty": 0,
            "empty": empty_count,
        }

    winner = max(counts, key=lambda k: counts[k])
    confidence = counts[winner] / non_empty

    return {
        "type": winner,
        "confidence": confidence,
        "counts": counts,
        "non_empty": non_empty,
        "empty": empty_count,
    }


def profile_table(rows: list, headers: list | None = None) -> dict:
    """Profile every column of a table.
    `rows` is a list of rows; each row is a list (positional) OR a dict (keyed by header).
    If rows are lists and headers given, key results by header; else key by column index as str.
    Returns {"columns": {col_key: <profile_column result>, ...}, "row_count": int, "column_count": int}.
    Handles ragged rows (missing cells treated as empty). Empty table -> {"columns": {}, "row_count":0, "column_count":0}.
    """
    if not rows:
        return {"columns": {}, "row_count": 0, "column_count": 0}

    row_count = len(rows)

    # Determine if rows are dicts or lists
    first = rows[0]
    if isinstance(first, dict):
        # Collect all keys across all rows
        all_keys: list = []
        seen: set = set()
        for row in rows:
            for k in row:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        columns: dict[str, list] = {k: [] for k in all_keys}
        for row in rows:
            for k in all_keys:
                columns[k].append(row.get(k, None))
        column_count = len(all_keys)
        col_profiles = {k: profile_column(columns[k]) for k in all_keys}
    else:
        # List rows — find max width
        max_width = max(
            (len(row) for row in rows if hasattr(row, "__len__")), default=0
        )
        column_count = max_width

        if headers and len(headers) >= max_width:
            col_keys = [str(h) for h in headers[:max_width]]
        else:
            col_keys = [str(i) for i in range(max_width)]

        columns_list: list[list] = [[] for _ in range(max_width)]
        for row in rows:
            for i in range(max_width):
                try:
                    columns_list[i].append(row[i])
                except (IndexError, KeyError):
                    columns_list[i].append(None)

        col_profiles = {
            col_keys[i]: profile_column(columns_list[i]) for i in range(max_width)
        }

    return {
        "columns": col_profiles,
        "row_count": row_count,
        "column_count": column_count,
    }
