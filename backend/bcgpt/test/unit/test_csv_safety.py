"""Unit tests for bcgpt.utils.csv_safety (CWE-1236 guard)."""

from bcgpt.utils.csv_safety import sanitize_csv_cell, sanitize_row


def test_equals_prefix():
    assert sanitize_csv_cell("=cmd()") == "'=cmd()"


def test_plus_minus_at_prefixes():
    assert sanitize_csv_cell("+1+1") == "'+1+1"
    assert sanitize_csv_cell("-2") == "'-2"
    assert sanitize_csv_cell("@SUM") == "'@SUM"


def test_tab_cr_prefixes():
    assert sanitize_csv_cell("\tdata") == "'\tdata"
    assert sanitize_csv_cell("\rx") == "'\rx"


def test_normal_strings_unchanged():
    assert sanitize_csv_cell("hello") == "hello"
    assert sanitize_csv_cell("user@example.com") == "user@example.com"


def test_numbers_preserved_with_type():
    result_int = sanitize_csv_cell(42)
    assert result_int == 42 and isinstance(result_int, int)

    result_float = sanitize_csv_cell(3.5)
    assert result_float == 3.5 and isinstance(result_float, float)

    result_bool = sanitize_csv_cell(True)
    assert result_bool is True


def test_none_returns_empty_string():
    assert sanitize_csv_cell(None) == ""


def test_empty_string_unchanged():
    assert sanitize_csv_cell("") == ""


def test_sanitize_row():
    assert sanitize_row(["=A1", "ok", 5, None]) == ["'=A1", "ok", 5, ""]
