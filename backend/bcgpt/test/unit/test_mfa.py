"""Unit tests for the MFA (TOTP) backup-code helpers.

The full ``UserMFATable`` methods are DB-backed and the ``auths`` router import
runs the app's migration set, so neither is exercised here (see the
``PRODUCTION_HARDENING_LOG.md`` iteration 50 note). These tests lock the two
security-relevant *pure* pieces of the backup-code path:

  * ``_hash_code`` -- backup codes are stored as SHA-256 hashes (never
    plaintext), and the hash is whitespace-tolerant to match ``verify_code``'s
    ``.strip()`` so a user-pasted ``" abcd1234 "`` matches the stored hash.
  * ``_generate_backup_codes`` -- the 2026-06-22 entropy bump from 32 bits
    (``token_hex(4)``) to 48 bits (``token_hex(6)``): each code is 12 hex chars,
    the requested count is produced, and all codes are unique.

The higher-level guarantees (login MFA gate behind ``MFA_ENABLED``, per-endpoint
``get_verified_user`` IDOR -- a user can only manage their own MFA, ``/mfa/disable``
requires a valid second factor so a hijacked session can't drop MFA, and the
account-lockout that rate-limits TOTP/backup guessing) were verified by white-box
review of ``routers/auths.py``.

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_mfa.py -q
"""

from __future__ import annotations

import re

from bcgpt.models.user_mfa import (
    _BACKUP_CODE_BYTES,
    _BACKUP_CODE_COUNT,
    _generate_backup_codes,
    _hash_code,
)

_HEX12 = re.compile(r"^[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# _hash_code -- backup codes are stored as SHA-256 hashes
# ---------------------------------------------------------------------------


def test_hash_code_is_sha256_hex():
    h = _hash_code("abcd1234")
    assert len(h) == 64  # SHA-256 = 32 bytes = 64 hex chars
    assert re.fullmatch(r"[0-9a-f]{64}", h)


def test_hash_code_deterministic():
    assert _hash_code("code") == _hash_code("code")


def test_hash_code_different_inputs_differ():
    assert _hash_code("code1") != _hash_code("code2")


def test_hash_code_strips_whitespace():
    """verify_code strips the supplied code before hashing/lookup, so the hash
    of a user-pasted "  abcd1234  " must equal the hash of "abcd1234"."""
    assert _hash_code("  abcd1234  ") == _hash_code("abcd1234")


def test_hash_code_empty_string_is_valid_hash():
    # Edge: an empty code still hashes (verify_code rejects empty *before* this,
    # but the helper itself must not raise).
    assert _hash_code("") == _hash_code("")


# ---------------------------------------------------------------------------
# _generate_backup_codes -- entropy + uniqueness (the 32 -> 48 bit bump)
# ---------------------------------------------------------------------------


def test_backup_codes_default_count():
    codes = _generate_backup_codes()
    assert len(codes) == _BACKUP_CODE_COUNT


def test_backup_codes_respect_custom_count():
    assert len(_generate_backup_codes(5)) == 5
    assert len(_generate_backup_codes(0)) == 0


def test_backup_codes_are_48_bit_hex():
    """Each code is 2 * _BACKUP_CODE_BYTES hex chars (48 bits at the default)."""
    codes = _generate_backup_codes(20)
    assert all(_HEX12.match(c) for c in codes), codes
    assert len(codes[0]) == 2 * _BACKUP_CODE_BYTES


def test_backup_codes_are_unique():
    codes = _generate_backup_codes(_BACKUP_CODE_COUNT)
    assert len(set(codes)) == _BACKUP_CODE_COUNT


def test_backup_codes_entropy_above_32_bits():
    """Regression guard for the 2026-06-22 fix: codes must carry MORE than the
    old 32 bits (8 hex chars). 12 hex chars = 48 bits."""
    codes = _generate_backup_codes(10)
    assert all(len(c) > 8 for c in codes)
