import secrets
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from bcgpt.env import (
    BCGPT_AUTH_COOKIE_SAME_SITE,
    BCGPT_AUTH_COOKIE_SECURE,
)

log = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
AUTH_COOKIE_NAME = "token"


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Double-submit-cookie CSRF protection scoped to the cookie attack surface.

    A state-changing request is only challenged when it is authenticated via the
    session ``token`` cookie *without* an ``Authorization`` header. Requests that
    carry an ``Authorization`` header (the SPA and all API-key/Bearer clients)
    are inherently safe from CSRF — a cross-site attacker cannot set that header
    — and pass through untouched. This makes the protection a pure addition that
    requires no frontend changes.

    For the cookie attack surface, the request must echo the value of the
    non-HttpOnly ``csrf_token`` cookie in the ``X-CSRF-Token`` header. A
    cross-site attacker can trigger the browser to send the cookie but cannot
    read its value to populate the matching header.
    """

    def __init__(self, app, exempt_prefixes=None, **kwargs):
        super().__init__(app, **kwargs)
        self.exempt_prefixes = tuple(exempt_prefixes or ())

    async def dispatch(self, request: Request, call_next):
        if self._requires_csrf(request):
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            header_token = request.headers.get(CSRF_HEADER_NAME)
            if (
                not cookie_token
                or not header_token
                or not secrets.compare_digest(cookie_token, header_token)
            ):
                log.warning(
                    "CSRF validation failed for %s %s",
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid."},
                )

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)
        return response

    def _requires_csrf(self, request: Request) -> bool:
        if request.method in SAFE_METHODS:
            return False

        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exempt_prefixes):
            return False

        # Bearer / API-key authenticated requests cannot be forged cross-site
        # (an attacker cannot set the Authorization header on the victim's
        # browser), so there is nothing to protect.
        if request.headers.get("authorization"):
            return False

        # Only sessions riding on the auth cookie are exposed to CSRF.
        if not request.cookies.get(AUTH_COOKIE_NAME):
            return False

        return True

    def _ensure_csrf_cookie(self, request: Request, response) -> None:
        if request.cookies.get(CSRF_COOKIE_NAME):
            return
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=secrets.token_urlsafe(32),
            # Must be readable by JS so a cookie-based client can echo it back
            # in the X-CSRF-Token header (double-submit pattern).
            httponly=False,
            samesite=BCGPT_AUTH_COOKIE_SAME_SITE,
            secure=BCGPT_AUTH_COOKIE_SECURE,
            path="/",
        )
