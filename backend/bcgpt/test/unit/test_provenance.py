"""Tests for RAG-provenance integrity helpers (``compliance/models/provenance.py``).

The provenance record carries a ``signature`` = SHA-256 over the canonical JSON of all
its fields (used for tamper-evidence / audit of which prompt+response+sources produced an
answer). These lock the pure hashing helpers so a regression (non-deterministic JSON
ordering, signature including itself, non-serializable values crashing) doesn't silently
break the audit trail. The DB insert path is not covered.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_provenance.py -q
"""

from __future__ import annotations

from bcgpt.compliance.models.provenance import _compute_signature, _sha256

# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------


def test_sha256_deterministic_and_hex():
    assert _sha256("hello") == _sha256("hello")
    assert all(c in "0123456789abcdef" for c in _sha256("hello"))
    assert len(_sha256("hello")) == 64


def test_sha256_different_inputs_differ():
    assert _sha256("a") != _sha256("b")


def test_sha256_unicode():
    # Korean text must encode as UTF-8 without raising.
    assert isinstance(_sha256("매출 증가"), str)


# ---------------------------------------------------------------------------
# _compute_signature -- canonical JSON -> SHA-256
# ---------------------------------------------------------------------------


def test_signature_is_deterministic():
    assert _compute_signature({"a": 1, "b": 2}) == _compute_signature({"a": 1, "b": 2})


def test_signature_is_key_order_independent():
    # sort_keys means insertion order must not change the signature.
    assert _compute_signature({"a": 1, "b": 2}) == _compute_signature({"b": 2, "a": 1})


def test_signature_changes_with_content():
    assert _compute_signature({"a": 1}) != _compute_signature({"a": 2})
    assert _compute_signature({"a": 1}) != _compute_signature({"a": 1, "b": 2})


def test_signature_includes_all_keys_exclusion_is_callers_job():
    # _compute_signature hashes EVERY key it is given (it does not auto-exclude
    # "signature"). The insert path is what strips the signature field before
    # calling it (no circular dependency) -- so adding a key here DOES change it.
    base = {"query_text": "q", "response_hash": "h"}
    assert _compute_signature(base) != _compute_signature({**base, "signature": "x"})


def test_signature_handles_non_serializable_via_default_str():
    # default=str stringifies otherwise-unserializable values instead of raising.

    class _Thing:
        def __str__(self):
            return "thing"

    # Must not raise; produces a stable signature.
    sig = _compute_signature({"obj": _Thing(), "n": 1})
    assert isinstance(sig, str) and len(sig) == 64


def test_signature_nested_structure_stable():
    a = {"retrieved": [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.5}]}
    b = {"retrieved": [{"id": 2, "score": 0.5}, {"id": 1, "score": 0.9}]}
    # Different list order -> different signature (list order is significant).
    assert _compute_signature(a) != _compute_signature(b)
    assert _compute_signature(a) == _compute_signature(
        {"retrieved": [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.5}]}
    )
