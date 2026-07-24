"""PDF generation from chat message histories.

Transforms chat messages into styled PDF documents using fpdf2 with
multi-script font support (Latin, Korean, Japanese, Chinese, emoji).

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import site
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from fpdf import FPDF

from bcgpt.env import FONTS_DIR, STATIC_DIR
from bcgpt.models import ChatTitleMessagesForm


class PDFGenerator:
    """Create PDF documents from chat message histories.

    The generation pipeline:
    1. Each message is converted to styled HTML.
    2. Messages are assembled into a full HTML body.
    3. fpdf2 renders the HTML to a PDF byte buffer.

    Attributes:
        form_data: :class:`ChatTitleMessagesForm` containing title and messages.
        css: Stylesheet loaded from ``static/assets/pdf-style.css``.
    """

    def __init__(self, form_data: ChatTitleMessagesForm) -> None:
        self.html_body: str | None = None
        self.messages_html: str | None = None
        self.form_data = form_data
        self.css = Path(STATIC_DIR / "assets" / "pdf-style.css").read_text()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_timestamp(timestamp: float) -> str:
        """Convert a UNIX timestamp to a human-readable date string.

        Args:
            timestamp: Seconds since the epoch.

        Returns:
            Formatted string like ``"2026-06-09, 14:30:00"``, or an empty
            string on error.
        """
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d, %H:%M:%S")
        except (ValueError, TypeError):
            return ""

    def _build_html_message(self, message: Dict[str, Any]) -> str:
        """Build an HTML fragment for a single chat message.

        Args:
            message: Dict with ``role``, ``content``, optional ``timestamp``
                and ``model`` keys.

        Returns:
            HTML string for the message card.
        """
        role = escape(message.get("role", "user"))
        content = escape(message.get("content", ""))
        timestamp = message.get("timestamp")
        model = escape(message.get("model") if role == "assistant" else "")
        date_str = escape(self.format_timestamp(timestamp) if timestamp else "")

        # Newlines to line breaks
        content = content.replace("\n", "<br/>")

        return f"""
            <div>
                <div>
                    <h4>
                        <strong>{role.title()}</strong>
                        <span style="font-size: 12px;">{model}</span>
                    </h4>
                    <div> {date_str} </div>
                </div>
                <br/>
                <br/>
                <div> {content} </div>
            </div>
            <br/>
        """

    def _generate_html_body(self) -> str:
        """Assemble the full HTML document from the title and message fragments.

        Returns:
            Complete HTML string ready for PDF rendering.
        """
        escaped_title = escape(self.form_data.title)
        return f"""
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            </head>
            <body>
            <div>
                <div>
                    <h2>{escaped_title}</h2>
                    {self.messages_html}
                </div>
            </div>
            </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_chat_pdf(self) -> bytes:
        """Generate a PDF document from the stored chat messages.

        Resolves font directories for different installation layouts
        (source tree, ``pip install``, ``pip install -e .``) and registers
        multi-script fonts before rendering.

        Returns:
            Raw PDF bytes.

        Raises:
            Exception: Propagated from fpdf2 on rendering failure.
        """
        global FONTS_DIR

        try:
            pdf = FPDF()
            pdf.add_page()

            # Resolve font directory for different install modes
            if not FONTS_DIR.exists():
                FONTS_DIR = Path(site.getsitepackages()[0]) / "static/fonts"
            if not FONTS_DIR.exists():
                FONTS_DIR = Path(".") / "backend" / "static" / "fonts"

            # Register multi-script fonts
            pdf.add_font("NotoSans", "", f"{FONTS_DIR}/NotoSans-Regular.ttf")
            pdf.add_font("NotoSans", "b", f"{FONTS_DIR}/NotoSans-Bold.ttf")
            pdf.add_font("NotoSans", "i", f"{FONTS_DIR}/NotoSans-Italic.ttf")
            pdf.add_font("NotoSansKR", "", f"{FONTS_DIR}/NotoSansKR-Regular.ttf")
            pdf.add_font("NotoSansJP", "", f"{FONTS_DIR}/NotoSansJP-Regular.ttf")
            pdf.add_font("NotoSansSC", "", f"{FONTS_DIR}/NotoSansSC-Regular.ttf")
            pdf.add_font("Twemoji", "", f"{FONTS_DIR}/Twemoji.ttf")

            pdf.set_font("NotoSans", size=12)
            pdf.set_fallback_fonts(
                ["NotoSansKR", "NotoSansJP", "NotoSansSC", "Twemoji"]
            )
            pdf.set_auto_page_break(auto=True, margin=15)

            # Build HTML
            messages_html_list: List[str] = [
                self._build_html_message(msg) for msg in self.form_data.messages
            ]
            self.messages_html = "<div>" + "".join(messages_html_list) + "</div>"
            self.html_body = self._generate_html_body()

            pdf.write_html(self.html_body)
            return bytes(pdf.output())

        except Exception as exc:
            raise exc
