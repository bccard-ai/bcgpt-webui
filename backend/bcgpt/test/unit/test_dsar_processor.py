"""Unit tests for the DSAR processor's security-relevant pure helpers.

The DB-backed export/erase/anonymize flows are not exercised here (the processor
runs raw SQL over a hardcoded table list; that surface was reviewed as
injection-safe: identifiers go through ``_quote_identifier`` and are hardcoded,
values use bind params). These tests lock the *pure* defenses:

  * ``_quote_identifier`` -- the SQL-identifier quoting that is the only thing
    standing between raw SQL and injection; must double embedded quotes and
    reject NUL/empty.
  * ``_redact_export_row`` -- credentials (auth.password, user.api_key,
    user_mfa.secret/backup_codes) must never appear in a portability export.
  * ``_json_safe`` / ``_safe_filename`` / ``_coerce_json`` -- serialization +
    filename sanitisation used while building the export bundle.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_dsar_processor.py -q
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from bcgpt.compliance.dsar_processor import (
    _coerce_json,
    _json_safe,
    _quote_identifier,
    _redact_export_row,
    _safe_filename,
)

_REDACTED = "[REDACTED_FOR_SECURITY]"


# ---------------------------------------------------------------------------
# _quote_identifier -- the SQL-injection defense
# ---------------------------------------------------------------------------


def test_quote_identifier_wraps_simple():
    assert _quote_identifier("user_id") == '"user_id"'


def test_quote_identifier_doubles_embedded_quotes():
    # An embedded double-quote must be doubled so the whole thing stays one
    # identifier (cannot break out into executable SQL).
    assert _quote_identifier('a"b') == '"a""b"'
    assert _quote_identifier('x"; DROP TABLE u; --') == '"x""; DROP TABLE u; --"'


def test_quote_identifier_rejects_empty():
    with pytest.raises(ValueError):
        _quote_identifier("")


def test_quote_identifier_rejects_nul():
    with pytest.raises(ValueError):
        _quote_identifier("a\x00b")


# ---------------------------------------------------------------------------
# _safe_filename -- export bundle filename sanitisation
# ---------------------------------------------------------------------------


def test_safe_filename_keeps_safe_chars():
    assert _safe_filename("user_export-2026.json") == "user_export-2026.json"


def test_safe_filename_replaces_unsafe_chars():
    # spaces and path/punctuation -> "_"
    assert _safe_filename("user 1/2?!file.json") == "user_1_2__file.json"


def test_safe_filename_truncates_to_64():
    long = "a" * 100
    assert len(_safe_filename(long)) == 64


def test_safe_filename_empty_fallback():
    # Only a truly empty result falls back to "user".
    assert _safe_filename("") == "user"


def test_safe_filename_all_unsafe_becomes_underscores():
    # Unsafe chars are replaced with "_" (not removed), so an all-unsafe input
    # is a non-empty string of underscores, not the "user" fallback.
    assert _safe_filename("!!!!") == "____"


# ---------------------------------------------------------------------------
# _json_safe -- export-row serialisation
# ---------------------------------------------------------------------------


def test_json_safe_primitives_passthrough():
    assert _json_safe(None) is None
    assert _json_safe("s") == "s"
    assert _json_safe(1) == 1
    assert _json_safe(1.5) == 1.5
    assert _json_safe(True) is True


def test_json_safe_decimal_to_float():
    assert _json_safe(Decimal("1.25")) == 1.25


def test_json_safe_bytes_utf8():
    assert _json_safe("hi".encode("utf-8")) == "hi"


def test_json_safe_bytes_non_utf8_to_hex():
    assert _json_safe(b"\xff\xfe") == "fffe"


def test_json_safe_dict_and_list():
    assert _json_safe({"a": 1, 2: "x"}) == {"a": 1, "2": "x"}  # keys stringified
    assert _json_safe([1, "a"]) == [1, "a"]
    assert _json_safe((1, 2)) == [1, 2]  # tuple -> list


def test_json_safe_datetime_isoformat():
    assert _json_safe(datetime(2026, 6, 22, 12, 0, 0)) == "2026-06-22T12:00:00"


# ---------------------------------------------------------------------------
# _redact_export_row -- credentials never appear in an export
# ---------------------------------------------------------------------------


def test_redact_auth_password():
    out = _redact_export_row("auth", {"password": "hashed", "email": "e@x.com"})
    assert out["password"] == _REDACTED
    assert out["email"] == "e@x.com"  # non-sensitive kept


def test_redact_user_api_key():
    out = _redact_export_row("user", {"api_key": "sk-xxx", "name": "Alice"})
    assert out["api_key"] == _REDACTED
    assert out["name"] == "Alice"


def test_redact_user_mfa_secret_and_backup_codes():
    out = _redact_export_row(
        "user_mfa", {"secret": "BASE32...", "backup_codes": ["1", "2"], "enabled": True}
    )
    assert out["secret"] == _REDACTED
    assert out["backup_codes"] == _REDACTED
    assert out["enabled"] is True


def test_redact_table_without_sensitive_fields_is_noop():
    row = {"id": "c1", "title": "chat", "user_id": "u1"}
    assert _redact_export_row("chat", row) == row


def test_redact_none_sensitive_value_stays_none():
    # A None credential is not turned into the redaction marker (line 143:
    # `and value is not None`).
    out = _redact_export_row("auth", {"password": None, "email": "e@x.com"})
    assert out["password"] is None


# ---------------------------------------------------------------------------
# _coerce_json -- JSON column normalisation
# ---------------------------------------------------------------------------


def test_coerce_json_none_to_default():
    assert _coerce_json(None, {}) == {}


def test_coerce_json_dict_passthrough():
    d = {"a": 1}
    assert _coerce_json(d, {}) is d


def test_coerce_json_list_passthrough():
    lst = [1, 2]
    assert _coerce_json(lst, []) is lst


def test_coerce_json_valid_string_parsed():
    assert _coerce_json('{"a": 1}', {}) == {"a": 1}


def test_coerce_json_invalid_string_to_default():
    assert _coerce_json("not json", {"fallback": True}) == {"fallback": True}


def test_coerce_json_non_string_to_default():
    assert _coerce_json(42, "default") == "default"
