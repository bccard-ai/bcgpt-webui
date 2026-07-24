"""CSV formula-injection guard (CWE-1236). Prefixes a single quote before cells starting with a formula-trigger character so spreadsheet apps treat them as text, not formulas."""

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value):
    """Make a cell value safe for CSV/spreadsheet export.
    - None -> "" (empty string).
    - Non-str (int/float/bool) -> returned UNCHANGED (numbers can't be formula-injected; preserve type so
      csv.writer formats them normally).
    - str starting with one of _FORMULA_PREFIXES (=,+,-,@,tab,CR) -> return "'" + value (leading apostrophe).
    - other str -> returned unchanged.
    Never raises."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize_row(row):
    """Apply sanitize_csv_cell to each item of an iterable; return a list."""
    return [sanitize_csv_cell(item) for item in row]
