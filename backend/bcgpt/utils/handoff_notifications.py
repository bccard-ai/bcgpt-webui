import logging
import os
import time

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.web.utils import validate_url

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class HandoffNotifier:
    def __init__(self, config):
        self.config = config

    async def notify(self, handoff_request: dict) -> dict:
        results = {}

        if self._config_value(self.config.HANDOFF_EMAIL_ENABLED):
            results["email"] = await self._send_email(handoff_request)

        if self._config_value(self.config.HANDOFF_WEBHOOK_ENABLED):
            results["webhook"] = await self._send_webhook(handoff_request)

        return results

    def _config_value(self, val):
        from bcgpt.config import PersistentConfig

        if isinstance(val, PersistentConfig):
            return val.value
        return val

    async def _send_email(self, handoff_request: dict) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText

            smtp_host = os.environ.get("HANDOFF_SMTP_HOST", "")
            smtp_port = int(os.environ.get("HANDOFF_SMTP_PORT", "587"))
            smtp_user = os.environ.get("HANDOFF_SMTP_USER", "")
            smtp_pass = os.environ.get("HANDOFF_SMTP_PASSWORD", "")
            from_addr = os.environ.get("HANDOFF_EMAIL_FROM", "noreply@bcgpt.local")
            to_addrs = self._config_value(self.config.HANDOFF_EMAIL_RECIPIENTS)

            if not smtp_host or not to_addrs:
                return False

            import json

            if isinstance(to_addrs, str):
                try:
                    to_addrs = json.loads(to_addrs)
                except (json.JSONDecodeError, TypeError):
                    to_addrs = [to_addrs] if to_addrs else []

            subject = f"[BCGPT] \uc0c8\ub85c\uc6b4 \uc0c1\ub2f4\uc6d0 \uc5f0\uacb0 \uc694\uccad (#{handoff_request.get('id', '')[:8]})"
            body = f"""
\uc0c8\ub85c\uc6b4 \uc0c1\ub2f4\uc6d0 \uc5f0\uacb0 \uc694\uccad\uc774 \uc811\uc218\ub418\uc5c8\uc2b5\ub2c8\ub2e4.

\uc694\uccad ID: {handoff_request.get('id')}
\uc0ac\uc6a9\uc790 ID: {handoff_request.get('user_id')}
\ucc44\ud305 ID: {handoff_request.get('chat_id')}
\uc0ac\uc720: {handoff_request.get('reason', 'N/A')}
\uc694\uccad \uc2dc\uac04: {handoff_request.get('created_at')}

\uad00\ub9ac\uc790 \ub300\uc2dc\ubcf4\ub4dc\uc5d0\uc11c \ud655\uc778\ud558\uc138\uc694.
"""

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(
                to_addrs if isinstance(to_addrs, list) else [to_addrs]
            )

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True
        except Exception as e:
            log.error(f"Handoff email notification failed: {e}")
            return False

    async def _send_webhook(self, handoff_request: dict) -> bool:
        try:
            import aiohttp

            webhook_url = self._config_value(self.config.HANDOFF_WEBHOOK_URL)
            if not webhook_url:
                return False

            try:
                validate_url(webhook_url)
            except (ValueError, Exception):
                log.warning(
                    f"Handoff webhook URL blocked (SSRF protection): {webhook_url}"
                )
                return False

            payload = {
                "event": "handoff_request",
                "data": handoff_request,
                "timestamp": int(time.time() * 1000),
            }

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                # SSRF: don't follow redirects to an internal address
                # (validate_url above only checked the initial host).
                async with session.post(
                    webhook_url, json=payload, allow_redirects=False
                ) as response:
                    return response.status < 400
        except Exception as e:
            log.error(f"Handoff webhook notification failed: {e}")
            return False
