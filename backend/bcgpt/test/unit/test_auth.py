"""Unit tests for JWT/auth helpers — token lifecycle and header parsing.

``bcgpt.utils.auth`` transitively imports the config/db layer, so this relies on
``conftest.py`` (same dir) providing BCGPT_SECRET_KEY + DATABASE_URL. Run from backend/:

    python -m pytest bcgpt/test/unit/test_auth.py
"""

from datetime import timedelta

import pytest

from bcgpt.utils.auth import (
    create_api_key,
    create_token,
    decode_token,
    extract_token_from_auth_header,
    get_http_authorization_cred,
    get_password_hash,
    verify_password,
)


def test_token_roundtrip_preserves_payload():
    decoded = decode_token(create_token({"id": "user-123"}, timedelta(minutes=5)))
    assert decoded is not None
    assert decoded["id"] == "user-123"


def test_token_with_expiry_has_iat_and_exp():
    # iter-1 hardening: every token is stamped with issued-at; finite tokens carry exp.
    decoded = decode_token(create_token({"id": "u"}, timedelta(minutes=5)))
    assert "iat" in decoded
    assert "exp" in decoded


def test_expired_token_is_rejected():
    expired = create_token({"id": "u"}, timedelta(minutes=-5))
    assert decode_token(expired) is None


def test_tampered_and_garbage_tokens_are_rejected():
    valid = create_token({"id": "u"}, timedelta(minutes=5))
    assert decode_token(valid + "tamper") is None
    assert decode_token("not.a.jwt") is None
    assert decode_token("") is None


def test_token_without_expiry_currently_never_expires():
    # DOCUMENTED tradeoff (see PRODUCTION_HARDENING_LOG iter-1 / SECURITY_AUDIT):
    # create_token() without expires_delta omits `exp`, and decode_token does NOT
    # enforce require=["exp"], so the token decodes indefinitely. This test locks
    # the current behavior — if mandatory expiry is ever introduced, update it
    # deliberately rather than letting the change pass silently.
    decoded = decode_token(create_token({"id": "u"}))
    assert decoded is not None
    assert "exp" not in decoded


# --- token_version (tv) claim -- carrier for logout / password-change revocation


def test_token_carries_token_version_claim():
    # The `tv` claim round-trips through create/decode. It is what the auth
    # dependency compares against the user's stored token_version to revoke
    # tokens on logout/password change. If this ever stops round-tripping,
    # revocation silently breaks (stale tokens would stay valid).
    decoded = decode_token(create_token({"id": "u", "tv": 7}, timedelta(minutes=5)))
    assert decoded is not None
    assert decoded.get("tv") == 7


def test_token_without_tv_has_no_version_claim():
    # A token minted without `tv` carries no version claim; the dependency's
    # `data.get("tv", 0)` then treats it as version 0.
    decoded = decode_token(create_token({"id": "u"}, timedelta(minutes=5)))
    assert decoded is not None
    assert "tv" not in decoded


def test_token_version_values_roundtrip():
    for tv in (0, 1, 99999):
        decoded = decode_token(
            create_token({"id": "u", "tv": tv}, timedelta(minutes=5))
        )
        assert decoded is not None
        assert decoded.get("tv") == tv


def test_extract_token_from_auth_header():
    assert extract_token_from_auth_header("Bearer abc.def.ghi") == "abc.def.ghi"


def test_get_http_authorization_cred_parses_valid_header():
    cred = get_http_authorization_cred("Bearer xyz")
    assert cred.scheme == "Bearer"
    assert cred.credentials == "xyz"


def test_get_http_authorization_cred_rejects_malformed_header():
    with pytest.raises(ValueError):
        get_http_authorization_cred("malformed-no-space")


def test_create_api_key_has_expected_prefix():
    key = create_api_key()
    assert key.startswith("sk-")
    assert len(key) > 10


# --- password hashing (bcrypt) ---------------------------------------------


def test_password_hash_is_not_plaintext_and_is_bcrypt():
    hashed = get_password_hash("hunter2")
    assert hashed != "hunter2"
    assert hashed.startswith("$2")  # bcrypt identifier


def test_verify_password_accepts_correct_and_rejects_wrong():
    hashed = get_password_hash("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_password_hash_is_salted():
    # Same input must yield different hashes (random salt), both verifying.
    h1 = get_password_hash("samepass")
    h2 = get_password_hash("samepass")
    assert h1 != h2
    assert verify_password("samepass", h1)
    assert verify_password("samepass", h2)


def test_verify_password_with_empty_hash_returns_falsy():
    # The guard `... if hashed_password else None` must not raise on a missing hash.
    assert not verify_password("anything", "")
    assert not verify_password("anything", None)
