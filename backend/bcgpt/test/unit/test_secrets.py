"""Unit tests for the secrets scanner (credential-leak detection).

Standalone — imports only ``bcgpt.utils.security.secrets`` (regex + enums), so it
runs without the integration harness. Run from ``backend/``:

    python -m pytest bcgpt/test/unit/test_secrets.py

Fixtures below are obviously-fake, pattern-matching samples (e.g. the canonical
AWS documentation example key) — never real credentials.
"""

import pytest

from bcgpt.utils.security.secrets import SecretsScanner, _mask_match

# (label, sample text, expected pattern_name)
SECRET_SAMPLES = [
    ("aws", "key is AKIAIOSFODNN7EXAMPLE today", "aws_access_key"),
    ("github", "token ghp_0123456789abcdefghijklmnopqrstuvwxyzABCD", "github_token"),
    ("openai", "use sk-proj-abcdefghij0123456789KLMN here", "openai_api_key"),
    (
        "jwt",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5Nz",
        "jwt",
    ),
    ("private_key", "-----BEGIN RSA PRIVATE KEY-----", "private_key"),
]


@pytest.mark.parametrize(
    "label,text,expected", SECRET_SAMPLES, ids=[s[0] for s in SECRET_SAMPLES]
)
def test_scan_detects_known_secret_types(label, text, expected):
    result = SecretsScanner().scan(text)
    assert result.is_safe is False
    names = {t.pattern_name for t in result.threats}
    assert expected in names


def test_scan_never_leaks_the_full_secret():
    # The canonical AWS example key must be truncated in every recorded field.
    aws = "AKIAIOSFODNN7EXAMPLE"
    result = SecretsScanner().scan(f"leaked {aws} oops")
    assert result.is_safe is False
    for threat in result.threats:
        assert aws not in threat.matched_text
        assert aws not in threat.masked_text
        assert threat.masked_text.endswith("...")


def test_clean_text_is_safe():
    result = SecretsScanner().scan("nothing secret in this perfectly ordinary sentence")
    assert result.is_safe is True
    assert result.threats == []
    assert result.scanner_name == "secrets"


def test_mask_match_truncation_rules():
    # > 8 chars → first 8 + "..."; <= 8 chars → first 4 + "..."
    assert _mask_match("AKIAIOSFODNN7EXAMPLE") == "AKIAIOSF..."
    assert _mask_match("short") == "shor..."
    # Whatever the length, the original is never fully reproduced.
    for sample in ("AKIAIOSFODNN7EXAMPLE", "short", "12345678"):
        assert sample not in _mask_match(sample) or len(sample) <= 4
