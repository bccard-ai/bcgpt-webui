"""Unit tests for the PII scanner/masker (security-critical redaction).

These are deliberately *standalone*: they import only
``bcgpt.utils.security.pii``, which has no environment-variable or heavy
dependency requirements, so they collect and run without the Postgres
testcontainer harness used by the integration tests. Run from ``backend/``:

    python -m pytest bcgpt/test/unit/test_pii.py
"""

from bcgpt.utils.security.pii import PIIScanner, _korean_rrn_validate, _luhn_validate

# A resident-registration number whose check digit satisfies the RRN checksum
# (asserted in test_valid_rrn_passes_checksum so the fixture can't silently rot).
VALID_RRN = "900101-1234568"


def test_valid_rrn_passes_checksum():
    assert _korean_rrn_validate(VALID_RRN) is True


def test_luhn_validate_distinguishes_valid_and_invalid():
    assert _luhn_validate("4242424242424242") is True
    assert _luhn_validate("4242424242424241") is False


def test_mask_redacts_valid_korean_rrn():
    scanner = PIIScanner()
    masked = scanner.mask(f"내 주민번호는 {VALID_RRN} 입니다")
    assert VALID_RRN not in masked
    assert "[REDACTED_KOREAN_RRN]" in masked


def test_mask_redacts_email_and_ssn():
    scanner = PIIScanner()
    masked = scanner.mask("email a.b@example.com or SSN 123-45-6789 here")
    assert "a.b@example.com" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "123-45-6789" not in masked
    assert "[REDACTED_SSN]" in masked


def test_clean_text_is_safe_and_unchanged():
    scanner = PIIScanner()
    result = scanner.scan("the quick brown fox jumps over the lazy dog")
    assert result.is_safe is True
    assert result.threats == []
    assert result.masked_text is None
    assert scanner.mask("the quick brown fox") == "the quick brown fox"


def test_scan_flags_pii_as_unsafe_with_masked_text():
    scanner = PIIScanner()
    result = scanner.scan(f"please call {VALID_RRN}")
    assert result.is_safe is False
    assert len(result.threats) >= 1
    assert result.masked_text is not None
    assert VALID_RRN not in result.masked_text


def test_invalid_checksum_rrn_is_not_redacted_as_rrn():
    # A string matching the RRN *shape* but failing the checksum must never be
    # tagged as a Korean RRN (it may still be caught by a broader pattern).
    scanner = PIIScanner()
    bogus = "000000-1000000"
    assert _korean_rrn_validate(bogus) is False
    assert "[REDACTED_KOREAN_RRN]" not in scanner.mask(bogus)
