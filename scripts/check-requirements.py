#!/usr/bin/env python3
"""Verify every pinned package in backend/requirements.txt is installed.

Exits 0 when all required distributions are present in the active interpreter,
1 otherwise (and prints the missing names, comma-separated, to stdout).

Called by scripts/watch-backend.js to decide whether `pip install -r` is needed.

Why this exists: the previous startup check only tested `import uvicorn` plus a
hash of requirements.txt. That heuristic silently accepts a *drifted* or
partially-populated environment — e.g. deps were once installed into a different
interpreter than the one now running uvicorn, so the hash matches but packages
are actually missing. Verifying *every* requirement catches that drift instead
of assuming.

Usage:
    python scripts/check-requirements.py                 # checks backend/requirements.txt
    python scripts/check-requirements.py path/to/req.txt # checks an explicit file
"""

from __future__ import annotations

import importlib.metadata as md
import pathlib
import re
import sys

# Leading distribution name per PEP 508 (before any extras / specifier / marker).
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_URL_SCHEMES = ("git+", "hg+", "svn+", "bzr+", "http://", "https://")
_INLINE_OPTIONS = (
    "-r ",
    "--requirement ",
    "-e ",
    "--editable ",
    "-f ",
    "--find-links ",
)


def iter_requirement_names(path: pathlib.Path, _seen: set[pathlib.Path] | None = None):
    """Yield distribution names required by a requirements file (recursing -r)."""
    path = path.resolve()
    if _seen is None:
        _seen = set()
    if path in _seen:
        return
    _seen.add(path)

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Nested requirements file -> recurse.
        if line.startswith(_INLINE_OPTIONS) and (
            line.startswith(("-r ", "--requirement "))
        ):
            nested = line.split(None, 1)[1].strip()
            yield from iter_requirement_names(path.parent / nested, _seen)
            continue

        # Any other pip option (-e, -f, --index-url, --hash, ...) or a VCS/URL
        # dependency: skip — we can't verify these by distribution name.
        if line.startswith("-") or line.startswith(_URL_SCHEMES):
            continue
        if "@" in line and "://" in line:
            continue

        # Drop environment markers ("pkg ; python_version < ..."). We check the
        # package unconditionally; if a marker would exclude it for this env,
        # the worst case is a harmless `pip install` that no-ops.
        line = line.split(";", 1)[0].strip()

        match = _NAME_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        # Strip extras: "pkg[foo,bar]" -> "pkg".
        name = name.split("[", 1)[0]
        if name:
            yield name


def main(argv: list[str]) -> int:
    default = (
        pathlib.Path(__file__).resolve().parent.parent / "backend" / "requirements.txt"
    )
    req_path = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else default

    missing = []
    for name in iter_requirement_names(req_path):
        try:
            md.version(name)
        except md.PackageNotFoundError:
            missing.append(name)

    if missing:
        # Stable, machine-parseable line for the watcher; dedupe + preserve order.
        unique = list(dict.fromkeys(missing))
        print("MISSING_PACKAGES:" + ",".join(unique))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
