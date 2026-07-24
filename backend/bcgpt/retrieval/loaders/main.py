"""Document loader subsystem.

Dispatches file content extraction to the appropriate backend based on
file extension, content type, and the configured loading engine (Tika,
Docling, or Azure Document Intelligence).  Falls back to direct
text extraction via LangChain community loaders.

Includes XXE hardening for stdlib XML parsers via ``defusedxml``.
"""

from __future__ import annotations

import logging
import sys

import ftfy
import requests

# XXE hardening: neutralize external-entity / billion-laughs attacks in
# Python's stdlib XML parsers used by some document loaders.  Best-effort —
# lxml-based loaders are not covered and rely on their upstream defaults.
try:
    from defusedxml import defuse_stdlib

    defuse_stdlib()
except Exception:  # pragma: no cover – defusedxml optional / already defused
    pass

from langchain_community.document_loaders import (
    AzureAIDocumentIntelligenceLoader,
    BSHTMLLoader,
    CSVLoader,
    Docx2txtLoader,
    OutlookMessageLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredEPubLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPowerPointLoader,
    UnstructuredRSTLoader,
    UnstructuredXMLLoader,
    YoutubeLoader,
)
from langchain_core.documents import Document

from bcgpt.env import GLOBAL_LOG_LEVEL, SRC_LOG_LEVELS

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

# ---------------------------------------------------------------------------
# Known source-code extensions — treated as plain text.
# ---------------------------------------------------------------------------

known_source_ext: list[str] = [
    "go",
    "py",
    "java",
    "sh",
    "bat",
    "ps1",
    "cmd",
    "js",
    "ts",
    "css",
    "cpp",
    "hpp",
    "h",
    "c",
    "cs",
    "sql",
    "log",
    "ini",
    "pl",
    "pm",
    "r",
    "dart",
    "dockerfile",
    "env",
    "php",
    "hs",
    "hsc",
    "lua",
    "nginxconf",
    "conf",
    "m",
    "mm",
    "plsql",
    "perl",
    "rb",
    "rs",
    "db2",
    "scala",
    "bash",
    "swift",
    "vue",
    "svelte",
    "msg",
    "ex",
    "exs",
    "erl",
    "tsx",
    "jsx",
    "lhs",
    "json",
]


# ---------------------------------------------------------------------------
# External service loaders
# ---------------------------------------------------------------------------


class TikaLoader:
    """Extract text from files via an Apache Tika server."""

    def __init__(self, url: str, file_path: str, mime_type: str | None = None) -> None:
        self.url = url
        self.file_path = file_path
        self.mime_type = mime_type

    def load(self) -> list[Document]:
        """Send the file to Tika and return extracted text as a ``Document``."""
        with open(self.file_path, "rb") as f:
            data = f.read()

        headers: dict[str, str] = {}
        if self.mime_type is not None:
            headers["Content-Type"] = self.mime_type

        endpoint = self.url.rstrip("/") + "/tika/text"
        r = requests.put(endpoint, data=data, headers=headers)

        if r.ok:
            raw_metadata = r.json()
            text = raw_metadata.get("X-TIKA:content", "<No text content found>").strip()
            if "Content-Type" in raw_metadata:
                headers["Content-Type"] = raw_metadata["Content-Type"]
            log.debug("Tika extracted text: %s", text)
            return [Document(page_content=text, metadata=headers)]

        raise Exception(f"Error calling Tika: {r.reason}")


class DoclingLoader:
    """Extract text from files via a Docling conversion server."""

    def __init__(
        self, url: str, file_path: str | None = None, mime_type: str | None = None
    ) -> None:
        self.url = url.rstrip("/")
        self.file_path = file_path
        self.mime_type = mime_type

    def load(self) -> list[Document]:
        """Post the file to Docling and return the Markdown content."""
        with open(self.file_path, "rb") as f:
            files = {
                "files": (
                    self.file_path,
                    f,
                    self.mime_type or "application/octet-stream",
                )
            }
            params = {"image_export_mode": "placeholder", "table_mode": "accurate"}
            r = requests.post(
                f"{self.url}/v1alpha/convert/file", files=files, data=params
            )

        if r.ok:
            result = r.json()
            text = result.get("document", {}).get(
                "md_content", "<No text content found>"
            )
            metadata = {"Content-Type": self.mime_type} if self.mime_type else {}
            log.debug("Docling extracted text: %s", text)
            return [Document(page_content=text, metadata=metadata)]

        error_msg = f"Error calling Docling API: {r.reason}"
        if r.text:
            try:
                error_data = r.json()
                if "detail" in error_data:
                    error_msg += f" - {error_data['detail']}"
            except Exception:
                error_msg += f" - {r.text}"
        raise Exception(error_msg)


# ---------------------------------------------------------------------------
# Main dispatch loader
# ---------------------------------------------------------------------------


class Loader:
    """Route file loading to the appropriate engine based on configuration and file type."""

    def __init__(self, engine: str = "", **kwargs) -> None:
        self.engine = engine
        self.kwargs = kwargs

    def load(
        self, filename: str, file_content_type: str, file_path: str
    ) -> list[Document]:
        """Load *filename* from *file_path* and return ``Document`` objects with fixed Unicode."""
        loader = self._get_loader(filename, file_content_type, file_path)
        docs = loader.load()
        docs = [
            Document(
                page_content=ftfy.fix_text(doc.page_content), metadata=doc.metadata
            )
            for doc in docs
        ]

        # Column-type profiling for tabular files (2.6): attach a compact
        # {column: type} map to each chunk's metadata so the LLM gets structured
        # column context (currency/percent/date/...) before reasoning.
        if self.kwargs.get("RAG_COLUMN_PROFILER_ENABLED") and filename.lower().endswith(
            (".csv", ".tsv")
        ):
            try:
                profile = self._profile_tabular(file_path, filename)
                if profile:
                    import json as _json

                    summary = _json.dumps(profile, ensure_ascii=False)
                    for d in docs:
                        d.metadata["column_profile"] = summary
            except Exception as e:  # pragma: no cover - best effort
                log.debug("Column profiling skipped for %s: %s", filename, e)

        return docs

    @staticmethod
    def _profile_tabular(file_path: str, filename: str, max_rows: int = 200) -> dict:
        """Profile column types of a CSV/TSV file → ``{column: type}``."""
        import csv as _csv

        from bcgpt.retrieval.column_profiler import profile_table

        delimiter = "\t" if filename.lower().endswith(".tsv") else ","
        headers = None
        rows: list = []
        with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = _csv.reader(f, delimiter=delimiter)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = row
                    continue
                rows.append(row)
                if i >= max_rows:
                    break
        if not rows:
            return {}
        result = profile_table(rows, headers=headers)
        return {k: v["type"] for k, v in result.get("columns", {}).items()}

    def _get_loader(self, filename: str, file_content_type: str, file_path: str):
        """Select the concrete loader instance for the given file."""
        file_ext = filename.split(".")[-1].lower()

        # ---- Engine-specific dispatch --------------------------------
        if self.engine == "tika" and self.kwargs.get("TIKA_SERVER_URL"):
            if file_ext in known_source_ext or (
                file_content_type and "text/" in file_content_type
            ):
                return TextLoader(file_path, autodetect_encoding=True)
            return TikaLoader(
                url=self.kwargs.get("TIKA_SERVER_URL"),
                file_path=file_path,
                mime_type=file_content_type,
            )

        if self.engine == "docling" and self.kwargs.get("DOCLING_SERVER_URL"):
            return DoclingLoader(
                url=self.kwargs.get("DOCLING_SERVER_URL"),
                file_path=file_path,
                mime_type=file_content_type,
            )

        if (
            self.engine == "document_intelligence"
            and self.kwargs.get("DOCUMENT_INTELLIGENCE_ENDPOINT")
            and self.kwargs.get("DOCUMENT_INTELLIGENCE_KEY")
            and (
                file_ext in ["pdf", "xls", "xlsx", "docx", "ppt", "pptx"]
                or file_content_type
                in [
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.ms-powerpoint",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ]
            )
        ):
            return AzureAIDocumentIntelligenceLoader(
                file_path=file_path,
                api_endpoint=self.kwargs.get("DOCUMENT_INTELLIGENCE_ENDPOINT"),
                api_key=self.kwargs.get("DOCUMENT_INTELLIGENCE_KEY"),
            )

        # ---- Extension-based fallback --------------------------------
        if file_ext == "pdf":
            return PyPDFLoader(
                file_path, extract_images=self.kwargs.get("PDF_EXTRACT_IMAGES")
            )
        if file_ext == "csv":
            return CSVLoader(file_path, autodetect_encoding=True)
        if file_ext == "rst":
            return UnstructuredRSTLoader(file_path, mode="elements")
        if file_ext == "xml":
            return UnstructuredXMLLoader(file_path)
        if file_ext in ("htm", "html"):
            # "utf-8" -- "unicode_escape" was a bug: it decodes Python source
            # escapes (\uXXXX / \n / \U), which corrupts non-ASCII (e.g. Korean
            # UTF-8 -> mojibake) and raises UnicodeDecodeError on any literal
            # "\U" (e.g. a pasted Windows path "C:\Users\..."), crashing HTML
            # ingestion. UTF-8 is the standard HTML encoding.
            return BSHTMLLoader(file_path, open_encoding="utf-8")
        if file_ext == "md":
            return TextLoader(file_path, autodetect_encoding=True)
        if file_content_type == "application/epub+zip":
            return UnstructuredEPubLoader(file_path)
        if (
            file_content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or file_ext == "docx"
        ):
            return Docx2txtLoader(file_path)
        if file_content_type in (
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ) or file_ext in ("xls", "xlsx"):
            return UnstructuredExcelLoader(file_path)
        if file_content_type in (
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ) or file_ext in ("ppt", "pptx"):
            return UnstructuredPowerPointLoader(file_path)
        if file_ext == "msg":
            return OutlookMessageLoader(file_path)

        # Default: treat as plain text
        return TextLoader(file_path, autodetect_encoding=True)
