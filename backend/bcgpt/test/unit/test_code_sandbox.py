"""Security tests for the ``run_python`` code sandbox (``utils/code_sandbox.py``).

The sandbox must not rely on AST validation alone: these tests lock the runtime
layer (reduced ``__builtins__``, import allowlist) and the environment isolation
so the server's secrets are never visible to sandboxed code.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_code_sandbox.py -q
"""

from __future__ import annotations

import asyncio
import os

import pytest

from bcgpt.utils import code_sandbox as cs


def _run(code: str) -> dict:
    return asyncio.run(cs.run_python_sandboxed(code))


def _run_unvalidated(code: str) -> dict:
    """Exercise the runtime layer directly, as if the AST check were bypassed."""
    script = cs._build_runner_script(
        cpu_seconds=cs.DEFAULT_CPU_SECONDS,
        memory_mb=cs.DEFAULT_MEMORY_MB,
        max_output=cs.DEFAULT_MAX_OUTPUT,
    )
    return asyncio.run(
        cs._execute(code, script=script, timeout=cs.DEFAULT_TIMEOUT, max_output=1000)
    )


def test_allowed_code_runs():
    result = _run(
        "import math, json\n"
        "from collections import Counter\n"
        "print(json.dumps({'sqrt': math.sqrt(16), 'n': Counter('aab')['a']}))"
    )
    assert result["success"] is True
    assert '"sqrt": 4.0' in result["output"]
    assert '"n": 2' in result["output"]


@pytest.mark.parametrize("module", ["os", "subprocess", "socket", "io", "configparser"])
def test_disallowed_imports_rejected_by_validator(module):
    assert cs.validate_code(f"import {module}")


@pytest.mark.parametrize("name", sorted(cs.FORBIDDEN_BUILTINS))
def test_forbidden_builtins_rejected_by_validator(name):
    assert cs.validate_code(f"x = {name}")


def test_runtime_builtins_exclude_forbidden_names():
    result = _run_unvalidated(
        "print(sorted(k for k in __builtins__ if k in %r))"
        % sorted(cs.FORBIDDEN_BUILTINS)
    )
    assert result["success"] is True
    assert result["output"].strip() == "[]"


def test_runtime_import_allowlist_enforced():
    result = _run_unvalidated("import os")
    assert result["success"] is False
    assert "not allowed" in result["error"]


def test_runtime_import_allows_allowlisted_module():
    result = _run_unvalidated("import statistics\nprint(statistics.mean([1, 2, 3]))")
    assert result["success"] is True
    assert result["output"].strip() == "2"


def test_sandbox_env_does_not_inherit_server_environment(monkeypatch):
    monkeypatch.setenv("BCGPT_SECRET_KEY", "must-not-leak")
    env = cs._sandbox_env()
    assert "BCGPT_SECRET_KEY" not in env
    assert set(env) <= {"PATH", "LANG", "PYTHONIOENCODING"}
    assert os.environ["BCGPT_SECRET_KEY"] == "must-not-leak"
