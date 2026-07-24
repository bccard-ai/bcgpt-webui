"""Security header middleware for BCGPT WebUI.

Applies a set of HTTP security headers to every response, including
Content-Security-Policy, Strict-Transport-Security, X-Frame-Options,
and others.  Each header can be overridden or customised via an
environment variable of the same name.

Public exports (re-exported via ``bcgpt.utils.__init__``):
    SecurityHeadersMiddleware,
    set_security_headers,
    set_hsts, set_xframe, set_permissions_policy, set_referrer,
    set_cache_control, set_xdownload_options, set_xcontent_type,
    set_xpermitted_cross_domain_policies, set_content_security_policy
"""

from __future__ import annotations

import os
import re
from typing import Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Validation regex patterns
# ---------------------------------------------------------------------------

_RE_HSTS = re.compile(
    r"^max-age=(\d+)(;includeSubDomains)?(;preload)?$", re.IGNORECASE
)
_RE_XFRAME = re.compile(r"^(DENY|SAMEORIGIN)$", re.IGNORECASE)
_RE_PERMISSIONS = re.compile(
    r"^(?:(accelerometer|autoplay|camera|clipboard-read|clipboard-write"
    r"|fullscreen|geolocation|gyroscope|magnetometer|microphone|midi"
    r"|payment|picture-in-picture|sync-xhr|usb|xr-spatial-tracking)"
    r"=\((self)?\),?)*$",
    re.IGNORECASE,
)
_RE_REFERRER = re.compile(
    r"^(no-referrer|no-referrer-when-downgrade|origin"
    r"|origin-when-cross-origin|same-origin|strict-origin"
    r"|strict-origin-when-cross-origin|unsafe-url)$",
    re.IGNORECASE,
)
_RE_CACHE_CONTROL = re.compile(
    r"^(public|private|no-cache|no-store|must-revalidate|proxy-revalidate"
    r"|max-age=\d+|s-maxage=\d+|no-transform|immutable)"
    r"(,\s*(public|private|no-cache|no-store|must-revalidate"
    r"|proxy-revalidate|max-age=\d+|s-maxage=\d+|no-transform|immutable))*$",
    re.IGNORECASE,
)
_RE_CROSS_DOMAIN = re.compile(
    r"^(none|master-only|by-content-type|by-ftp-filename)$", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Default Content-Security-Policy
# ---------------------------------------------------------------------------

# Production CSP for BCGPT WebUI deployments.
# - ``unsafe-inline`` is required for Svelte compiled CSS (transitions).
# - ``unsafe-eval`` is required for the built-in code editor (Monaco/CodeMirror).
# These can be tightened with nonce-based CSP in a future iteration.
_CSP_DEFAULT = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self'; "
    "connect-src 'self' https: wss:; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'"
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects security headers into every response.

    The header set is determined by :func:`set_security_headers`, which
    reads environment variables for overrides and supplies secure defaults.
    """

    async def dispatch(self, request: Request, call_next):
        """Apply security headers after the downstream handler returns."""
        response = await call_next(request)
        response.headers.update(set_security_headers())
        return response


# ---------------------------------------------------------------------------
# Header construction
# ---------------------------------------------------------------------------


def set_security_headers() -> Dict[str, str]:
    """Build the complete security header dictionary.

    Reads the following environment variables and validates each value
    through its associated setter function:

    .. list-table::
       :header-rows: 1

       * - Env Variable
         - Header
       * - ``CACHE_CONTROL``
         - ``Cache-Control``
       * - ``HSTS``
         - ``Strict-Transport-Security``
       * - ``PERMISSIONS_POLICY``
         - ``Permissions-Policy``
       * - ``REFERRER_POLICY``
         - ``Referrer-Policy``
       * - ``XCONTENT_TYPE``
         - ``X-Content-Type-Options``
       * - ``XDOWNLOAD_OPTIONS``
         - ``X-Download-Options``
       * - ``XFRAME_OPTIONS``
         - ``X-Frame-Options``
       * - ``XPERMITTED_CROSS_DOMAIN_POLICIES``
         - ``X-Permitted-Cross-Domain-Policies``
       * - ``CONTENT_SECURITY_POLICY``
         - ``Content-Security-Policy``

    If an env var is not set, a secure default is used instead.

    Returns:
        A dict mapping header names to their values.
    """
    options: Dict[str, str] = {}

    header_setters = {
        "CACHE_CONTROL": set_cache_control,
        "HSTS": set_hsts,
        "PERMISSIONS_POLICY": set_permissions_policy,
        "REFERRER_POLICY": set_referrer,
        "XCONTENT_TYPE": set_xcontent_type,
        "XDOWNLOAD_OPTIONS": set_xdownload_options,
        "XFRAME_OPTIONS": set_xframe,
        "XPERMITTED_CROSS_DOMAIN_POLICIES": set_xpermitted_cross_domain_policies,
        "CONTENT_SECURITY_POLICY": set_content_security_policy,
    }

    for env_var, setter in header_setters.items():
        value = os.environ.get(env_var)
        if value:
            header = setter(value)
            if header:
                options.update(header)

    # Secure-by-default headers (overridable via the env vars above).
    # SAMEORIGIN (not DENY) so the app's own same-origin iframes (artifact /
    # HTML file previews) keep working while cross-origin clickjacking is
    # blocked.
    options.setdefault("X-Content-Type-Options", "nosniff")
    options.setdefault("X-Frame-Options", "SAMEORIGIN")
    options.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

    # HSTS enabled by default for production HTTPS.
    options.setdefault(
        "Strict-Transport-Security",
        "max-age=31536000;includeSubDomains",
    )

    # CSP enabled by default.  Override via CONTENT_SECURITY_POLICY env var.
    options.setdefault("Content-Security-Policy", _CSP_DEFAULT)

    return options


# ---------------------------------------------------------------------------
# Individual header setters
# ---------------------------------------------------------------------------


def set_hsts(value: str) -> Dict[str, str]:
    """Set the ``Strict-Transport-Security`` header.

    Falls back to ``max-age=31536000;includeSubDomains`` on invalid input.
    """
    if not _RE_HSTS.match(value):
        value = "max-age=31536000;includeSubDomains"
    return {"Strict-Transport-Security": value}


def set_xframe(value: str) -> Dict[str, str]:
    """Set the ``X-Frame-Options`` header.

    Accepts ``DENY`` or ``SAMEORIGIN``.  Falls back to ``DENY``.
    """
    if not _RE_XFRAME.match(value):
        value = "DENY"
    return {"X-Frame-Options": value}


def set_permissions_policy(value: str) -> Dict[str, str]:
    """Set the ``Permissions-Policy`` header.

    Falls back to ``none`` on invalid input.
    """
    if not _RE_PERMISSIONS.match(value):
        value = "none"
    return {"Permissions-Policy": value}


def set_referrer(value: str) -> Dict[str, str]:
    """Set the ``Referrer-Policy`` header.

    Falls back to ``no-referrer`` on invalid input.
    """
    if not _RE_REFERRER.match(value):
        value = "no-referrer"
    return {"Referrer-Policy": value}


def set_cache_control(value: str) -> Dict[str, str]:
    """Set the ``Cache-Control`` header.

    Falls back to ``no-store, max-age=0`` on invalid input.
    """
    if not _RE_CACHE_CONTROL.match(value):
        value = "no-store, max-age=0"
    return {"Cache-Control": value}


def set_xdownload_options(value: str) -> Dict[str, str]:
    """Set the ``X-Download-Options`` header.

    Always resolves to ``noopen`` (IE-specific; no other value is useful).
    """
    if value != "noopen":
        value = "noopen"
    return {"X-Download-Options": value}


def set_xcontent_type(value: str) -> Dict[str, str]:
    """Set the ``X-Content-Type-Options`` header.

    Always resolves to ``nosniff``.
    """
    if value != "nosniff":
        value = "nosniff"
    return {"X-Content-Type-Options": value}


def set_xpermitted_cross_domain_policies(value: str) -> Dict[str, str]:
    """Set the ``X-Permitted-Cross-Domain-Policies`` header.

    Accepts ``none``, ``master-only``, ``by-content-type``, or
    ``by-ftp-filename``.  Falls back to ``none``.
    """
    if not _RE_CROSS_DOMAIN.match(value):
        value = "none"
    return {"X-Permitted-Cross-Domain-Policies": value}


def set_content_security_policy(value: str) -> Dict[str, str]:
    """Set the ``Content-Security-Policy`` header.

    The value is passed through as-is; CSP syntax is too complex to
    validate with a single regex.
    """
    return {"Content-Security-Policy": value}
