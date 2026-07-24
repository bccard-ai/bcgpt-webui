#!/usr/bin/env python3
"""Repeatable config/env inventory extractor.

Scans Python source (AST), frontend JS/TS (regex), and deployment manifests
(.env.example, Dockerfile, docker-compose, Helm, GitHub Actions) to produce a
raw, machine-generated inventory of every environment/configuration key.

Outputs:
  - docs/generated/CONFIG_INVENTORY.md  (sorted unique-key rows + summaries)
  - docs/generated/CONFIG_INVENTORY_DIFF.md  (drift vs previous baseline)

Usage:
  python scripts/extract_config_inventory.py
  make config-inventory

Extractor scope is documented in
docs/CONFIG_INVENTORY_GENERATION_RUNBOOK_2026-06-23.md §3.

This is a REPORT-ONLY baseline generator. Heuristic secret_guess and owner_guess
fields MUST be reviewed before production use. See runbook §9 acceptance criteria.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXTRACTOR_VERSION = "v1.0-2026-06-23"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_INVENTORY = REPO_ROOT / "docs" / "generated" / "CONFIG_INVENTORY.md"
OUTPUT_DIFF = REPO_ROOT / "docs" / "generated" / "CONFIG_INVENTORY_DIFF.md"
CONFIG_REFERENCE = REPO_ROOT / "docs" / "CONFIG_REFERENCE.md"

# Python source globs (runbook §3.1)
PY_INCLUDE_DIRS = ["backend/bcgpt", "scripts"]
PY_EXCLUDE_DIRS = {"static", "test", "tests", "__pycache__", ".pytest_cache"}
PY_EXCLUDE_FILES = {"extract_config_inventory.py"}

# Frontend/script globs (runbook §3.2)
FE_INCLUDE_GLOBS = [
    "vite.config.ts",
    "src/**/*.ts",
    "src/**/*.svelte",
    "src/**/*.js",
    "scripts/**/*.js",
]

# Deployment files (runbook §3.3)
ENV_EXAMPLE = REPO_ROOT / ".env.example"
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_GLOB = "docker-compose*.yml"
HELM_VALUES = REPO_ROOT / "kubernetes" / "helm" / "values.yaml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Env-helper function names that wrap os.environ.get
ENV_HELPER_FUNCS = {
    "_env_bool",
    "_env_int",
    "_env_float",
    "_env_str",
    "_env_str_or_none",
}

# Secret-like substring heuristic
SECRET_SUBSTRINGS = (
    "SECRET",
    "KEY",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "CREDENTIAL",
    "PRIVATE",
    "API_KEY",
    "ACCESS_KEY",
    "CLIENT_SECRET",
)

# Owner-guess prefix mapping (ordered by specificity)
OWNER_PREFIX_MAP = [
    ("RAG", "rag/retrieval"),
    ("ENABLE", "platform"),
    ("SECURITY", "compliance/security"),
    ("OAUTH", "auth/security"),
    ("LDAP", "auth/security"),
    ("SCIM", "auth/security"),
    ("AUDIO", "model/provider"),
    ("OLLAMA", "model/provider"),
    ("OPENAI", "model/provider"),
    ("ANTHROPIC", "model/provider"),
    ("CLAUDE", "model/provider"),
    ("GEMINI", "model/provider"),
    ("LITELLM", "model/provider"),
    ("AUTOMATIC1111", "model/provider"),
    ("COMPLIANCE", "compliance/security"),
    ("AUDIT", "observability/audit"),
    ("DSAR", "compliance/security"),
    ("GOOGLE", "model/provider"),
    ("MICROSOFT", "model/provider"),
    ("AZURE", "storage/files"),
    ("S3", "storage/files"),
    ("GCS", "storage/files"),
    ("STORAGE", "storage/files"),
    ("DATABASE", "platform"),
    ("REDIS", "platform"),
    ("WEBSOCKET", "realtime/platform"),
    ("REALTIME", "realtime/platform"),
    ("HANDOFF", "compliance/security"),
    ("QUALITY", "platform"),
    ("AGENT", "platform"),
    ("BCGPT", "platform"),
    ("USER", "platform"),
    ("VITE", "frontend/platform"),
    ("PUBLIC", "frontend/platform"),
    ("APP", "frontend/platform"),
    ("FRONTEND", "frontend/platform"),
    ("DOCKER", "infra/platform"),
    ("PORT", "infra/platform"),
    ("HOST", "infra/platform"),
    ("DATA_DIR", "infra/platform"),
    ("STATIC_DIR", "infra/platform"),
    ("FRONTS_DIR", "infra/platform"),
    ("ENV", "platform"),
    ("USE_CUDA", "infra/platform"),
    ("GLOBAL_LOG_LEVEL", "observability/audit"),
    ("CORS", "infra/platform"),
    ("AIOHTTP", "infra/platform"),
    ("TRUSTED", "auth/security"),
    ("PIP", "infra/platform"),
    ("CHUNK", "rag/retrieval"),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RawRecord:
    """A single source-level observation of an env/config key."""

    key: str
    source_type: str  # PersistentConfig, env-only, BaseSettings, frontend-build, frontend-public, script-env, deployment-only, example-only
    read_type: str  # PersistentConfig, _env_bool, os.environ.get, os.getenv, process.env, vite.define, etc.
    source_file: str  # relative to repo root
    source_line: int
    persistent_path: str = ""  # dot path for PersistentConfig
    default_expr: str = ""

    def location(self) -> str:
        return f"{self.source_file}:{self.source_line}"


@dataclass
class AggregatedRow:
    """One row per unique key, merging all raw records."""

    key: str
    source_types: set[str] = field(default_factory=set)
    read_types: set[str] = field(default_factory=set)
    first_source: str = ""  # file:line of earliest observation
    all_sources: list[str] = field(default_factory=list)
    source_count: int = 0
    persistent_path: str = ""
    default_expr: str = ""
    lifecycle_guess: str = "unknown"
    deployment_exposure: str = "missing"
    secret_guess: str = "public-config"
    curation_state: str = "uncurated"
    owner_guess: str = "platform"


# ---------------------------------------------------------------------------
# Python AST scanner
# ---------------------------------------------------------------------------


class PythonEnvVisitor(ast.NodeVisitor):
    """Walk a Python AST and collect env/config key references."""

    def __init__(self, filepath: str, records: list[RawRecord]) -> None:
        self.filepath = filepath
        self.records = records
        self._class_stack: list[str] = []
        self._is_basesettings = False

    def _add(
        self,
        key: str,
        source_type: str,
        read_type: str,
        line: int,
        persistent_path: str = "",
        default_expr: str = "",
    ) -> None:
        if not key or not key.replace("_", "").isalnum():
            return
        # Skip lowercase/dynamic keys unless they look like env vars
        if key != key.upper() and not key.isupper():
            return
        self.records.append(
            RawRecord(
                key=key.upper(),
                source_type=source_type,
                read_type=read_type,
                source_file=self.filepath,
                source_line=line,
                persistent_path=persistent_path,
                default_expr=default_expr,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        was_bs = self._is_basesettings
        self._is_basesettings = any(
            (isinstance(b, ast.Name) and b.id == "BaseSettings")
            or (isinstance(b, ast.Attribute) and b.attr == "BaseSettings")
            for b in node.bases
        )
        # Collect annotated assignments in BaseSettings class body
        if self._is_basesettings:
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ):
                    key = stmt.target.id
                    default = ""
                    if stmt.value is not None:
                        try:
                            default = ast.unparse(stmt.value)
                        except Exception:
                            default = "<expr>"
                    self._add(
                        key,
                        "BaseSettings",
                        "BaseSettings-field",
                        stmt.lineno,
                        default_expr=default,
                    )
        self.generic_visit(node)
        self._is_basesettings = was_bs
        self._class_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        func_name = ""
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr

        # PersistentConfig("KEY", "config.path", default)
        if func_name == "PersistentConfig":
            if node.args and isinstance(node.args[0], ast.Constant):
                key = node.args[0].value
                path = ""
                default = ""
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    path = str(node.args[1].value)
                if len(node.args) > 2:
                    try:
                        default = ast.unparse(node.args[2])
                    except Exception:
                        default = "<expr>"
                self._add(
                    str(key),
                    "PersistentConfig",
                    "PersistentConfig",
                    node.lineno,
                    persistent_path=path,
                    default_expr=default,
                )

        # _env_bool("KEY"), _env_int("KEY"), _env_str("KEY"), etc.
        elif func_name in ENV_HELPER_FUNCS:
            if node.args and isinstance(node.args[0], ast.Constant):
                key = node.args[0].value
                default = ""
                if len(node.args) > 1:
                    try:
                        default = ast.unparse(node.args[1])
                    except Exception:
                        default = "<expr>"
                self._add(
                    str(key), "env-only", func_name, node.lineno, default_expr=default
                )

        elif func_name in ("get", "setdefault"):
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "os"
                and func.value.attr == "environ"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    default = ""
                    if len(node.args) > 1:
                        try:
                            default = ast.unparse(node.args[1])
                        except Exception:
                            default = "<expr>"
                    self._add(
                        str(key),
                        "env-only",
                        f"os.environ.{func_name}",
                        node.lineno,
                        default_expr=default,
                    )
        elif func_name == "getenv":
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    default = ""
                    if len(node.args) > 1:
                        try:
                            default = ast.unparse(node.args[1])
                        except Exception:
                            default = "<expr>"
                    self._add(
                        str(key),
                        "env-only",
                        "os.getenv",
                        node.lineno,
                        default_expr=default,
                    )

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # os.environ["KEY"] or os.environ[KEY]
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
            and node.value.attr == "environ"
        ):
            key_node = node.slice
            if isinstance(key_node, ast.Constant):
                self._add(str(key_node.value), "env-only", "os.environ[]", node.lineno)
        self.generic_visit(node)


def scan_python_file(filepath: Path, relative_path: str) -> list[RawRecord]:
    """Parse one Python file and return env key records."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return []
    records: list[RawRecord] = []

    # Walk for PersistentConfig, _env_*, BaseSettings
    visitor = PythonEnvVisitor(relative_path, records)
    visitor.visit(tree)

    # Regex fallback for os.environ.get/getenv that AST visitor may miss
    # (e.g., complex expressions or chained calls)
    source = filepath.read_text(encoding="utf-8")
    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        for m in re.finditer(
            r'os\.(?:environ\.get|getenv)\(\s*["\']([A-Z][A-Z0-9_]+)["\']', line
        ):
            key = m.group(1)
            if not any(
                r.key == key and r.source_file == relative_path and r.source_line == i
                for r in records
            ):
                records.append(
                    RawRecord(
                        key=key,
                        source_type="env-only",
                        read_type="os.environ.get",
                        source_file=relative_path,
                        source_line=i,
                    )
                )
        for m in re.finditer(
            r'os\.environ\.setdefault\(\s*["\']([A-Z][A-Z0-9_]+)["\']', line
        ):
            key = m.group(1)
            if not any(
                r.key == key and r.source_file == relative_path and r.source_line == i
                for r in records
            ):
                records.append(
                    RawRecord(
                        key=key,
                        source_type="env-only",
                        read_type="os.environ.setdefault",
                        source_file=relative_path,
                        source_line=i,
                    )
                )
        if i < len(lines):
            multiline = re.match(r"^.*os\.(?:environ\.get|getenv)\(\s*$", line)
            if multiline:
                next_line = lines[i].strip() if i < len(lines) else ""
                key_m = re.match(r'^["\']([A-Z][A-Z0-9_]+)["\']', next_line)
                if key_m:
                    key = key_m.group(1)
                    if not any(
                        r.key == key
                        and r.source_file == relative_path
                        and r.source_line == i
                        for r in records
                    ):
                        records.append(
                            RawRecord(
                                key=key,
                                source_type="env-only",
                                read_type="os.environ.get",
                                source_file=relative_path,
                                source_line=i,
                            )
                        )

    return records


def scan_python_sources() -> list[RawRecord]:
    """Scan all Python source directories."""
    records: list[RawRecord] = []
    for include_dir in PY_INCLUDE_DIRS:
        base = REPO_ROOT / include_dir
        if not base.exists():
            continue
        for pyfile in base.rglob("*.py"):
            rel = str(pyfile.relative_to(REPO_ROOT))
            # Exclude by directory
            parts = pyfile.parts
            if any(exc in parts for exc in PY_EXCLUDE_DIRS):
                continue
            if pyfile.name in PY_EXCLUDE_FILES:
                continue
            records.extend(scan_python_file(pyfile, rel))
    return records


# ---------------------------------------------------------------------------
# Frontend scanner (regex-based)
# ---------------------------------------------------------------------------

FE_PATTERN = re.compile(r"(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]+)")
VITE_DEFINE_PATTERN = re.compile(r"(?:VITE_|PUBLIC_|APP_)([A-Z][A-Z0-9_]+)")


def scan_frontend_sources() -> list[RawRecord]:
    """Scan frontend JS/TS/Svelte/Vite files for env references."""
    records: list[RawRecord] = []
    for pattern in FE_INCLUDE_GLOBS:
        for filepath in REPO_ROOT.glob(pattern):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(REPO_ROOT))
            try:
                source = filepath.read_text(encoding="utf-8")
            except Exception:
                continue
            for i, line in enumerate(source.splitlines(), 1):
                # process.env.KEY / import.meta.env.KEY
                for m in FE_PATTERN.finditer(line):
                    key = m.group(1)
                    source_type = "frontend-build"
                    if key.startswith("PUBLIC_"):
                        source_type = "frontend-public"
                    records.append(
                        RawRecord(
                            key=process_fe_key(line, key),
                            source_type=source_type,
                            read_type=(
                                "process.env"
                                if "process.env" in line
                                else "import.meta.env"
                            ),
                            source_file=rel,
                            source_line=i,
                        )
                    )
                # VITE_* defines in vite.config.ts
                if "vite.config" in rel:
                    for m in VITE_DEFINE_PATTERN.finditer(line):
                        full_key = m.group(0)
                        records.append(
                            RawRecord(
                                key=full_key,
                                source_type="frontend-build",
                                read_type="vite.define",
                                source_file=rel,
                                source_line=i,
                            )
                        )
    return records


def process_fe_key(line: str, matched_key: str) -> str:
    """Determine the full env key from a frontend line."""
    # Special cases: process.env.npm_package_version etc.
    lower_keys = {"npm_package_version", "bun_package_version"}
    if matched_key.lower() in lower_keys:
        return matched_key.upper()
    # APP_BUILD_HASH is a known define
    if "APP_BUILD_HASH" in line:
        return "APP_BUILD_HASH"
    return matched_key


# ---------------------------------------------------------------------------
# Deployment manifest scanner
# ---------------------------------------------------------------------------


def scan_env_example() -> list[RawRecord]:
    """Parse .env.example for KEY=value lines (including commented)."""
    records: list[RawRecord] = []
    if not ENV_EXAMPLE.exists():
        return records
    rel = str(ENV_EXAMPLE.relative_to(REPO_ROOT))
    source = ENV_EXAMPLE.read_text(encoding="utf-8")
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip("# ").strip()
        m = re.match(r"^([A-Z][A-Z0-9_]+)\s*=", stripped)
        if m:
            records.append(
                RawRecord(
                    key=m.group(1),
                    source_type="example-only",
                    read_type=".env.example",
                    source_file=rel,
                    source_line=i,
                )
            )
    return records


def scan_dockerfile() -> list[RawRecord]:
    """Parse Dockerfile ENV and ARG directives."""
    records: list[RawRecord] = []
    if not DOCKERFILE.exists():
        return records
    rel = str(DOCKERFILE.relative_to(REPO_ROOT))
    source = DOCKERFILE.read_text(encoding="utf-8")
    # Handle multi-line ENV blocks: ENV KEY=val KEY2=val2 (backslash continuation)
    # Also handle: ENV KEY=val
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        # ENV KEY=value or ENV KEY=value KEY2=value2
        env_match = re.match(r"^(?:ENV\s+)(.+)", stripped)
        arg_match = re.match(r"^(?:ARG\s+)([A-Z][A-Z0-9_]+)", stripped)
        if env_match:
            rest = env_match.group(1)
            # Extract all KEY= patterns
            for km in re.finditer(r"\b([A-Z][A-Z0-9_]+)\s*=", rest):
                records.append(
                    RawRecord(
                        key=km.group(1),
                        source_type="deployment-only",
                        read_type="Dockerfile-ENV",
                        source_file=rel,
                        source_line=i,
                    )
                )
        if arg_match:
            records.append(
                RawRecord(
                    key=arg_match.group(1),
                    source_type="deployment-only",
                    read_type="Dockerfile-ARG",
                    source_file=rel,
                    source_line=i,
                )
            )
    return records


def scan_compose_files() -> list[RawRecord]:
    """Parse docker-compose*.yml for environment entries."""
    records: list[RawRecord] = []
    if yaml is None:
        return records
    for compose_file in REPO_ROOT.glob(COMPOSE_GLOB):
        rel = str(compose_file.relative_to(REPO_ROOT))
        try:
            data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        line_offset = _build_line_map(compose_file.read_text(encoding="utf-8"))
        for service_name, service in (data.get("services") or {}).items():
            if not isinstance(service, dict):
                continue
            env_list = service.get("environment")
            if isinstance(env_list, list):
                for env_item in env_list:
                    if isinstance(env_item, str):
                        key = env_item.split("=")[0].split(":")[0].strip()
                        if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                            records.append(
                                RawRecord(
                                    key=key,
                                    source_type="deployment-only",
                                    read_type="compose-environment",
                                    source_file=rel,
                                    source_line=_find_line(line_offset, key, rel),
                                )
                            )
            elif isinstance(env_list, dict):
                for key in env_list:
                    if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                        records.append(
                            RawRecord(
                                key=key,
                                source_type="deployment-only",
                                read_type="compose-environment",
                                source_file=rel,
                                source_line=_find_line(line_offset, key, rel),
                            )
                        )
    return records


def scan_helm() -> list[RawRecord]:
    """Parse Helm values.yaml env and secrets sections."""
    records: list[RawRecord] = []
    if not HELM_VALUES.exists() or yaml is None:
        return records
    rel = str(HELM_VALUES.relative_to(REPO_ROOT))
    try:
        data = yaml.safe_load(HELM_VALUES.read_text(encoding="utf-8"))
    except Exception:
        return records
    if not isinstance(data, dict):
        return records
    line_offset = _build_line_map(HELM_VALUES.read_text(encoding="utf-8"))
    # env: section → helm-env-or-values
    env_section = data.get("env")
    if isinstance(env_section, dict):
        for key in env_section:
            if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                records.append(
                    RawRecord(
                        key=key,
                        source_type="deployment-only",
                        read_type="helm-values-env",
                        source_file=rel,
                        source_line=_find_line(line_offset, key, rel),
                    )
                )
    # secrets: section → helm-secret-or-values
    secrets_section = data.get("secrets")
    if isinstance(secrets_section, dict):
        for key in secrets_section:
            if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                records.append(
                    RawRecord(
                        key=key,
                        source_type="deployment-only",
                        read_type="helm-values-secret",
                        source_file=rel,
                        source_line=_find_line(line_offset, key, rel),
                    )
                )
    return records


def scan_workflows() -> list[RawRecord]:
    """Parse GitHub Actions workflow env injections."""
    records: list[RawRecord] = []
    if yaml is None or not WORKFLOWS_DIR.exists():
        return records
    for wf_file in WORKFLOWS_DIR.glob("*.yml"):
        rel = str(wf_file.relative_to(REPO_ROOT))
        try:
            data = yaml.safe_load(wf_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        line_map = _build_line_map(wf_file.read_text(encoding="utf-8"))
        _collect_workflow_env(data, rel, line_map, records, path_parts=[])
    return records


def _collect_workflow_env(
    node, rel: str, line_map, records: list, path_parts: list
) -> None:
    """Recursively walk workflow YAML to find env: blocks."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "env" and isinstance(val, dict):
                for env_key in val:
                    if re.match(r"^[A-Z][A-Z0-9_]*$", str(env_key)):
                        records.append(
                            RawRecord(
                                key=str(env_key),
                                source_type="deployment-only",
                                read_type="github-workflows-env",
                                source_file=rel,
                                source_line=_find_line(line_map, str(env_key), rel),
                            )
                        )
            _collect_workflow_env(val, rel, line_map, records, path_parts + [key])
    elif isinstance(node, list):
        for item in node:
            _collect_workflow_env(item, rel, line_map, records, path_parts)


def _build_line_map(source: str) -> dict[str, int]:
    """Build a map from first chars of each line to line number."""
    result: dict[str, int] = {}
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip()
        if stripped:
            # Use first 30 chars as key for disambiguation
            result[stripped[:30]] = i
    return result


def _find_line(line_map: dict[str, int], key: str, rel: str) -> int:
    """Best-effort line number for a key in a YAML file."""
    for prefix, lineno in line_map.items():
        if key in prefix:
            return lineno
    return 0


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_records(records: list[RawRecord]) -> dict[str, AggregatedRow]:
    """Merge raw records into unique-key rows."""
    rows: dict[str, AggregatedRow] = {}

    # Load curated keys from CONFIG_REFERENCE.md
    curated_keys = load_curated_keys()

    for rec in records:
        if rec.key not in rows:
            row = AggregatedRow(key=rec.key)
            rows[rec.key] = row
        else:
            row = rows[rec.key]

        row.source_types.add(rec.source_type)
        row.read_types.add(rec.read_type)
        row.source_count += 1
        row.all_sources.append(rec.location())

        # Track first source (earliest by file:line)
        loc = rec.location()
        if not row.first_source or loc < row.first_source:
            row.first_source = loc

        if rec.persistent_path and not row.persistent_path:
            row.persistent_path = rec.persistent_path
        if rec.default_expr and not row.default_expr:
            row.default_expr = rec.default_expr

    # Post-process each row
    for row in rows.values():
        _classify_row(row, curated_keys)

    return rows


def load_curated_keys() -> set[str]:
    """Extract backtick-quoted uppercase keys from CONFIG_REFERENCE.md."""
    if not CONFIG_REFERENCE.exists():
        return set()
    source = CONFIG_REFERENCE.read_text(encoding="utf-8")
    return set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", source))


def _classify_row(row: AggregatedRow, curated_keys: set[str]) -> None:
    """Apply heuristic classification to an aggregated row."""

    # lifecycle_guess
    types = row.source_types
    if "BaseSettings" in types:
        row.lifecycle_guess = "startup-validation"
    elif "PersistentConfig" in types:
        row.lifecycle_guess = "persistent-seed/db-admin"
    elif "frontend-build" in types or "vite.define" in row.read_types:
        row.lifecycle_guess = "build-time"
    elif types <= {"deployment-only", "example-only"}:
        row.lifecycle_guess = "deployment-only"
    elif "script-env" in types:
        row.lifecycle_guess = "script/runtime"
    elif "env-only" in types:
        row.lifecycle_guess = "env-only/restart"
    else:
        row.lifecycle_guess = "unknown"

    # deployment_exposure
    exposures = []
    if "example-only" in types:
        exposures.append(".env.example")
    read_set = row.read_types
    if any("compose" in r for r in read_set):
        exposures.append("compose")
    if any("helm-values-env" in r for r in read_set):
        exposures.append("helm-env-or-values")
    if any("helm-values-secret" in r for r in read_set):
        exposures.append("helm-secret-or-values")
    if any("Dockerfile" in r for r in read_set):
        exposures.append("dockerfile")
    if any("github-workflows" in r for r in read_set):
        exposures.append("ci")

    # Also check if key appears in deployment sources via source_types
    if "deployment-only" in types:
        if not exposures:
            # Need to check the actual read_type
            for rt in read_set:
                if "compose" in rt and "compose" not in exposures:
                    exposures.append("compose")
                elif "helm-values-env" in rt and "helm-env-or-values" not in exposures:
                    exposures.append("helm-env-or-values")
                elif (
                    "helm-values-secret" in rt
                    and "helm-secret-or-values" not in exposures
                ):
                    exposures.append("helm-secret-or-values")
                elif "Dockerfile" in rt and "dockerfile" not in exposures:
                    exposures.append("dockerfile")

    if not exposures and not types.isdisjoint(
        {"PersistentConfig", "env-only", "BaseSettings"}
    ):
        row.deployment_exposure = "missing"
    elif exposures:
        row.deployment_exposure = ", ".join(sorted(set(exposures)))
    else:
        row.deployment_exposure = "missing"

    # secret_guess
    if any(s in row.key for s in SECRET_SUBSTRINGS):
        row.secret_guess = "secret-like"
    else:
        row.secret_guess = "public-config"

    # curation_state
    if row.key in curated_keys:
        row.curation_state = "curated"
    elif types == {"deployment-only"} or types == {"deployment-only", "example-only"}:
        row.curation_state = "deployment-only"
    elif types == {"example-only"}:
        row.curation_state = "uncurated"
    else:
        row.curation_state = "uncurated"

    # owner_guess
    row.owner_guess = _guess_owner(row.key)


def _guess_owner(key: str) -> str:
    """Infer owner from key prefix."""
    for prefix, owner in OWNER_PREFIX_MAP:
        if key.startswith(prefix):
            return owner
    return "platform"


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def generate_inventory_markdown(
    rows: dict[str, AggregatedRow],
    raw_count: int,
    py_files_scanned: int,
) -> str:
    """Generate the CONFIG_INVENTORY.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    sorted_keys = sorted(rows.keys())

    # Build count summaries
    source_type_counts: dict[str, int] = defaultdict(int)
    for row in rows.values():
        for st in row.source_types:
            # Normalize: deployment records from different files count as deployment-only
            source_type_counts[st] += 1

    prefix_counts: dict[str, int] = defaultdict(int)
    for key in sorted_keys:
        prefix = key.split("_")[0] if "_" in key else key
        prefix_counts[prefix] += 1

    curation_counts: dict[str, int] = defaultdict(int)
    for row in rows.values():
        curation_counts[row.curation_state] += 1

    deployment_counts: dict[str, int] = defaultdict(int)
    for row in rows.values():
        deployment_counts[row.deployment_exposure] += 1

    owner_counts: dict[str, int] = defaultdict(int)
    for row in rows.values():
        owner_counts[row.owner_guess] += 1

    lines: list[str] = []
    lines.append("# Generated Config Inventory - 2026-06-23")
    lines.append("")
    lines.append(
        "This is a **machine-generated** raw inventory produced by "
        "`scripts/extract_config_inventory.py` (extractor "
        f"`{EXTRACTOR_VERSION}`)."
    )
    lines.append("")
    lines.append(
        "The extractor scope is documented in "
        "`docs/CONFIG_INVENTORY_GENERATION_RUNBOOK_2026-06-23.md` §3."
    )
    lines.append("")
    lines.append(
        "Important: this is a report-only baseline, not an owner-approved "
        "production config reference. Heuristic `secret_guess` and "
        "`owner_guess` fields MUST be reviewed. Curated operator guidance "
        "remains in `docs/CONFIG_REFERENCE.md`."
    )
    lines.append("")

    # Extractor Metadata
    lines.append("## Extractor Metadata")
    lines.append("")
    lines.append(
        "| Field                         | Value                                                                              |"
    )
    lines.append(
        "| ----------------------------- | ---------------------------------------------------------------------------------- |"
    )
    lines.append(
        f"| extractor_version             | {EXTRACTOR_VERSION}                                                                |"
    )
    lines.append(
        f"| generated_at                  | {now}                                                                              |"
    )
    lines.append(
        f"| repository_root               | {REPO_ROOT}                                                                        |"
    )
    lines.append(
        f"| python_files_scanned          | {py_files_scanned}                                                                 |"
    )
    lines.append(
        f"| raw_records                   | {raw_count}                                                                        |"
    )
    lines.append(
        f"| unique_keys                   | {len(sorted_keys)}                                                                 |"
    )
    pc_keys = sum(1 for r in rows.values() if "PersistentConfig" in r.source_types)
    lines.append(
        f"| persistent_config_unique_keys | {pc_keys}                                                                          |"
    )
    lines.append(
        "| curated_reference_match       | heuristic exact backtick key match against docs/CONFIG_REFERENCE.md                |"
    )
    lines.append(
        "| deployment_exposure           | .env.example, Dockerfile, docker-compose\\*.yml, kubernetes/helm, .github/workflows |"
    )
    lines.append(
        "| regeneration_command          | `python scripts/extract_config_inventory.py` or `make config-inventory`            |"
    )
    lines.append("")

    # Count Summary
    lines.append("## Count Summary")
    lines.append("")

    # Source Types
    lines.append("### Raw Record Source Types")
    lines.append("")
    lines.append("| source_type      | records |")
    lines.append("| ---------------- | ------- |")
    for st in sorted(source_type_counts, key=lambda x: -source_type_counts[x]):
        lines.append(f"| {st:<16} | {source_type_counts[st]:>7} |")
    lines.append("")

    # Top Prefixes
    lines.append("### Top Prefixes")
    lines.append("")
    lines.append("| prefix        | unique_keys |")
    lines.append("| ------------- | ----------- |")
    for prefix in sorted(prefix_counts, key=lambda x: -prefix_counts[x])[:20]:
        lines.append(f"| {prefix:<13} | {prefix_counts[prefix]:>11} |")
    lines.append("")

    # Curation State
    lines.append("### Curation State")
    lines.append("")
    lines.append("| curation_state  | unique_keys |")
    lines.append("| --------------- | ----------- |")
    for cs in sorted(curation_counts, key=lambda x: -curation_counts[x]):
        lines.append(f"| {cs:<15} | {curation_counts[cs]:>11} |")
    lines.append("")

    # Deployment Exposure
    lines.append("### Deployment Exposure")
    lines.append("")
    lines.append("| deployment_exposure                          | unique_keys |")
    lines.append("| -------------------------------------------- | ----------- |")
    for de in sorted(deployment_counts, key=lambda x: -deployment_counts[x]):
        lines.append(f"| {de:<44} | {deployment_counts[de]:>11} |")
    lines.append("")

    # Owner Guess
    lines.append("### Owner Guess")
    lines.append("")
    lines.append("| owner_guess         | unique_keys |")
    lines.append("| ------------------- | ----------- |")
    for og in sorted(owner_counts, key=lambda x: -owner_counts[x]):
        lines.append(f"| {og:<19} | {owner_counts[og]:>11} |")
    lines.append("")

    # Unique Key Rows
    lines.append("## Unique Key Rows")
    lines.append("")
    lines.append(
        "| key | source_types | first_source | sources | lifecycle | deployment | secret_guess | curation | owner_guess |"
    )
    lines.append(
        "| --- | ------------ | ------------ | ------- | --------- | ---------- | ------------ | -------- | ----------- |"
    )
    for key in sorted_keys:
        row = rows[key]
        st_str = ", ".join(sorted(row.source_types))
        lines.append(
            f"| {row.key} | {st_str} | {row.first_source} | {row.source_count} | "
            f"{row.lifecycle_guess} | {row.deployment_exposure} | "
            f"{row.secret_guess} | {row.curation_state} | {row.owner_guess} |"
        )
    lines.append("")

    # Source-level records (machine-readable appendix)
    lines.append("## Raw Source Records (Appendix)")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Click to expand full 1:many source records</summary>")
    lines.append("")
    lines.append(
        "| key | source_type | read_type | source_file:line | persistent_path | default_expr |"
    )
    lines.append(
        "| --- | ----------- | --------- | ---------------- | --------------- | ------------ |"
    )
    # This appendix would be too large; we skip it for now
    lines.append("| _(see script JSON output for full 1:many records)_ | | | | | |")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff generation
# ---------------------------------------------------------------------------


def load_previous_keys() -> set[str]:
    """Extract keys from the existing committed CONFIG_INVENTORY.md."""
    if not OUTPUT_INVENTORY.exists():
        return set()
    source = OUTPUT_INVENTORY.read_text(encoding="utf-8")
    # Keys are in the Unique Key Rows table, first column after |
    keys = set()
    for line in source.splitlines():
        m = re.match(r"^\|\s+([A-Z][A-Z0-9_]{2,})\s+\|", line)
        if m and m.group(1) not in {"source_types", "Field"}:
            keys.add(m.group(1))
    return keys


def generate_diff_markdown(
    current_keys: set[str],
    previous_keys: set[str],
    current_rows: dict[str, AggregatedRow],
) -> str:
    """Generate CONFIG_INVENTORY_DIFF.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    new_keys = sorted(current_keys - previous_keys)
    removed_keys = sorted(previous_keys - current_keys)

    # Deployment-only keys (in deployment but not in source)
    deployment_only = sorted(
        k
        for k in current_keys
        if current_rows[k].source_types == {"deployment-only"}
        or current_rows[k].source_types == {"deployment-only", "example-only"}
    )
    # Example-only keys
    example_only = sorted(
        k
        for k in current_keys
        if "example-only" in current_rows[k].source_types
        and not (
            current_rows[k].source_types
            & {"PersistentConfig", "env-only", "BaseSettings"}
        )
    )

    lines: list[str] = []
    lines.append("# Generated Config Inventory Diff - 2026-06-23")
    lines.append("")
    lines.append(
        f"Generated by `scripts/extract_config_inventory.py` ({EXTRACTOR_VERSION}) on {now}."
    )
    lines.append("")
    lines.append(
        "Compares the current generated inventory against the previously committed baseline."
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("| ------ | ----- |")
    lines.append(f"| Total current unique keys | {len(current_keys)} |")
    lines.append(f"| Total previous unique keys | {len(previous_keys)} |")
    lines.append(f"| New keys (added) | {len(new_keys)} |")
    lines.append(f"| Removed keys | {len(removed_keys)} |")
    lines.append(f"| Deployment-only keys | {len(deployment_only)} |")
    lines.append(f"| Example-only keys (no source) | {len(example_only)} |")
    lines.append("")

    if new_keys:
        lines.append("## New Source Keys")
        lines.append("")
        lines.append(
            "These keys appear in the current inventory but were not in the previous baseline."
        )
        lines.append("")
        lines.append("| key | source_types | first_source |")
        lines.append("| --- | ------------ | ------------ |")
        for key in new_keys:
            row = current_rows[key]
            lines.append(
                f"| {key} | {', '.join(sorted(row.source_types))} | {row.first_source} |"
            )
        lines.append("")

    if removed_keys:
        lines.append("## Removed Source Keys")
        lines.append("")
        lines.append(
            "These keys were in the previous baseline but are no longer found in source."
        )
        lines.append("")
        lines.append("| key |")
        lines.append("| --- |")
        for key in removed_keys:
            lines.append(f"| {key} |")
        lines.append("")

    if deployment_only:
        lines.append("## Deployment-Only Keys")
        lines.append("")
        lines.append(
            "These keys appear in deployment manifests (Helm/Compose/Dockerfile/.env.example) "
            "but have no source-level read. They require owner classification: launcher, "
            "external dependency, dead config, or candidate."
        )
        lines.append("")
        lines.append("| key | deployment |")
        lines.append("| --- | ---------- |")
        for key in deployment_only:
            row = current_rows[key]
            lines.append(f"| {key} | {row.deployment_exposure} |")
        lines.append("")

    if example_only:
        lines.append("## Example-Only Keys")
        lines.append("")
        lines.append(
            "These keys appear in `.env.example` but have no source-level read. "
            "Verify alias/deprecated docs."
        )
        lines.append("")
        lines.append("| key |")
        lines.append("| --- |")
        for key in example_only:
            lines.append(f"| {key} |")
        lines.append("")

    if not new_keys and not removed_keys:
        lines.append("## No Changes Detected")
        lines.append("")
        lines.append("The current inventory matches the previous baseline exactly.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the full extraction pipeline."""
    print(f"[config-inventory] Extractor {EXTRACTOR_VERSION}")
    print(f"[config-inventory] Repository root: {REPO_ROOT}")

    # Phase 1: Scan Python sources
    print("[config-inventory] Scanning Python sources...")
    py_records = scan_python_sources()
    py_files = len(set(r.source_file for r in py_records))
    print(f"  → {len(py_records)} records from {py_files} Python files")

    # Phase 2: Scan frontend sources
    print("[config-inventory] Scanning frontend sources...")
    fe_records = scan_frontend_sources()
    print(f"  → {len(fe_records)} records from frontend/script files")

    # Phase 3: Scan deployment manifests
    print("[config-inventory] Scanning deployment manifests...")
    env_records = scan_env_example()
    docker_records = scan_dockerfile()
    compose_records = scan_compose_files()
    helm_records = scan_helm()
    workflow_records = scan_workflows()
    deploy_total = (
        len(env_records)
        + len(docker_records)
        + len(compose_records)
        + len(helm_records)
        + len(workflow_records)
    )
    print(
        f"  → {deploy_total} deployment records "
        f"(env.example={len(env_records)}, Dockerfile={len(docker_records)}, "
        f"compose={len(compose_records)}, helm={len(helm_records)}, workflows={len(workflow_records)})"
    )

    # Combine all records
    all_records = (
        py_records
        + fe_records
        + env_records
        + docker_records
        + compose_records
        + helm_records
        + workflow_records
    )
    print(f"[config-inventory] Total raw records: {len(all_records)}")

    # Phase 4: Aggregate
    print("[config-inventory] Aggregating unique keys...")
    rows = aggregate_records(all_records)
    print(f"  → {len(rows)} unique keys")

    # Phase 5: Load previous keys for diff
    print("[config-inventory] Loading previous baseline...")
    previous_keys = load_previous_keys()
    print(f"  → {len(previous_keys)} keys in previous baseline")

    # Phase 6: Generate markdown
    print("[config-inventory] Generating inventory markdown...")
    inventory_md = generate_inventory_markdown(rows, len(all_records), py_files)

    print("[config-inventory] Generating diff markdown...")
    diff_md = generate_diff_markdown(set(rows.keys()), previous_keys, rows)

    # Phase 7: Write output files
    OUTPUT_INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_INVENTORY.write_text(inventory_md + "\n", encoding="utf-8")
    print(f"  → wrote {OUTPUT_INVENTORY.relative_to(REPO_ROOT)}")

    OUTPUT_DIFF.write_text(diff_md + "\n", encoding="utf-8")
    print(f"  → wrote {OUTPUT_DIFF.relative_to(REPO_ROOT)}")

    print(
        f"[config-inventory] Done. {len(rows)} unique keys, "
        f"{len(all_records)} raw records."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
