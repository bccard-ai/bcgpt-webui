"""YouTube transcript loader.

Fetches video transcripts via the ``youtube_transcript_api`` package.
Supports multiple languages with automatic fallback to English, and
optional proxy configuration.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Union
from urllib.parse import parse_qs, urlparse

from langchain_core.documents import Document

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_NETLOCS = {
    "youtu.be",
    "m.youtube.com",
    "youtube.com",
    "www.youtube.com",
    "www.youtube-nocookie.com",
    "vid.plus",
}


def _parse_video_id(url: str) -> Optional[str]:
    """Extract the 11-character YouTube video ID from *url*, or ``None``."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        return None
    if parsed.netloc not in ALLOWED_NETLOCS:
        return None

    path = parsed.path

    if path.endswith("/watch"):
        qs = parse_qs(parsed.query)
        if "v" not in qs:
            return None
        ids = qs["v"]
        video_id = ids if isinstance(ids, str) else ids[0]
    else:
        video_id = path.lstrip("/").split("/")[-1]

    if len(video_id) != 11:
        return None
    return video_id


class YoutubeLoader:
    """Load a YouTube video transcript as a ``Document``.

    Args:
        video_id: YouTube video ID or full URL.
        language: Preferred transcript language(s).  Falls back to ``"en"``.
        proxy_url: Optional HTTP/HTTPS proxy for the transcript API.
    """

    def __init__(
        self,
        video_id: str,
        language: Union[str, Sequence[str]] = "en",
        proxy_url: Optional[str] = None,
    ) -> None:
        parsed_id = _parse_video_id(video_id)
        self.video_id: str = parsed_id if parsed_id is not None else video_id
        self._metadata: Dict[str, str] = {"source": video_id}
        self.language: List[str] = [language] if isinstance(language, str) else list(language)
        self.proxy_url: Optional[str] = proxy_url

    def load(self) -> List[Document]:
        """Fetch the transcript and return it wrapped in a ``Document``."""
        try:
            from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi
        except ImportError:
            raise ImportError(
                'Could not import "youtube_transcript_api". '
                "Install it with `pip install youtube-transcript-api`."
            )

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}
            log.debug("Using proxy URL: %s...", self.proxy_url[:14])

        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(self.video_id, proxies=proxies)
        except Exception:
            log.exception("Loading YouTube transcript failed")
            return []

        try:
            transcript = transcript_list.find_transcript(self.language)
        except NoTranscriptFound:
            transcript = transcript_list.find_transcript(["en"])

        fetched = transcript.fetch()

        # v1.x returns FetchedTranscript with ``to_raw_data()``.
        pieces = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else fetched
        text = " ".join(piece["text"].strip(" ") for piece in pieces)

        return [Document(page_content=text, metadata=self._metadata)]
