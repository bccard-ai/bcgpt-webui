"""Magic-byte file signature validation. Re-implemented from open-moai `lib/security/file-validator.ts`
(Apache-2.0). Hand-rolled signature table incl. WebP dual-offset RIFF check. Fail-secure on read
errors. Blocks extension/MIME spoofing in the RAG ingest path."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Signature table
# Each entry: (canonical_type, checks) where checks is a list of (offset, expected_bytes).
# ALL checks in a single entry must match (AND logic).
# Entries are evaluated in order; first full match wins.
# ---------------------------------------------------------------------------
_SIGNATURES: list[tuple[str, list[tuple[int, bytes]]]] = [
    # WebP must come before WAV because both start with RIFF
    ("webp", [(0, b"RIFF"), (8, b"WEBP")]),
    ("wav", [(0, b"RIFF"), (8, b"WAVE")]),
    ("pdf", [(0, b"%PDF")]),
    ("png", [(0, b"\x89PNG\r\n\x1a\n")]),
    ("jpeg", [(0, b"\xff\xd8\xff")]),
    ("gif", [(0, b"GIF87a")]),
    ("gif", [(0, b"GIF89a")]),
    ("zip", [(0, b"PK\x03\x04")]),
    ("zip", [(0, b"PK\x05\x06")]),
    ("zip", [(0, b"PK\x07\x08")]),
    ("ole", [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")]),
    ("rtf", [(0, b"{\\rtf")]),
    ("bmp", [(0, b"BM")]),
    ("mp3", [(0, b"ID3")]),
    ("mp3", [(0, b"\xff\xfb")]),
]


def detect_file_type(contents: bytes) -> str | None:
    """Return the canonical type string (e.g. 'pdf','png','jpeg','gif','webp','zip','ole','rtf',
    'bmp','mp3','wav') by inspecting magic bytes (incl. WebP/WAV dual-offset). None if no known
    signature matches."""
    if not contents or not isinstance(contents, bytes):
        return None

    for canonical_type, checks in _SIGNATURES:
        matched = True
        for offset, magic in checks:
            end = offset + len(magic)
            if len(contents) < end or contents[offset:end] != magic:
                matched = False
                break
        if matched:
            return canonical_type

    return None


# ---------------------------------------------------------------------------
# Extension -> acceptable canonical types
# ---------------------------------------------------------------------------
_EXT_TO_TYPES: dict[str, set[str]] = {
    "pdf": {"pdf"},
    "png": {"png"},
    "jpg": {"jpeg"},
    "jpeg": {"jpeg"},
    "gif": {"gif"},
    "webp": {"webp"},
    "bmp": {"bmp"},
    "docx": {"zip"},
    "xlsx": {"zip"},
    "pptx": {"zip"},
    "zip": {"zip"},
    "doc": {"ole"},
    "xls": {"ole"},
    "ppt": {"ole"},
    "rtf": {"rtf"},
    "mp3": {"mp3"},
    "wav": {"wav"},
}

_UNVERIFIABLE_TEXT_EXTS: set[str] = {
    "txt",
    "csv",
    "md",
    "markdown",
    "json",
    "log",
    "tsv",
    "html",
    "htm",
    "xml",
    "yaml",
    "yml",
}


def validate_file_signature(
    contents: bytes,
    filename: str,
    declared_content_type: str | None = None,
) -> tuple[bool, str]:
    """Cross-check magic bytes against the filename extension.

    Rules:
      - contents falsy or not bytes  -> (False, 'unreadable or empty file')  [FAIL-SECURE]
      - no extension                 -> (False, 'missing file extension')
      - ext in _UNVERIFIABLE_TEXT_EXTS -> (True, 'text type (signature not enforced)')
      - ext in _EXT_TO_TYPES:
            detected in allowed set  -> (True, 'ok: <type>')
            detected is None         -> (False, 'no recognizable signature for .<ext>')
            detected mismatches      -> (False, 'signature mismatch: .<ext> file has <detected> content')
      - ext not in either table      -> (True, 'extension not subject to signature validation')

    Never raises; wraps detection in try/except -> (False, 'validation error') on unexpected error.
    """
    try:
        # Fail-secure: unreadable / empty
        if not contents or not isinstance(contents, bytes):
            return (False, "unreadable or empty file")

        # Extract extension
        dot_idx = filename.rfind(".")
        if dot_idx == -1 or dot_idx == len(filename) - 1:
            return (False, "missing file extension")
        ext = filename[dot_idx + 1 :].lower()

        # Plain-text types — cannot magic-validate; allow
        if ext in _UNVERIFIABLE_TEXT_EXTS:
            return (True, "text type (signature not enforced)")

        # Known binary types
        if ext in _EXT_TO_TYPES:
            detected = detect_file_type(contents)
            allowed = _EXT_TO_TYPES[ext]

            if detected in allowed:
                return (True, f"ok: {detected}")

            if detected is None:
                return (False, f"no recognizable signature for .{ext}")

            return (False, f"signature mismatch: .{ext} file has {detected} content")

        # Extension not in any table — not our problem here; blocklist handles dangerous exts
        return (True, "extension not subject to signature validation")

    except Exception:
        return (False, "validation error")
