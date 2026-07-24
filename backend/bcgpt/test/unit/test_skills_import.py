"""Tests for the GitHub import helper (allow-list, size, validation).

cd backend && python -m pytest bcgpt/test/unit/test_skills_import.py -v
"""

from __future__ import annotations

import pytest

from bcgpt.utils import gh_import

VALID_MD = """---
name: technical-writing
description: Plan and revise clear technical docs
---
# Technical Writing
When asked to write or edit documentation, follow the rubric in resources/style.md.
"""


def test_allowed_host_accepted(monkeypatch):
    def fake_urlopen(req, timeout):
        class _R:
            headers = {"Content-Length": str(len(VALID_MD))}
            status = 200

            def read(self):
                return VALID_MD.encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _R()

    monkeypatch.setattr(gh_import.urllib.request, "urlopen", fake_urlopen)
    content, src = gh_import.fetch_skill_from_url(
        "https://raw.githubusercontent.com/org/repo/main/skills/writing/SKILL.md"
    )
    assert "Technical Writing" in content
    assert src.startswith("https://raw.githubusercontent.com/")


def test_disallowed_host_rejected():
    with pytest.raises(ValueError):
        gh_import.fetch_skill_from_url("https://evil.example.com/x.md")


def test_oversized_payload_rejected(monkeypatch):
    big = "x" * (gh_import.MAX_BYTES + 1)

    class _R:
        headers = {"Content-Length": str(len(big))}
        status = 200

        def read(self):
            return big.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(gh_import.urllib.request, "urlopen", lambda *a, **k: _R())
    with pytest.raises(ValueError):
        gh_import.fetch_skill_from_url("https://raw.githubusercontent.com/o/r/m/b.md")


def test_validate_rejects_scripts_resource():
    from bcgpt.utils.gh_import import validate_skill_content

    md = (
        "---\nname: n\ndescription: d\n"
        'resources:\n  scripts/run.py: "print(1)"\n---\n# body\n'
    )
    with pytest.raises(ValueError):
        validate_skill_content(md, fmt="md")


def test_validate_requires_name_and_description():
    md = "---\ndescription: missing name\n---\nbody"
    with pytest.raises(ValueError):
        gh_import.validate_skill_content(md, fmt="md")


def test_validate_valid_md_returns_skill():
    skill, meta = gh_import.validate_skill_content(VALID_MD, fmt="md")
    assert skill.name == "technical-writing"
    assert "Writing" in skill.prompt_template
    assert meta["resources"] == {}
