import hashlib
import logging
from datetime import datetime, timezone

import aiohttp

from bcgpt.utils.http_client import get_client_session

log = logging.getLogger(__name__)


async def send_siem_event(
    event_data: dict,
    webhook_url: str,
    headers: dict | None = None,
) -> bool:
    try:
        final_headers = {
            "Content-Type": "application/json",
            **(headers or {}),
        }

        session = await get_client_session()
        async with session.post(
            webhook_url,
            json=event_data,
            headers=final_headers,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response:
            log.info(
                "SIEM event sent: status=%d url=%s",
                response.status,
                webhook_url,
            )
            return response.status < 400

    except Exception as exc:
        log.warning("SIEM webhook failed (silently ignored): %s", exc)
        return False


def format_security_event_for_siem(
    scan_result,
    user: dict | None,
    text_hash: str,
    metadata: dict | None = None,
) -> dict:
    threat_types = [t.threat_type.value for t in scan_result.threats]
    severities = [t.severity.value for t in scan_result.threats]

    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    max_severity = (
        max(severities, key=lambda s: severity_order.get(s, 0))
        if severities
        else "info"
    )

    descriptions = "; ".join(
        t.description for t in scan_result.threats if t.description
    )

    now = datetime.now(timezone.utc).isoformat()

    event = {
        "version": "CEF:0",
        "deviceVendor": "BCGPT",
        "deviceProduct": "SecurityScanner",
        "deviceVersion": "1.0",
        "signatureId": scan_result.scanner_name or "unknown",
        "name": f"SecurityScan: {', '.join(threat_types) if threat_types else 'clean'}",
        "severity": max_severity,
        "extension": {
            "rt": now,
            "src": user.get("id", "unknown") if user else "system",
            "msg": descriptions or "No threats detected",
            "cn1": len(scan_result.threats),
            "cn1Label": "ThreatCount",
            "cs1": ",".join(threat_types) if threat_types else "none",
            "cs1Label": "ThreatTypes",
            "cs2": text_hash,
            "cs2Label": "TextHash",
            "is_safe": scan_result.is_safe,
        },
    }

    if metadata:
        event["extension"]["meta"] = metadata

    return event
