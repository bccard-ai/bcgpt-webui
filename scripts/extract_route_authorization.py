#!/usr/bin/env python3
"""Route authorization inventory extractor.

Scans FastAPI router source files via AST to produce a committed, repeatable
route authorization inventory. Outputs ``docs/generated/ROUTE_AUTHORIZATION_INVENTORY.md``.

Scope:
  - ``backend/bcgpt/routers/**/*.py``
  - ``backend/bcgpt/agent/routers/**/*.py``
  - ``backend/bcgpt/compliance/routers/**/*.py``
  - ``backend/bcgpt/compliance/hitl/router.py``

For each route decorator (``@router.get``, ``@router.post``, etc.) the extractor
captures:
  - HTTP method (or comma-joined methods for ``api_route``)
  - Decorator path argument
  - Full path prefix resolved from ``main.py`` ``include_router`` calls
  - Source file + line number
  - FastAPI dependency classification (``get_admin_user``, ``get_verified_user``,
    ``get_current_user``, ``get_current_user_by_api_key``, or ``none``)
  - Inline guard summary (``role_check``, ``has_permission``, ``has_access``,
    ``_require_scim``, ``feature_flag``)

No runtime behavior changes — this is a static analysis tool.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_VERSION = "v1.0-2026-06-24"

ROUTER_GLOBS = [
    "backend/bcgpt/routers/**/*.py",
    "backend/bcgpt/agent/routers/**/*.py",
    "backend/bcgpt/compliance/routers/**/*.py",
    "backend/bcgpt/compliance/hitl/router.py",
]

EXCLUDE_FILES = {"__init__.py"}

# Dependency classification map — order matters for priority resolution.
DEPENDENCY_MAP = {
    "get_admin_user": "get_admin_user",
    "get_verified_user": "get_verified_user",
    "get_current_user_by_api_key": "get_current_user_by_api_key",
    "get_current_user": "get_current_user",
}

# Multi-method api_route support
HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}

# Inline check patterns
INLINE_PATTERNS = {
    "role_check": re.compile(r'user\.role\s*[!=]==?\s*["\']admin["\']'),
    "has_permission": re.compile(r"\bhas_permission\s*\("),
    "has_access": re.compile(r"\bhas_access\s*\("),
    "require_scim": re.compile(r"\b_require_scim\s*\("),
    "feature_flag": re.compile(
        r"(?:ENABLE_ADMIN|BYPASS_|COMPLIANCE_ENABLED|TOOLS_ALLOW|MFA_REQUIRED)"
    ),
}

# include_router prefix mapping (module basename → prefix).
# Parsed lazily from main.py at runtime.
PREFIX_MAP: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RouteRow:
    """One route endpoint."""

    method: str
    decorator_path: str
    full_path: str
    router_file: str
    line: int
    function_name: str
    dependency: str  # get_admin_user | get_verified_user | get_current_user | get_current_user_by_api_key | none
    inline_guards: list[str] = field(default_factory=list)

    @property
    def dependency_sort_key(self) -> int:
        order = [
            "get_admin_user",
            "get_verified_user",
            "get_current_user",
            "get_current_user_by_api_key",
            "none",
        ]
        try:
            return order.index(self.dependency)
        except ValueError:
            return 99


# ---------------------------------------------------------------------------
# Prefix resolution from main.py
# ---------------------------------------------------------------------------


def parse_prefix_map(main_py: Path) -> dict[str, str]:
    """Parse ``app.include_router(X.router, prefix="...", ...)`` from main.py."""
    mapping: dict[str, str] = {}
    if not main_py.exists():
        return mapping
    source = main_py.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(main_py))
    except SyntaxError:
        return mapping

    lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match app.include_router(...)
        if not (isinstance(func, ast.Attribute) and func.attr == "include_router"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "app"):
            continue

        # Extract module identifier from first positional arg.
        router_name = ""
        if node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Attribute) and isinstance(arg0.value, ast.Name):
                router_name = arg0.value.id  # e.g. "users" from users.router
            elif isinstance(arg0, ast.Name):
                router_name = arg0.id  # e.g. "hitl_router"

        # Extract prefix from keyword.
        prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                prefix = str(kw.value.value)

        if router_name:
            mapping[router_name] = prefix

    return mapping


def guess_prefix(router_file: Path) -> str:
    """Guess the include_router prefix for a router file based on its module name."""
    # Map file path to the router variable name used in main.py.
    # e.g. backend/bcgpt/routers/users.py → module "users"
    #      backend/bcgpt/compliance/routers/aiia.py → "compliance_aiia"
    parts = router_file.parts
    if "compliance" in parts:
        if "hitl" in parts:
            return PREFIX_MAP.get("hitl_router", "/api/v1/compliance/hitl")
        stem = router_file.stem  # e.g. "aiia"
        key = f"compliance_{stem}"
        return PREFIX_MAP.get(key, f"/api/v1/compliance/{stem}")
    if "agent" in parts:
        if "multi_agent" in router_file.name or "multi" in router_file.name:
            return PREFIX_MAP.get("multi_agent_router", "/api/v1/agents/multi-agent")
        return PREFIX_MAP.get("agents_router", "/api/v1/agents")
    # Standard routers
    stem = router_file.stem
    return PREFIX_MAP.get(stem, "")


# ---------------------------------------------------------------------------
# AST scanning
# ---------------------------------------------------------------------------


def extract_decorator_info(dec: ast.expr) -> tuple[str, str] | None:
    """Extract (method, path) from a route decorator.

    Returns ``None`` for non-route decorators.
    """
    # @router.get("/path")
    if isinstance(dec, ast.Call):
        func = dec.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id == "router":
                method = func.attr.lower()
                if method in HTTP_METHODS:
                    path = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = str(dec.args[0].value)
                    return (method.upper(), path)
                if method == "api_route":
                    # @router.api_route("/path", methods=["GET", "POST"])
                    path = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = str(dec.args[0].value)
                    methods: list[str] = []
                    for kw in dec.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, ast.List):
                            for elt in kw.value.elts:
                                if isinstance(elt, ast.Constant):
                                    methods.append(str(elt.value))
                    method_str = (
                        "+".join(m.upper() for m in methods) if methods else "API_ROUTE"
                    )
                    return (method_str, path)
    return None


def classify_dependency(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Classify the FastAPI dependency of a route function.

    Returns the highest-priority dependency found in function parameters.
    """
    found: set[str] = set()

    for arg in func_node.args.args + func_node.args.kwonlyargs:
        # Check default values: param=Depends(get_admin_user)
        pass

    # Check defaults for positional args
    defaults = func_node.args.defaults
    args_with_defaults = func_node.args.args[-len(defaults) :] if defaults else []
    for arg, default in zip(args_with_defaults, defaults):
        dep = _extract_depends_name(default)
        if dep:
            found.add(dep)

    # Check kwonly defaults: param=Depends(...)
    for arg, default in zip(func_node.args.kwonlyargs, func_node.args.kw_defaults):
        if default is None:
            continue
        dep = _extract_depends_name(default)
        if dep:
            found.add(dep)

    # Resolve by priority
    for dep_name in DEPENDENCY_MAP:
        if dep_name in found:
            return DEPENDENCY_MAP[dep_name]

    return "none"


def _extract_depends_name(node: ast.expr) -> str | None:
    """Extract the function name inside Depends(...)."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name) and func.id == "Depends":
        # Depends(get_admin_user)
        if node.args and isinstance(node.args[0], ast.Name):
            return node.args[0].id
        if node.args and isinstance(node.args[0], ast.Attribute):
            return node.args[0].attr
        # Depends(get_admin_user) with no args → return ""
        return ""
    return None


def scan_inline_guards(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]
) -> list[str]:
    """Scan the function body source for inline authorization checks."""
    start = func_node.lineno - 1
    end = func_node.end_lineno if func_node.end_lineno else start + 1
    body_text = "\n".join(source_lines[start:end])
    guards: list[str] = []
    for name, pattern in INLINE_PATTERNS.items():
        if pattern.search(body_text):
            guards.append(name)
    return guards


def scan_router_file(filepath: Path, source_lines: list[str]) -> list[RouteRow]:
    """Scan a single router file for route decorators."""
    source = "\n".join(source_lines)
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    rows: list[RouteRow] = []
    rel_file = str(filepath.relative_to(REPO_ROOT))
    prefix = guess_prefix(filepath)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Check decorators
        for dec in node.decorator_list:
            info = extract_decorator_info(dec)
            if info is None:
                continue
            method, decorator_path = info

            # Normalize decorator path: "" → "/", join with prefix
            if decorator_path == "":
                decorator_path_norm = "/"
            else:
                decorator_path_norm = decorator_path

            full_path = prefix + decorator_path if decorator_path else prefix + "/"

            dep = classify_dependency(node)
            guards = scan_inline_guards(node, source_lines)

            rows.append(
                RouteRow(
                    method=method,
                    decorator_path=decorator_path_norm,
                    full_path=full_path,
                    router_file=rel_file,
                    line=node.lineno,
                    function_name=node.name,
                    dependency=dep,
                    inline_guards=guards,
                )
            )
    return rows


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------


def collect_router_files() -> list[Path]:
    """Collect all router source files matching configured globs."""
    files: list[Path] = []
    for pattern in ROUTER_GLOBS:
        for p in (
            (REPO_ROOT / pattern).parent.glob(Path(pattern).name)
            if "*" not in Path(pattern).parent.name
            else []
        ):
            pass
        # Use glob from repo root
        for p in REPO_ROOT.glob(pattern):
            if p.name in EXCLUDE_FILES:
                continue
            if p.is_file() and p.suffix == ".py":
                files.append(p)
    # Deduplicate and sort
    seen = set()
    unique: list[Path] = []
    for p in files:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)
    return sorted(unique)


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def generate_markdown(rows: list[RouteRow], router_files: list[Path]) -> str:
    """Generate the route authorization inventory markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Count summaries
    dep_counts = Counter(r.dependency for r in rows)
    method_counts = Counter(r.method for r in rows)
    router_counts = Counter(r.router_file for r in rows)

    # Inline guard stats
    guard_counts: Counter[str] = Counter()
    routes_with_guards = 0
    for r in rows:
        if r.inline_guards:
            routes_with_guards += 1
            for g in r.inline_guards:
                guard_counts[g] += 1

    lines: list[str] = []
    lines.append("# Route Authorization Inventory (Generated)")
    lines.append("")
    lines.append(
        f"> **Extractor**: `scripts/extract_route_authorization.py` ({EXTRACTOR_VERSION})  "
    )
    lines.append(f"> **Generated**: {now}  ")
    lines.append(
        f"> **Source**: `backend/bcgpt/routers/`, `backend/bcgpt/agent/routers/`, `backend/bcgpt/compliance/`  "
    )
    lines.append(
        "> **Purpose**: Repeatable AST-based route authorization baseline per "
    )
    lines.append("> `ACCESS_CONTROL_ADMIN_GOVERNANCE_PLAN_2026-06-23.md` Phase 0.")
    lines.append("")

    # Summary metrics
    lines.append("## 1. Summary Metrics")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("| --- | ---: |")
    lines.append(f"| Router files scanned | {len(router_files)} |")
    lines.append(f"| Total route rows | {len(rows)} |")
    lines.append(f"| `get_admin_user` rows | {dep_counts.get('get_admin_user', 0)} |")
    lines.append(
        f"| `get_verified_user` rows | {dep_counts.get('get_verified_user', 0)} |"
    )
    lines.append(
        f"| `get_current_user` rows | {dep_counts.get('get_current_user', 0)} |"
    )
    lines.append(
        f"| `get_current_user_by_api_key` rows | {dep_counts.get('get_current_user_by_api_key', 0)} |"
    )
    lines.append(f"| No dependency rows | {dep_counts.get('none', 0)} |")
    lines.append(f"| Routes with inline guards | {routes_with_guards} |")
    lines.append("")

    # Method breakdown
    lines.append("## 2. HTTP Method Breakdown")
    lines.append("")
    lines.append("| Method | Count |")
    lines.append("| --- | ---: |")
    for method, count in sorted(method_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {method} | {count} |")
    lines.append("")

    # Router file breakdown
    lines.append("## 3. Router File Breakdown")
    lines.append("")
    lines.append("| Router file | Routes | Admin | Verified | Current | None |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for rf, total in sorted(router_counts.items(), key=lambda x: -x[1]):
        file_rows = [r for r in rows if r.router_file == rf]
        admin = sum(1 for r in file_rows if r.dependency == "get_admin_user")
        verified = sum(1 for r in file_rows if r.dependency == "get_verified_user")
        current = sum(
            1
            for r in file_rows
            if r.dependency in ("get_current_user", "get_current_user_by_api_key")
        )
        none = sum(1 for r in file_rows if r.dependency == "none")
        lines.append(
            f"| `{rf}` | {total} | {admin} | {verified} | {current} | {none} |"
        )
    lines.append("")

    # Inline guard breakdown
    lines.append("## 4. Inline Guard Breakdown")
    lines.append("")
    lines.append("| Guard pattern | Routes |")
    lines.append("| --- | ---: |")
    for guard, count in sorted(guard_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{guard}` | {count} |")
    lines.append("")

    # Full route table
    lines.append("## 5. Route Authorization Rows")
    lines.append("")
    lines.append("Sorted by dependency priority, then router file, then line number.")
    lines.append("")
    lines.append(
        "| Dependency | Method | Full Path | Router | Line | Function | Inline Guards |"
    )
    lines.append("| --- | --- | --- | --- | ---: | --- | --- |")
    for r in sorted(rows, key=lambda r: (r.dependency_sort_key, r.router_file, r.line)):
        guards_str = (
            ", ".join(f"`{g}`" for g in r.inline_guards) if r.inline_guards else "—"
        )
        lines.append(
            f"| `{r.dependency}` | {r.method} | `{r.full_path}` | `{r.router_file}` | {r.line} | `{r.function_name}` | {guards_str} |"
        )
    lines.append("")

    # Caveats
    lines.append("## 6. Extraction Caveats")
    lines.append("")
    lines.append(
        "- This static pass only sees FastAPI dependency injection in function parameters."
    )
    lines.append(
        "- Routes classified as `none` may have inline guards (`_require_scim`, `COMPLIANCE_ENABLED`)."
    )
    lines.append(
        "- Routes classified as `get_verified_user` typically have additional owner/ACL/permission checks"
    )
    lines.append(
        "  that are not captured by dependency classification alone — see inline guard column."
    )
    lines.append(
        "- Prefix resolution uses `main.py` `include_router` calls; sub-routers or dynamic includes may differ."
    )
    lines.append("- This inventory is a **baseline**, not a policy decision. See")
    lines.append(
        "  `docs/generated/AUTHORIZATION_POLICY_MATRIX.md` for the target authorization model."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    global PREFIX_MAP

    # Parse prefix map from main.py
    main_py = REPO_ROOT / "backend" / "bcgpt" / "main.py"
    PREFIX_MAP = parse_prefix_map(main_py)

    # Collect router files
    router_files = collect_router_files()
    if not router_files:
        print("ERROR: No router files found.", file=sys.stderr)
        return 1

    # Scan each file
    all_rows: list[RouteRow] = []
    for filepath in router_files:
        source_lines = filepath.read_text(encoding="utf-8").splitlines()
        rows = scan_router_file(filepath, source_lines)
        all_rows.extend(rows)

    # Generate markdown
    markdown = generate_markdown(all_rows, router_files)

    # Write output
    output_dir = REPO_ROOT / "docs" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ROUTE_AUTHORIZATION_INVENTORY.md"
    output_path.write_text(markdown, encoding="utf-8")

    # Print summary to stdout
    dep_counts = Counter(r.dependency for r in all_rows)
    print(f"Route authorization inventory generated: {output_path}")
    print(f"  Router files scanned: {len(router_files)}")
    print(f"  Total route rows:     {len(all_rows)}")
    print(f"  get_admin_user:       {dep_counts.get('get_admin_user', 0)}")
    print(f"  get_verified_user:    {dep_counts.get('get_verified_user', 0)}")
    print(f"  get_current_user:     {dep_counts.get('get_current_user', 0)}")
    print(
        f"  get_current_user_by_api_key: {dep_counts.get('get_current_user_by_api_key', 0)}"
    )
    print(f"  none:                 {dep_counts.get('none', 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
