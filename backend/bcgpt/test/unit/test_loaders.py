"""Tests for the document-loader HTML encoding fix (``retrieval/loaders/main.py``).

Locks the iter-73 fix: HTML files are now read with ``utf-8`` instead of the broken
``unicode_escape``. ``unicode_escape`` decodes Python source escapes (``\\uXXXX`` / ``\\n`` / ``\\U``),
which (a) corrupts non-ASCII text -- Korean UTF-8 came out as mojibake like ``ë§¤ì¶`` -- and (b) raises
``UnicodeDecodeError`` on any literal ``\\U`` (e.g. a pasted Windows path ``C:\\Users\\...``), crashing
HTML ingestion outright. For a Korean-deployment RAG system both are severe.

The dispatch ``Loader._get_loader`` is light (loaders are constructed lazily, no parsing on init), so the
chosen ``open_encoding`` is asserted directly. The behavior cases (UTF-8 preserves Korean; the old codec
corrupted / crashed) document why.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_loaders.py -q
"""

from __future__ import annotations

import pytest

from bcgpt.retrieval.loaders.main import Loader

# ---------------------------------------------------------------------------
# the fix: HTML loader must NOT use unicode_escape
# ---------------------------------------------------------------------------


def test_html_loader_uses_utf8_not_unicode_escape():
    loader = Loader._get_loader(
        Loader(engine="default"), "/tmp/sample.html", "utf-8", "text/html"
    )
    assert type(loader).__name__ == "BSHTMLLoader"
    assert getattr(loader, "open_encoding", None) == "utf-8"
    assert getattr(loader, "open_encoding", None) != "unicode_escape"


def test_htm_extension_also_uses_utf8():
    loader = Loader._get_loader(
        Loader(engine="default"), "/tmp/sample.htm", "utf-8", "text/html"
    )
    assert getattr(loader, "open_encoding", None) == "utf-8"


# ---------------------------------------------------------------------------
# behavior: why unicode_escape was wrong (regression documentation)
# ---------------------------------------------------------------------------


def test_utf8_preserves_korean_html():
    # The correct encoding keeps Korean text intact.
    html = "<p>매출 증가</p>".encode("utf-8")
    assert html.decode("utf-8") == "<p>매출 증가</p>"


def test_unicode_escape_corrupted_korean():
    # The old codec mangled multi-byte UTF-8 into latin-1 mojibake -- this is the
    # bug the fix removes. Locked so the broken encoding is never reintroduced.
    html = "<p>매출</p>".encode("utf-8")
    decoded = html.decode("unicode_escape")
    assert decoded != "<p>매출</p>"  # corrupted (mojibake)
    assert "매" not in decoded


def test_unicode_escape_crashed_on_literal_U():
    # A literal "\U" (e.g. a Windows path) raised under the old codec; utf-8 reads it fine.
    html = b"<p>C:\\Users\\name</p>"
    assert html.decode("utf-8") == "<p>C:\\Users\\name</p>"
    with pytest.raises(UnicodeDecodeError):
        b"C:\\Users".decode("unicode_escape")
