#!/usr/bin/env python3
"""
Svelte-check ratchet gate.

Runs `svelte-check --output machine`, parses the result, and compares
against a committed baseline.  The gate **fails** if the total error
count has increased, preventing silent type-safety regressions.

Usage:
    python scripts/check_ratchet.py           # Check against baseline (CI gate)
    python scripts/check_ratchet.py --update  # Update baseline to current counts
    python scripts/check_ratchet.py --init    # Create initial baseline

Exit codes:
    0 — pass (errors <= baseline)
    1 — fail  (errors >  baseline)
    2 — svelte-check itself failed to run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# ── constants ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = REPO_ROOT / ".svelte-check-baseline.json"
BASELINE_VERSION = "1.0.0"

# Machine output line patterns
#   <ts> ERROR   "<file>" <line>:<col> "<message>"
#   <ts> WARNING "<file>" <line>:<col> "<message>"
#   <ts> COMPLETED <total_files> FILES <errors> ERRORS <warnings> WARNINGS <files_with_problems> FILES_WITH_PROBLEMS
DIAG_RE = re.compile(r'^\d+\s+(ERROR|WARNING)\s+"(.+?)"\s+\d+:\d+\s+"', re.MULTILINE)
COMPLETED_RE = re.compile(
    r"(\d+)\s+ERRORS\s+(\d+)\s+WARNINGS\s+(\d+)\s+FILES_WITH_PROBLEMS"
)

# Permissive threshold: allow up to N errors above baseline before failing.
# Useful during large refactors. Default 0 (strict).
DEFAULT_TOLERANCE = 0


# ── core logic ─────────────────────────────────────────────────────────────


def run_svelte_check() -> tuple[str, int]:
    """Run svelte-check and return (stdout, exit_code)."""
    proc = subprocess.run(
        ["bunx", "svelte-check", "--output", "machine"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )
    # svelte-check always exits 1 when errors exist — that's expected.
    return proc.stdout + proc.stderr, proc.returncode


def parse_output(raw: str) -> dict:
    """Parse machine output into structured result."""
    # COMPLETED summary line
    m = COMPLETED_RE.search(raw)
    if not m:
        raise RuntimeError(
            "Could not find COMPLETED summary line in svelte-check output.\n"
            "Raw output (last 500 chars):\n" + raw[-500:]
        )
    total_errors = int(m.group(1))
    total_warnings = int(m.group(2))
    files_with_problems = int(m.group(3))

    # Per-file breakdown
    per_file: dict[str, dict[str, int]] = defaultdict(
        lambda: {"errors": 0, "warnings": 0}
    )
    for match in DIAG_RE.finditer(raw):
        severity, fpath = match.group(1), match.group(2)
        if severity == "ERROR":
            per_file[fpath]["errors"] += 1
        else:
            per_file[fpath]["warnings"] += 1

    return {
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "files_with_problems": files_with_problems,
        "per_file": dict(
            sorted(
                per_file.items(),
                key=lambda x: -(x[1]["errors"] + x[1]["warnings"]),
            )
        ),
    }


def load_baseline() -> dict | None:
    """Load baseline from disk, or None if not present."""
    if not BASELINE_FILE.exists():
        return None
    with open(BASELINE_FILE) as f:
        return json.load(f)


def save_baseline(result: dict) -> None:
    """Write current result as new baseline."""
    baseline = {
        "version": BASELINE_VERSION,
        "baseline_date": date.today().isoformat(),
        "tool": "svelte-check",
        "command": "bunx svelte-check --output machine",
        "total_errors": result["total_errors"],
        "total_warnings": result["total_warnings"],
        "files_with_problems": result["files_with_problems"],
        "per_file": result["per_file"],
    }
    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2, sort_keys=False)
        f.write("\n")


def print_diff(baseline: dict, current: dict) -> None:
    """Print human-readable diff between baseline and current."""
    b_err = baseline["total_errors"]
    c_err = current["total_errors"]
    b_warn = baseline["total_warnings"]
    c_warn = current["total_warnings"]
    b_files = baseline["files_with_problems"]
    c_files = current["files_with_problems"]

    err_delta = c_err - b_err
    warn_delta = c_warn - b_warn
    file_delta = c_files - b_files

    def sign(n: int) -> str:
        return f"+{n}" if n > 0 else str(n)

    print()
    print("=" * 60)
    print("SVELTE-CHECK RATCHET REPORT")
    print("=" * 60)
    print(f"  Errors:   {c_err:>5}  (baseline {b_err}, delta {sign(err_delta)})")
    print(f"  Warnings: {c_warn:>5}  (baseline {b_warn}, delta {sign(warn_delta)})")
    print(f"  Files:    {c_files:>5}  (baseline {b_files}, delta {sign(file_delta)})")
    print()

    # Per-file deltas (top 10 worsened)
    b_pf = baseline.get("per_file", {})
    c_pf = current["per_file"]

    worsened = []
    improved = []
    new_files = []

    all_files = set(b_pf.keys()) | set(c_pf.keys())
    for f in all_files:
        b_e = b_pf.get(f, {}).get("errors", 0)
        c_e = c_pf.get(f, {}).get("errors", 0)
        delta = c_e - b_e
        if delta > 0:
            if f not in b_pf:
                new_files.append((f, c_e))
            else:
                worsened.append((f, delta, b_e, c_e))
        elif delta < 0:
            improved.append((f, delta, b_e, c_e))

    if worsened:
        worsened.sort(key=lambda x: -x[1])
        print(f"WORSENED FILES ({len(worsened)}):")
        for f, delta, old, new in worsened[:10]:
            print(f"  {f}: {old} -> {new} ({sign(delta)})")
        if len(worsened) > 10:
            print(f"  ... and {len(worsened) - 10} more")
        print()

    if new_files:
        new_files.sort(key=lambda x: -x[1])
        print(f"NEW FILES WITH ERRORS ({len(new_files)}):")
        for f, cnt in new_files[:10]:
            print(f"  {f}: {cnt} errors")
        if len(new_files) > 10:
            print(f"  ... and {len(new_files) - 10} more")
        print()

    if improved:
        improved.sort(key=lambda x: x[1])
        print(f"IMPROVED FILES ({len(improved)}):")
        for f, delta, old, new in improved[:10]:
            print(f"  {f}: {old} -> {new} ({sign(delta)})")
        if len(improved) > 10:
            print(f"  ... and {len(improved) - 10} more")
        print()


# ── CLI ────────────────────────────────────────────────────────────────────


def cmd_init() -> int:
    """Create initial baseline."""
    if BASELINE_FILE.exists():
        print(f"Baseline already exists at {BASELINE_FILE}")
        print("Use --update to refresh it.")
        return 1
    print("Running svelte-check to capture initial baseline...")
    raw, _ = run_svelte_check()
    result = parse_output(raw)
    save_baseline(result)
    print(f"Baseline saved to {BASELINE_FILE}")
    print(f"  Errors:   {result['total_errors']}")
    print(f"  Warnings: {result['total_warnings']}")
    print(f"  Files:    {result['files_with_problems']}")
    return 0


def cmd_update() -> int:
    """Update baseline to current counts (use after fixing errors)."""
    print("Running svelte-check to capture current counts...")
    raw, _ = run_svelte_check()
    result = parse_output(raw)
    old = load_baseline()
    save_baseline(result)
    print(f"Baseline updated at {BASELINE_FILE}")
    if old:
        print(f"  Errors:   {old['total_errors']} -> {result['total_errors']}")
        print(f"  Warnings: {old['total_warnings']} -> {result['total_warnings']}")
        print(
            f"  Files:    {old['files_with_problems']} -> {result['files_with_problems']}"
        )
    else:
        print(f"  Errors:   {result['total_errors']}")
        print(f"  Warnings: {result['total_warnings']}")
        print(f"  Files:    {result['files_with_problems']}")
    return 0


def cmd_check(tolerance: int) -> int:
    """Run check against baseline."""
    baseline = load_baseline()
    if baseline is None:
        print(f"ERROR: No baseline found at {BASELINE_FILE}")
        print("Run `python scripts/check_ratchet.py --init` first.")
        return 2

    print("Running svelte-check...")
    try:
        raw, _ = run_svelte_check()
    except subprocess.TimeoutExpired:
        print("ERROR: svelte-check timed out after 300s")
        return 2
    except FileNotFoundError:
        print("ERROR: `bunx` not found. Is Bun installed?")
        return 2

    try:
        result = parse_output(raw)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 2

    print_diff(baseline, result)

    b_err = baseline["total_errors"]
    c_err = result["total_errors"]
    delta = c_err - b_err

    if delta <= tolerance:
        if delta < 0:
            print(f"PASS: Error count improved by {-delta}.")
            print(
                f"  Run `python scripts/check_ratchet.py --update` to lock in the improvement."
            )
        elif delta == 0:
            print("PASS: Error count unchanged.")
        else:
            print(
                f"PASS: Error count increased by {delta} (within tolerance {tolerance})."
            )
        return 0
    else:
        print(f"FAIL: Error count increased by {delta} (tolerance: {tolerance}).")
        print(f"  Baseline: {b_err} errors")
        print(f"  Current:  {c_err} errors")
        print()
        print("Fix the new errors, or if they are expected:")
        print("  1. Run `python scripts/check_ratchet.py --update`")
        print("  2. Commit the updated baseline with an explanation.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Svelte-check ratchet gate")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init", action="store_true", help="Create initial baseline")
    group.add_argument(
        "--update",
        action="store_true",
        help="Update baseline to current counts",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE,
        help=f"Allow up to N errors above baseline (default: {DEFAULT_TOLERANCE})",
    )
    args = parser.parse_args()

    if args.init:
        return cmd_init()
    elif args.update:
        return cmd_update()
    else:
        return cmd_check(args.tolerance)


if __name__ == "__main__":
    sys.exit(main())
