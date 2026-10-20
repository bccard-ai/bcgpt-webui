"""Frontmatter ``requirements`` may only name packages, never pip options or URLs.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_plugin_requirements.py -q
"""

from __future__ import annotations

import pytest

from bcgpt.utils.plugin import parse_frontmatter_requirements


def test_plain_requirements_accepted():
    assert parse_frontmatter_requirements(
        "requests, pydantic>=2.0, numpy==1.26.4, uvicorn[standard]~=0.30"
    ) == ["requests", "pydantic>=2.0", "numpy==1.26.4", "uvicorn[standard]~=0.30"]


def test_empty_entries_dropped():
    assert parse_frontmatter_requirements(" , ") == []


@pytest.mark.parametrize(
    "spec",
    [
        "--index-url https://example.invalid/simple",
        "-e git+https://example.invalid/repo.git",
        "pkg @ https://example.invalid/pkg.whl",
        "git+https://example.invalid/repo.git",
        "./local/path",
        "/abs/path.whl",
        "pkg; os_name == 'posix'",
    ],
)
def test_non_package_specifiers_rejected(spec):
    with pytest.raises(ValueError):
        parse_frontmatter_requirements(spec)
