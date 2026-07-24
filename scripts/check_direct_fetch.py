#!/usr/bin/env python3
"""
Direct fetch ratchet gate.

Scans src/**/*.ts and src/**/*.svelte for direct fetch() calls that
bypass the central ApiClient (src/lib/apis/client.ts). Compares findings
against the committed allowlist (.direct-fetch-allowlist.json) and exits
non-zero when unclassified entries are detected.

Usage:
    python scripts/check_direct_fetch.py             # Check mode (CI gate)
    python scripts/check_direct_fetch.py --update     # Update allowlist with current findings
    python scripts/check_direct_fetch.py --verbose    # Show all matches including allowlisted

Part of the API Client unification governance:
    docs/API_CONTRACT_CLIENT_GOVERNANCE_PLAN_2026-06-23.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = REPO_ROOT / ".direct-fetch-allowlist.json"
SRC_DIR = REPO_ROOT / "src"
GLOB_PATTERNS = ("**/*.ts", "**/*.svelte")
EXCLUDE_DIRS = {"__tests__", "node_modules", ".svelte-kit", "static"}
EXCLUDE_SUFFIXES = (".test.ts", ".spec.ts")
FETCH_RE = re.compile(r"\bfetch\s*\(")


@dataclass
class FetchCall:
    """A single direct fetch() invocation found in source."""

    file: str  # repo-relative path
    line: int  # 1-based line number
    content: str  # trimmed line content
    snippet: str  # first 80 chars for matching


@dataclass
class AllowlistEntry:
    file: str
    line: int
    snippet: str
    family: str
    auth_mode: str
    response_mode: str
    reason: str


@dataclass
class CheckResult:
    total_found: int = 0
    allowlisted: int = 0
    new_entries: list[FetchCall] = field(default_factory=list)
    removed_entries: list[AllowlistEntry] = field(default_factory=list)


def should_exclude(path: Path) -> bool:
    """Check if a file should be excluded from scanning."""
    parts = path.parts
    for excl in EXCLUDE_DIRS:
        if excl in parts:
            return True
    for suffix in EXCLUDE_SUFFIXES:
        if path.name.endswith(suffix):
            return True
    return False


def scan_source_files() -> list[FetchCall]:
    """Scan all source files for direct fetch() calls."""
    calls: list[FetchCall] = []
    for pattern in GLOB_PATTERNS:
        for filepath in sorted(SRC_DIR.glob(pattern)):
            if should_exclude(filepath):
                continue
            rel = str(filepath.relative_to(REPO_ROOT))
            try:
                lines = filepath.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, PermissionError):
                continue
            for i, line in enumerate(lines, 1):
                if FETCH_RE.search(line):
                    trimmed = line.strip()
                    snippet = trimmed[:80]
                    calls.append(
                        FetchCall(file=rel, line=i, content=trimmed, snippet=snippet)
                    )
    return calls


def load_allowlist() -> tuple[list[AllowlistEntry], list[str]]:
    """Load the committed allowlist. Returns (entries, exclude_files)."""
    if not ALLOWLIST_PATH.exists():
        return [], []
    data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = [
        AllowlistEntry(
            file=e["file"],
            line=e["line"],
            snippet=e["snippet"],
            family=e["family"],
            auth_mode=e["auth_mode"],
            response_mode=e["response_mode"],
            reason=e["reason"],
        )
        for e in data.get("entries", [])
    ]
    return entries, data.get("exclude_files", [])


def match_key(entry: FetchCall | AllowlistEntry) -> str:
    """Stable matching key: file path + line number.

    Each fetch() call on a specific line is unique. When code above shifts
    line numbers, run --update to refresh the allowlist.
    """
    return f"{entry.file}::{entry.line}"


def run_check(verbose: bool = False) -> CheckResult:
    """Compare current findings against allowlist."""
    found = scan_source_files()
    allowlist, exclude_files = load_allowlist()

    # Build exclude set (ApiClient itself is supposed to call fetch)
    exclude_set = set(exclude_files)

    # Filter out excluded files
    relevant = [c for c in found if c.file not in exclude_set]

    # Build allowlist key set
    allowed_keys = {match_key(e) for e in allowlist}

    result = CheckResult(total_found=len(relevant), allowlisted=0)
    found_keys = set()

    for call in relevant:
        key = match_key(call)
        found_keys.add(key)
        if key in allowed_keys:
            result.allowlisted += 1
            if verbose:
                print(f"  [OK] {call.file}:{call.line} — {call.snippet}")
        else:
            result.new_entries.append(call)

    # Detect removed entries (in allowlist but no longer in source)
    for entry in allowlist:
        if match_key(entry) not in found_keys:
            result.removed_entries.append(entry)

    return result


def update_allowlist() -> None:
    """Update the allowlist JSON with current findings (preserving metadata for existing entries)."""
    found = scan_source_files()
    old_entries, exclude_files = load_allowlist()

    # Build lookup of old entries by key
    old_by_key: dict[str, AllowlistEntry] = {}
    for e in old_entries:
        old_by_key[match_key(e)] = e

    # Exclude ApiClient itself
    exclude_set = set(exclude_files)
    relevant = [c for c in found if c.file not in exclude_set]

    new_entries = []
    for call in relevant:
        key = match_key(call)
        if key in old_by_key:
            # Preserve existing metadata, update line number
            old = old_by_key[key]
            new_entries.append(
                {
                    "file": call.file,
                    "line": call.line,
                    "snippet": call.snippet,
                    "family": old.family,
                    "auth_mode": old.auth_mode,
                    "response_mode": old.response_mode,
                    "reason": old.reason,
                }
            )
        else:
            # New unclassified entry — add with placeholder metadata
            new_entries.append(
                {
                    "file": call.file,
                    "line": call.line,
                    "snippet": call.snippet,
                    "family": "unclassified",
                    "auth_mode": "unknown",
                    "response_mode": "unknown",
                    "reason": "TODO: classify this direct fetch call",
                }
            )
            print(f"  [NEW] {call.file}:{call.line} — {call.snippet}")

    output = {
        "version": "v1.0-2026-06-24",
        "description": "Allowlist of direct fetch() calls that are exempt from ApiClient migration. See docs/generated/API_CLIENT_DIRECT_FETCH_CATALOG.md for rationale.",
        "exclude_files": list(exclude_files),
        "entries": sorted(new_entries, key=lambda e: (e["file"], e["line"])),
    }

    ALLOWLIST_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"\nUpdated {ALLOWLIST_PATH.relative_to(REPO_ROOT)} ({len(new_entries)} entries)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct fetch ratchet gate")
    parser.add_argument(
        "--update", action="store_true", help="Update allowlist with current findings"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all matches including allowlisted",
    )
    args = parser.parse_args()

    if args.update:
        update_allowlist()
        return 0

    result = run_check(verbose=args.verbose)

    print(
        f"Direct fetch scan: {result.total_found} found, {result.allowlisted} allowlisted"
    )

    if result.removed_entries:
        print(
            f"\n  [INFO] {len(result.removed_entries)} allowlist entries no longer in source:"
        )
        for e in result.removed_entries:
            print(f"    - {e.file}:{e.line} ({e.family}) — {e.snippet[:60]}")
        print("  Run 'python scripts/check_direct_fetch.py --update' to clean up.")

    if result.new_entries:
        print(
            f"\n  [FAIL] {len(result.new_entries)} unclassified direct fetch call(s):"
        )
        for c in result.new_entries:
            print(f"    - {c.file}:{c.line} — {c.snippet}")
        print("\n  Either migrate to ApiClient or add to .direct-fetch-allowlist.json")
        print("  with proper family/auth_mode/response_mode classification.")
        return 1

    print("  [PASS] All direct fetch calls are classified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
