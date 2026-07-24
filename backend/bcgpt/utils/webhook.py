"""Webhook notification dispatcher with SSRF protection.

Delivers event notifications to Slack, Google Chat, Discord, and Microsoft
Teams webhook endpoints.  All URLs are validated against private/reserved
IP ranges before dispatch to prevent server-side request forgery.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from bcgpt.config import BCGPT_FAVICON_URL
from bcgpt.env import SRC_LOG_LEVELS, VERSION

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["WEBHOOK"])


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------


def _is_webhook_url_safe(url: str) -> bool:
    """Check that *url* resolves to a publicly routable address.

    Rejects non-HTTP schemes, unresolvable hostnames, and any IP in a
    private, loopback, link-local, reserved, multicast, or unspecified
    range.

    Args:
        url: Webhook URL to validate.

    Returns:
        ``True`` when the URL is safe to call.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        results = socket.getaddrinfo(parsed.hostname, None)
    except Exception:
        return False
    for result in results:
        ip_str = result[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------


def post_webhook(
    name: str,
    url: str,
    message: str,
    event_data: Dict[str, Any],
) -> bool:
    """Post a notification to the given *url* in the provider-native format.

    Automatically adapts the payload for known providers:

    * **Slack / Google Chat** — ``{"text": message}``
    * **Discord** — ``{"content": message}`` (truncated at 2000 chars)
    * **Microsoft Teams** — Adaptive Card with activity info and facts
    * **Other** — Raw *event_data* forwarded as JSON

    All URLs are validated by :func:`_is_webhook_url_safe` before the
    request is made.

    Args:
        name: Display name of the notification source.
        url: Webhook endpoint URL.
        message: Human-readable notification text.
        event_data: Structured event metadata forwarded to the provider.

    Returns:
        ``True`` on successful delivery, ``False`` on any failure.
    """
    try:
        if not _is_webhook_url_safe(url):
            log.warning("post_webhook: refusing unsafe/non-public URL %s", url)
            return False

        log.debug("post_webhook: %s, %s, %s", url, message, event_data)
        payload: Dict[str, Any] = {}

        # Slack and Google Chat
        if "https://hooks.slack.com" in url or "https://chat.googleapis.com" in url:
            payload["text"] = message

        # Discord
        elif "https://discord.com/api/webhooks" in url:
            payload["content"] = (
                message
                if len(message) < 2000
                else f"{message[:1980]}... (truncated)"
            )

        # Microsoft Teams
        elif "webhook.office.com" in url:
            action = event_data.get("action", "undefined")
            facts = [
                {"name": k, "value": v}
                for k, v in json.loads(event_data.get("user", {})).items()
            ]
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": message,
                "sections": [
                    {
                        "activityTitle": message,
                        "activitySubtitle": f"{name} ({VERSION}) - {action}",
                        "activityImage": BCGPT_FAVICON_URL,
                        "facts": facts,
                        "markdown": True,
                    }
                ],
            }

        # Default: forward raw event data
        else:
            payload = {**event_data}

        log.debug("payload: %s", payload)
        resp = requests.post(url, json=payload, timeout=10, allow_redirects=False)
        resp.raise_for_status()
        log.debug("response: %s", resp.text)
        return True

    except Exception as exc:
        log.exception("Webhook delivery failed: %s", exc)
        return False
