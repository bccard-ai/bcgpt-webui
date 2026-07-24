"""Unit tests for column_profiler module."""

import pytest
from bcgpt.retrieval.column_profiler import (
    detect_cell_type,
    profile_column,
    profile_table,
)

# ---------------------------------------------------------------------------
# 1. detect_cell_type — individual cell classification
# ---------------------------------------------------------------------------


class TestDetectCellType:
    def test_currency_usd_symbol(self):
        assert detect_cell_type("$1,234.56") == "currency"

    def test_currency_won_symbol(self):
        assert detect_cell_type("₩1,000") == "currency"

    def test_currency_korean_suffix(self):
        assert detect_cell_type("1,000원") == "currency"

    def test_percent(self):
        assert detect_cell_type("12.5%") == "percent"

    def test_date_iso(self):
        assert detect_cell_type("2024-01-15") == "date"

    def test_date_korean(self):
        assert detect_cell_type("2024년 1월 15일") == "date"

    def test_date_valid_leap_day(self):
        assert detect_cell_type("2024-02-29") == "date"

    @pytest.mark.parametrize(
        "value",
        [
            "2026-13-45",
            "2023-02-29",
            "2024년 13월 1일",
            "02/31/2024",
            "31/02/2024",
        ],
    )
    def test_invalid_calendar_dates_are_text(self, value):
        assert detect_cell_type(value) == "text"

    def test_number_thousands(self):
        assert detect_cell_type("1,234") == "number"

    def test_number_negative(self):
        assert detect_cell_type("-42") == "number"

    def test_number_parens_negative(self):
        assert detect_cell_type("(42)") == "number"

    def test_boolean_true(self):
        assert detect_cell_type("true") == "boolean"

    def test_boolean_korean_yes(self):
        assert detect_cell_type("예") == "boolean"

    def test_empty_string(self):
        assert detect_cell_type("") == "empty"

    def test_empty_none(self):
        assert detect_cell_type(None) == "empty"

    def test_text(self):
        assert detect_cell_type("hello") == "text"


# ---------------------------------------------------------------------------
# 2. profile_column — all same type
# ---------------------------------------------------------------------------


def test_profile_column_all_currency():
    result = profile_column(["$1", "$2", "$3"])
    assert result["type"] == "currency"
    assert result["confidence"] == 1.0


# ---------------------------------------------------------------------------
# 3. profile_column — mixed majority (2 of 3 percent)
# ---------------------------------------------------------------------------


def test_profile_column_mixed_majority():
    result = profile_column(["10%", "20%", "abc"])
    assert result["type"] == "percent"
    assert abs(result["confidence"] - 2 / 3) < 1e-9


# ---------------------------------------------------------------------------
# 4. profile_column — numbers with one empty
# ---------------------------------------------------------------------------


def test_profile_column_numbers_with_empty():
    result = profile_column(["1", "2", "", "3"])
    assert result["type"] == "number"
    assert result["non_empty"] == 3
    assert result["empty"] == 1
    assert result["confidence"] == 1.0


# ---------------------------------------------------------------------------
# 5. profile_column — all empty / empty list
# ---------------------------------------------------------------------------


def test_profile_column_empty_list():
    result = profile_column([])
    assert result["type"] == "text"
    assert result["non_empty"] == 0


def test_profile_column_all_empty_strings():
    result = profile_column(["", "", ""])
    assert result["type"] == "text"
    assert result["non_empty"] == 0


# ---------------------------------------------------------------------------
# 6. profile_table — list rows + headers
# ---------------------------------------------------------------------------


def test_profile_table_list_rows_with_headers():
    rows = [["$1", "2024-01-01"], ["$2", "2024-02-01"]]
    headers = ["price", "date"]
    result = profile_table(rows, headers=headers)
    assert result["row_count"] == 2
    assert result["column_count"] == 2
    assert result["columns"]["price"]["type"] == "currency"
    assert result["columns"]["date"]["type"] == "date"


# ---------------------------------------------------------------------------
# 7. profile_table — dict rows
# ---------------------------------------------------------------------------


def test_profile_table_dict_rows():
    rows = [{"a": "5%", "b": "x"}, {"a": "7%", "b": "y"}]
    result = profile_table(rows)
    assert result["columns"]["a"]["type"] == "percent"
    assert result["columns"]["b"]["type"] == "text"


# ---------------------------------------------------------------------------
# 8. profile_table — ragged rows (no exception, correct empty count)
# ---------------------------------------------------------------------------


def test_profile_table_ragged_rows():
    rows = [["1", "2"], ["3"]]
    result = profile_table(rows)
    # Column index "1" should have one empty cell (second row missing)
    col1 = result["columns"]["1"]
    assert col1["empty"] == 1
    # Should not raise; column "0" has both cells as number
    col0 = result["columns"]["0"]
    assert col0["type"] == "number"
