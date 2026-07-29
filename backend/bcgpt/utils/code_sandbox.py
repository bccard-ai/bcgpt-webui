"""Sandboxed Python code interpreter for agent tool calls.

Executes Python code in a restricted subprocess with:
- CPU / memory / file-size rlimits
- No network access (socket module blocked at runtime)
- AST validation (allowlist of safe module imports + dunder/attribute guards)
- Timeout enforcement via ``asyncio.wait_for``
- Process isolation (separate OS process)

Exposes ``make_run_python_descriptor()`` which returns the synthetic tool
descriptor consumed by ``process_chat_payload`` -- follows the exact pattern of
``skill_runtime.make_read_skill_descriptor``.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import sys
import textwrap
from typing import Any

log = logging.getLogger(__name__)

# -- Configuration -----------------------------------------------------------

DEFAULT_TIMEOUT = 10
DEFAULT_CPU_SECONDS = 5
DEFAULT_MEMORY_MB = 256
DEFAULT_MAX_OUTPUT = 50_000

ALLOWED_MODULES: frozenset[str] = frozenset({
    "math", "cmath", "statistics", "random", "itertools", "functools",
    "operator", "collections", "re", "json", "datetime",
    "decimal", "fractions", "string", "textwrap",
    "hashlib", "base64", "unicodedata", "bisect", "heapq",
    "array", "struct", "pprint", "numbers", "enum",
    "dataclasses", "typing", "io", "csv", "configparser",
})

_FORBIDDEN_ATTRS: frozenset[str] = frozenset({
    "__import__", "__subclasses__", "__bases__", "__mro__",
    "__globals__", "__builtins__", "__code__", "__func__",
    "gi_frame", "gi_code", "cr_frame", "cr_code",
    "f_back", "f_locals", "f_globals", "f_builtins", "f_code",
    "co_consts", "co_names", "co_code",
})


# -- AST Validation ----------------------------------------------------------

class _SandboxValidator(ast.NodeVisitor):
    """Reject dangerous patterns before code reaches the subprocess."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def _err(self, msg: str) -> None:
        self.errors.append(msg)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in ALLOWED_MODULES:
                self._err(f"Import of '{alias.name}' is not allowed in sandbox")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self._err("Relative imports are not allowed in sandbox")
            return
        top = node.module.split(".")[0]
        if top not in ALLOWED_MODULES:
            self._err(f"Import from '{node.module}' is not allowed in sandbox")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _FORBIDDEN_ATTRS:
            self._err(f"Access to attribute '{node.attr}' is not allowed in sandbox")
        self.generic_visit(node)

    _SAFE_DUNDERS: frozenset[str] = frozenset({
        "__name__", "__doc__", "__file__", "__all__",
        "__version__", "__author__",
    })

    def visit_Name(self, node: ast.Name) -> None:
        nid = node.id
        if nid.startswith("__") and nid.endswith("__") and nid not in self._SAFE_DUNDERS:
            self._err(f"Use of '{nid}' is not allowed in sandbox")
        self.generic_visit(node)


def validate_code(code: str) -> list[str]:
    """Return a list of validation errors (empty list = code is safe)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Syntax error: {exc}"]
    validator = _SandboxValidator()
    validator.visit(tree)
    return validator.errors


# -- Subprocess runner script ------------------------------------------------

_RUNNER_SCRIPT = textwrap.dedent("""\
import sys, json, io, contextlib, traceback, resource

try:
    resource.setrlimit(resource.RLIMIT_CPU, ({cpu_seconds}, {cpu_seconds}))
    resource.setrlimit(resource.RLIMIT_AS, ({max_memory}, {max_memory}))
    resource.setrlimit(resource.RLIMIT_FSIZE, ({max_file}, {max_file}))
except (ValueError, OSError):
    pass

import socket as _sock_mod

class _BlockedSocket:
    def __init__(self, *a, **kw):
        raise OSError("Network access is blocked in the sandbox")

_sock_mod.socket = _BlockedSocket

_code = sys.stdin.read()
_out = io.StringIO()
_result = {{}}
try:
    with contextlib.redirect_stdout(_out), contextlib.redirect_stderr(_out):
        exec(compile(_code, "<sandbox>", "exec"), {{}})
    _result["success"] = True
    _result["output"] = _out.getvalue()[:{max_output}]
except Exception as _exc:
    _result["success"] = False
    _result["error"] = str(_exc)[:{max_output}]
    _result["traceback"] = traceback.format_exc()[:{max_output}]
    _result["output"] = _out.getvalue()[:{max_output}]
print(json.dumps(_result, ensure_ascii=False, default=str))
""")


def _build_runner_script(*, cpu_seconds: int, memory_mb: int, max_output: int) -> str:
    return _RUNNER_SCRIPT.format(
        cpu_seconds=cpu_seconds,
        max_memory=memory_mb * 1024 * 1024,
        max_file=10 * 1024 * 1024,
        max_output=max_output,
    )


# -- Public API --------------------------------------------------------------

async def run_python_sandboxed(
    code: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    cpu_seconds: int = DEFAULT_CPU_SECONDS,
    memory_mb: int = DEFAULT_MEMORY_MB,
    max_output: int = DEFAULT_MAX_OUTPUT,
) -> dict[str, Any]:
    """Execute *code* in a sandboxed subprocess.

    Returns dict with: success (bool), output (str), and on failure:
    error (str), traceback (str).
    """
    errors = validate_code(code)
    if errors:
        return {
            "success": False,
            "error": "Code validation failed",
            "details": "; ".join(errors),
            "output": "",
        }

    script = _build_runner_script(
        cpu_seconds=cpu_seconds, memory_mb=memory_mb, max_output=max_output,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-c", script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(code.encode()), timeout=timeout,
        )
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Execution timed out after {timeout}s", "output": ""}
    except Exception as exc:
        return {"success": False, "error": f"Sandbox error: {exc}", "output": ""}

    raw = stdout.decode(errors="replace").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    err = stderr.decode(errors="replace")[:max_output]
    return {"success": False, "error": f"Sandbox exited with code {proc.returncode}", "output": err}


# -- Synthetic tool descriptor -----------------------------------------------

_RUN_PYTHON_SPEC: dict[str, Any] = {
    "name": "run_python",
    "description": (
        "Execute Python code in a secure sandbox for calculations, data "
        "analysis, or text processing. No network access. Allowed imports: "
        "math, statistics, random, itertools, functools, collections, re, "
        "json, datetime, decimal, hashlib, base64, and more. Use print() "
        "for output."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use print() for output.",
            },
        },
        "required": ["code"],
    },
}


def make_run_python_descriptor() -> dict[str, Any]:
    """Build the synthetic ``run_python`` tool descriptor for ``tools_dict``.

    Register alongside ``read_skill`` in ``process_chat_payload``::

        tools_dict["run_python"] = make_run_python_descriptor()
    """

    async def _run_python_callable(code: str) -> str:
        result = await run_python_sandboxed(code)
        if result.get("success"):
            output = (result.get("output") or "").strip()
            if not output:
                return "Code executed successfully (no output)."
            return f"```\n{output}\n```"
        error = result.get("error", "Unknown error")
        details = result.get("details", "")
        output = (result.get("output") or "").strip()
        parts = [f"Error: {error}"]
        if details:
            parts.append(f"Details: {details}")
        if output:
            parts.append(f"Output before error:\n```\n{output}\n```")
        return "\n".join(parts)

    return {
        "spec": _RUN_PYTHON_SPEC,
        "callable": _run_python_callable,
        "toolkit_id": "__code_sandbox__",
    }
