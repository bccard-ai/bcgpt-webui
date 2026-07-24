"""Web retrieval utilities with SSRF protection, rate limiting, and safe loaders.

Provides URL validation, SSL verification, metadata extraction, and several
safe document loader classes that wrap upstream LangChain loaders with
defence-in-depth security checks.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import ssl
import time as _time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
)

import aiohttp
import certifi
import validators
from langchain_community.document_loaders import PlaywrightURLLoader, WebBaseLoader
from langchain_community.document_loaders.base import BaseLoader
from langchain_community.document_loaders.firecrawl import FireCrawlLoader
from langchain_core.documents import Document

from bcgpt.config import (
    ENABLE_RAG_LOCAL_WEB_FETCH,
    FIRECRAWL_API_BASE_URL,
    FIRECRAWL_API_KEY,
    PLAYWRIGHT_TIMEOUT,
    PLAYWRIGHT_WS_URI,
    RAG_WEB_LOADER_ENGINE,
    TAVILY_API_KEY,
    TAVILY_EXTRACT_DEPTH,
)
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import TavilyLoader
from bcgpt.utils.http_client import get_client_session

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_INVALID_URL_MSG = ERROR_MESSAGES.INVALID_URL


def _resolve_proxy_from_env(
    proxy: Optional[Dict[str, str]],
    *,
    trust_env: bool,
) -> Optional[Dict[str, str]]:
    """Populate *proxy* with the system HTTPS/HTTP proxy when *trust_env* is set.

    Returns the (possibly updated) proxy dict, or ``None`` when neither the
    supplied proxy nor the environment provides a server address.
    """
    if proxy and proxy.get("server"):
        return proxy
    if not trust_env:
        return proxy

    env_proxies = urllib.request.getproxies()
    env_server = env_proxies.get("https") or env_proxies.get("http")
    if not env_server:
        return proxy

    if proxy is None:
        return {"server": env_server}
    proxy["server"] = env_server
    return proxy


def _check_ips_against_blocklist(
    hostname: str,
    *,
    allow_private: bool,
) -> None:
    """Resolve *hostname* and raise ``ValueError`` if any IP is blocked.

    This is the core SSRF guard – every hostname that will be fetched must
    pass through here.
    """
    try:
        ipv4, ipv6 = resolve_hostname(hostname)
    except Exception:
        raise ValueError(_INVALID_URL_MSG)

    for ip_str in ipv4 + ipv6:
        if _is_blocked_ip(ip_str, allow_private=allow_private):
            raise ValueError(_INVALID_URL_MSG)


# ---------------------------------------------------------------------------
# Public helpers – URL validation & metadata
# ---------------------------------------------------------------------------


def _is_blocked_ip(ip_str: str, allow_private: bool = False) -> bool:
    """Return ``True`` when *ip_str* must never be fetched (SSRF protection).

    Loopback, link-local, multicast, unspecified and reserved ranges are
    always blocked regardless of *allow_private*.  When *allow_private* is
    ``False`` (the default), RFC-1918 and unique-local addresses are also
    rejected.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        return True

    # Cloud-metadata endpoints (169.254.169.254 / fd00:ec2::254) are
    # link-local and already caught by the check above.
    if not allow_private and ip.is_private:
        return True

    return False


def validate_url(url: Union[str, Sequence[str]]) -> Union[bool, Literal[False]]:
    """Validate one URL or a sequence of URLs for safe fetching.

    Checks scheme (http/https), uses the *validators* library, resolves the
    hostname and rejects blocked IP addresses.  When *ENABLE_RAG_LOCAL_WEB_FETCH*
    is enabled private IPs are allowed.

    Returns:
        ``True`` for a valid single URL, the result of ``all()`` for a
        sequence, or ``False`` for an unsupported type.
    """
    if isinstance(url, str):
        if isinstance(validators.url(url), validators.ValidationError):
            raise ValueError(_INVALID_URL_MSG)

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(_INVALID_URL_MSG)

        allow_private = bool(ENABLE_RAG_LOCAL_WEB_FETCH)
        _check_ips_against_blocklist(parsed.hostname, allow_private=allow_private)
        return True

    if isinstance(url, Sequence):
        return all(validate_url(u) for u in url)

    return False


async def validate_url_with_redirect_check(url: str) -> bool:
    """Validate a URL *and* verify its final redirect destination is safe.

    Performs the standard :func:`validate_url` checks first, then issues a
    HEAD request to follow redirects.  The final resolved hostname is
    re-checked against :func:`_is_blocked_ip` so that open-redirect SSRF
    attacks are caught.

    Raises:
        ValueError: If the URL or its redirect destination is invalid/blocked.
    """
    validate_url(url)

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.head(url, allow_redirects=True) as resp:
                final_url = str(resp.url)
    except Exception as exc:
        # Fail CLOSED – reject if the redirect target cannot be verified.
        log.warning("Redirect check failed for %s: %s", url, exc)
        raise ValueError(_INVALID_URL_MSG)

    parsed = urllib.parse.urlparse(final_url)
    if not parsed.hostname:
        raise ValueError(_INVALID_URL_MSG)

    allow_private = bool(ENABLE_RAG_LOCAL_WEB_FETCH)
    _check_ips_against_blocklist(parsed.hostname, allow_private=allow_private)
    return True


def safe_validate_urls(urls: Sequence[str]) -> Sequence[str]:
    """Return only the URLs from *urls* that pass :func:`validate_url`.

    Invalid URLs are silently skipped rather than raising.
    """
    valid: List[str] = []
    for u in urls:
        try:
            if validate_url(u):
                valid.append(u)
        except ValueError:
            continue
    return valid


def resolve_hostname(hostname: str) -> tuple[list[str], list[str]]:
    """Resolve *hostname* and return ``(ipv4_addresses, ipv6_addresses)``."""
    addr_info = socket.getaddrinfo(hostname, None)
    ipv4 = [info[4][0] for info in addr_info if info[0] == socket.AF_INET]
    ipv6 = [info[4][0] for info in addr_info if info[0] == socket.AF_INET6]
    return ipv4, ipv6


def extract_metadata(soup: Any, url: str) -> Dict[str, str]:
    """Extract common HTML metadata from a BeautifulSoup *soup* object.

    Returns a dict containing at minimum ``"source": url`` and optionally
    ``title``, ``description`` and ``language`` keys.
    """
    metadata: Dict[str, str] = {"source": url}

    if title_tag := soup.find("title"):
        metadata["title"] = title_tag.get_text()

    if description_tag := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description_tag.get("content", "No description found.")

    if html_tag := soup.find("html"):
        metadata["language"] = html_tag.get("lang", "No language found.")

    return metadata


def verify_ssl_cert(url: str) -> bool:
    """Verify the SSL certificate presented by the host in *url*.

    Returns ``True`` when the certificate is valid or the URL is not HTTPS.
    Returns ``False`` on verification failure.
    """
    if not url.startswith("https://"):
        return True

    try:
        hostname = url.split("://")[-1].split("/")[0]
        ctx = ssl.create_default_context(cafile=certifi.where())
        with ctx.wrap_socket(ssl.socket(), server_hostname=hostname) as sock:
            sock.connect((hostname, 443))
        return True
    except ssl.SSLError:
        return False
    except Exception as exc:
        log.warning("SSL verification failed for %s: %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# Mixins – rate limiting & URL safety
# ---------------------------------------------------------------------------


class RateLimitMixin:
    """Mixin that adds configurable per-second rate limiting."""

    requests_per_second: Optional[float]
    last_request_time: Optional[datetime]

    async def _wait_for_rate_limit(self) -> None:
        """Sleep until the rate-limit interval has elapsed (async)."""
        if self.requests_per_second and self.last_request_time:
            min_interval = timedelta(seconds=1.0 / self.requests_per_second)
            elapsed = datetime.now() - self.last_request_time
            if elapsed < min_interval:
                await asyncio.sleep((min_interval - elapsed).total_seconds())
        self.last_request_time = datetime.now()

    def _sync_wait_for_rate_limit(self) -> None:
        """Sleep until the rate-limit interval has elapsed (sync)."""
        if self.requests_per_second and self.last_request_time:
            min_interval = timedelta(seconds=1.0 / self.requests_per_second)
            elapsed = datetime.now() - self.last_request_time
            if elapsed < min_interval:
                _time.sleep((min_interval - elapsed).total_seconds())
        self.last_request_time = datetime.now()


class URLProcessingMixin:
    """Mixin that adds SSL verification before URL processing."""

    verify_ssl: bool

    def _verify_ssl_cert(self, url: str) -> bool:
        """Delegate to the module-level :func:`verify_ssl_cert`."""
        return verify_ssl_cert(url)

    async def _safe_process_url(self, url: str) -> bool:
        """Run SSL check and wait for rate limit (async)."""
        if self.verify_ssl and not self._verify_ssl_cert(url):
            raise ValueError("SSL certificate verification failed for %s" % url)
        await self._wait_for_rate_limit()
        return True

    def _safe_process_url_sync(self, url: str) -> bool:
        """Run SSL check and wait for rate limit (sync)."""
        if self.verify_ssl and not self._verify_ssl_cert(url):
            raise ValueError("SSL certificate verification failed for %s" % url)
        self._sync_wait_for_rate_limit()
        return True


# ---------------------------------------------------------------------------
# Safe loader helpers
# ---------------------------------------------------------------------------


def _loader_should_continue(exc: BaseException, url: str, *, continue_on_failure: bool) -> bool:
    """Log *exc* and decide whether to continue or re-raise.

    Returns ``True`` when the caller should ``continue`` to the next URL.
    """
    if continue_on_failure:
        log.exception("Error loading %s: %s", url, exc)
        return True
    return False


def _collect_valid_urls_sync(
    web_paths: Sequence[str],
    *,
    continue_on_failure: bool,
    safe_check: Any,  # bound method _safe_process_url_sync
) -> List[str]:
    """Pre-validate URLs synchronously, collecting those that pass safety checks."""
    valid: List[str] = []
    for url in web_paths:
        try:
            safe_check(url)
            valid.append(url)
        except Exception as exc:
            log.warning("SSL verification failed for %s: %s", url, exc)
            if not continue_on_failure:
                raise
    return valid


async def _collect_valid_urls_async(
    web_paths: Sequence[str],
    *,
    continue_on_failure: bool,
    safe_check: Any,  # bound method _safe_process_url
) -> List[str]:
    """Pre-validate URLs asynchronously, collecting those that pass safety checks."""
    valid: List[str] = []
    for url in web_paths:
        try:
            await safe_check(url)
            valid.append(url)
        except Exception as exc:
            log.warning("SSL verification failed for %s: %s", url, exc)
            if not continue_on_failure:
                raise
    return valid


def _no_valid_urls(continue_on_failure: bool) -> None:
    """Handle the "no valid URLs after verification" edge case."""
    if continue_on_failure:
        log.warning("No valid URLs to process after SSL verification")
        return
    raise ValueError("No valid URLs to process after SSL verification")


# ---------------------------------------------------------------------------
# SafeFireCrawlLoader
# ---------------------------------------------------------------------------


class SafeFireCrawlLoader(BaseLoader, RateLimitMixin, URLProcessingMixin):
    """FireCrawl loader with rate limiting, SSL verification and proxy support."""

    def __init__(
        self,
        web_paths: Sequence[str],
        verify_ssl: bool = True,
        trust_env: bool = False,
        requests_per_second: Optional[float] = None,
        continue_on_failure: bool = True,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        mode: Literal["crawl", "scrape", "map"] = "crawl",
        proxy: Optional[Dict[str, str]] = None,
        params: Optional[Dict] = None,
    ) -> None:
        proxy = _resolve_proxy_from_env(proxy, trust_env=trust_env)

        self.web_paths = web_paths
        self.verify_ssl = verify_ssl
        self.requests_per_second = requests_per_second
        self.last_request_time = None
        self.trust_env = trust_env
        self.continue_on_failure = continue_on_failure
        self.api_key = api_key
        self.api_url = api_url
        self.mode = mode
        self.params = params

    def lazy_load(self) -> Iterator[Document]:
        """Load documents synchronously via FireCrawl with safety checks."""
        for url in self.web_paths:
            try:
                self._safe_process_url_sync(url)
                loader = FireCrawlLoader(
                    url=url,
                    api_key=self.api_key,
                    api_url=self.api_url,
                    mode=self.mode,
                    params=self.params,
                )
                yield from loader.lazy_load()
            except Exception as exc:
                if not _loader_should_continue(exc, url, continue_on_failure=self.continue_on_failure):
                    raise

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Load documents asynchronously via FireCrawl with safety checks."""
        for url in self.web_paths:
            try:
                await self._safe_process_url(url)
                loader = FireCrawlLoader(
                    url=url,
                    api_key=self.api_key,
                    api_url=self.api_url,
                    mode=self.mode,
                    params=self.params,
                )
                async for doc in loader.alazy_load():
                    yield doc
            except Exception as exc:
                if not _loader_should_continue(exc, url, continue_on_failure=self.continue_on_failure):
                    raise


# ---------------------------------------------------------------------------
# SafeTavilyLoader
# ---------------------------------------------------------------------------


class SafeTavilyLoader(BaseLoader, RateLimitMixin, URLProcessingMixin):
    """Tavily loader with rate limiting, SSL verification and proxy support."""

    def __init__(
        self,
        web_paths: Union[str, List[str]],
        api_key: str,
        extract_depth: Literal["basic", "advanced"] = "basic",
        continue_on_failure: bool = True,
        requests_per_second: Optional[float] = None,
        verify_ssl: bool = True,
        trust_env: bool = False,
        proxy: Optional[Dict[str, str]] = None,
    ) -> None:
        self.web_paths = web_paths if isinstance(web_paths, list) else [web_paths]
        self.api_key = api_key
        self.extract_depth = extract_depth
        self.continue_on_failure = continue_on_failure
        self.verify_ssl = verify_ssl
        self.trust_env = trust_env
        self.proxy = _resolve_proxy_from_env(proxy, trust_env=trust_env)
        self.requests_per_second = requests_per_second
        self.last_request_time = None

    def lazy_load(self) -> Iterator[Document]:
        """Load documents synchronously via Tavily with safety checks."""
        valid_urls = _collect_valid_urls_sync(
            self.web_paths,
            continue_on_failure=self.continue_on_failure,
            safe_check=self._safe_process_url_sync,
        )
        if not valid_urls:
            _no_valid_urls(self.continue_on_failure)
            return

        try:
            loader = TavilyLoader(
                urls=valid_urls,
                api_key=self.api_key,
                extract_depth=self.extract_depth,
                continue_on_failure=self.continue_on_failure,
            )
            yield from loader.lazy_load()
        except Exception as exc:
            if self.continue_on_failure:
                log.exception("Error extracting content from URLs: %s", exc)
            else:
                raise

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Load documents asynchronously via Tavily with safety checks."""
        valid_urls = await _collect_valid_urls_async(
            self.web_paths,
            continue_on_failure=self.continue_on_failure,
            safe_check=self._safe_process_url,
        )
        if not valid_urls:
            _no_valid_urls(self.continue_on_failure)
            return

        try:
            loader = TavilyLoader(
                urls=valid_urls,
                api_key=self.api_key,
                extract_depth=self.extract_depth,
                continue_on_failure=self.continue_on_failure,
            )
            async for doc in loader.alazy_load():
                yield doc
        except Exception as exc:
            if self.continue_on_failure:
                log.exception("Error loading URLs: %s", exc)
            else:
                raise


# ---------------------------------------------------------------------------
# SafePlaywrightURLLoader
# ---------------------------------------------------------------------------


class SafePlaywrightURLLoader(PlaywrightURLLoader, RateLimitMixin, URLProcessingMixin):
    """Playwright loader with SSL verification, rate limiting and remote browser support.

    Attributes:
        verify_ssl: Verify SSL certificates before fetching.
        requests_per_second: Optional rate-limit for requests.
        playwright_ws_url: WebSocket endpoint for a remote Chromium instance.
        playwright_timeout: Maximum page-load time in milliseconds.
    """

    def __init__(
        self,
        web_paths: List[str],
        verify_ssl: bool = True,
        trust_env: bool = False,
        requests_per_second: Optional[float] = None,
        continue_on_failure: bool = True,
        headless: bool = True,
        remove_selectors: Optional[List[str]] = None,
        proxy: Optional[Dict[str, str]] = None,
        playwright_ws_url: Optional[str] = None,
        playwright_timeout: Optional[int] = 10000,
    ) -> None:
        proxy = _resolve_proxy_from_env(proxy, trust_env=trust_env)

        super().__init__(
            urls=web_paths,
            continue_on_failure=continue_on_failure,
            headless=headless if playwright_ws_url is None else False,
            remove_selectors=remove_selectors,
            proxy=proxy,
        )
        self.verify_ssl = verify_ssl
        self.requests_per_second = requests_per_second
        self.last_request_time = None
        self.playwright_ws_url = playwright_ws_url
        self.trust_env = trust_env
        self.playwright_timeout = playwright_timeout

    def lazy_load(self) -> Iterator[Document]:
        """Load pages synchronously with Playwright (local or remote browser)."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            if self.playwright_ws_url:
                browser = p.chromium.connect(self.playwright_ws_url)
            else:
                browser = p.chromium.launch(headless=self.headless, proxy=self.proxy)

            for url in self.urls:
                try:
                    self._safe_process_url_sync(url)
                    page = browser.new_page()
                    response = page.goto(url, timeout=self.playwright_timeout)
                    if response is None:
                        raise ValueError("page.goto() returned None for url %s" % url)
                    text = self.evaluator.evaluate(page, browser, response)
                    yield Document(page_content=text, metadata={"source": url})
                except Exception as exc:
                    if not _loader_should_continue(exc, url, continue_on_failure=self.continue_on_failure):
                        raise
            browser.close()

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Load pages asynchronously with Playwright (local or remote browser)."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            if self.playwright_ws_url:
                browser = await p.chromium.connect(self.playwright_ws_url)
            else:
                browser = await p.chromium.launch(headless=self.headless, proxy=self.proxy)

            for url in self.urls:
                try:
                    await self._safe_process_url(url)
                    page = await browser.new_page()
                    response = await page.goto(url, timeout=self.playwright_timeout)
                    if response is None:
                        raise ValueError("page.goto() returned None for url %s" % url)
                    text = await self.evaluator.evaluate_async(page, browser, response)
                    yield Document(page_content=text, metadata={"source": url})
                except Exception as exc:
                    if not _loader_should_continue(exc, url, continue_on_failure=self.continue_on_failure):
                        raise
            await browser.close()


# ---------------------------------------------------------------------------
# SafeWebBaseLoader
# ---------------------------------------------------------------------------

_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class SafeWebBaseLoader(WebBaseLoader):
    """WebBaseLoader with SSRF-safe redirect handling and retry logic.

    Redirects are followed *manually* so each hop is validated against the
    IP blocklist, preventing open-redirect SSRF attacks.
    """

    def __init__(self, trust_env: bool = False, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.trust_env = trust_env

    async def _fetch(
        self,
        url: str,
        retries: int = 3,
        cooldown: int = 2,
        backoff: float = 1.5,
        max_redirects: int = 5,
    ) -> str:
        """Fetch a single URL with retries and SSRF-safe redirect following.

        Redirects are **not** followed automatically; each 3xx hop is
        validated via :func:`validate_url` before the next request is made.
        """
        session = await get_client_session(trust_env=self.trust_env)

        for attempt in range(retries):
            try:
                headers = dict(self.session.headers)
                cookies = self.session.cookies.get_dict()
                if cookies:
                    headers["Cookie"] = "; ".join(
                        "%s=%s" % (k, v) for k, v in cookies.items()
                    )

                fetch_kwargs: Dict[str, Any] = dict(headers=headers)
                if not self.session.verify:
                    fetch_kwargs["ssl"] = False

                # Do NOT auto-follow redirects – validate each hop.
                fetch_kwargs["allow_redirects"] = False

                current_url = url
                for _hop in range(max_redirects + 1):
                    async with session.get(
                        current_url, **(self.requests_kwargs | fetch_kwargs)
                    ) as resp:
                        if (
                            resp.status in _REDIRECT_STATUSES
                            and "location" in resp.headers
                        ):
                            next_url = urllib.parse.urljoin(
                                current_url, resp.headers["location"]
                            )
                            await asyncio.to_thread(validate_url, next_url)
                            current_url = next_url
                            continue

                        if self.raise_for_status:
                            resp.raise_for_status()
                        return await resp.text()

                raise ValueError("Too many redirects while fetching %s" % url)

            except aiohttp.ClientConnectionError as exc:
                if attempt == retries - 1:
                    raise
                log.warning(
                    "Error fetching %s (attempt %d/%d): %s. Retrying...",
                    url,
                    attempt + 1,
                    retries,
                    exc,
                )
                await asyncio.sleep(cooldown * backoff ** attempt)

        raise ValueError("retry count exceeded")

    def _unpack_fetch_results(
        self,
        results: Any,
        urls: List[str],
        parser: Union[str, None] = None,
    ) -> List[Any]:
        """Convert raw HTML strings into BeautifulSoup objects."""
        from bs4 import BeautifulSoup

        final: List[Any] = []
        for i, result in enumerate(results):
            url = urls[i]
            chosen_parser = parser
            if chosen_parser is None:
                chosen_parser = "xml" if url.endswith(".xml") else self.default_parser
                self._check_parser(chosen_parser)
            final.append(BeautifulSoup(result, chosen_parser, **self.bs_kwargs))
        return final

    async def ascrape_all(
        self,
        urls: List[str],
        parser: Union[str, None] = None,
    ) -> List[Any]:
        """Fetch all *urls* asynchronously and return parsed soups."""
        results = await self.fetch_all(urls)
        return self._unpack_fetch_results(results, urls, parser=parser)

    def lazy_load(self) -> Iterator[Document]:
        """Load documents synchronously with per-URL error handling."""
        for path in self.web_paths:
            try:
                soup = self._scrape(path, bs_kwargs=self.bs_kwargs)
                text = soup.get_text(**self.bs_get_text_kwargs)
                metadata = extract_metadata(soup, path)
                yield Document(page_content=text, metadata=metadata)
            except Exception as exc:
                log.exception("Error loading %s: %s", path, exc)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Load documents asynchronously with metadata extraction."""
        results = await self.ascrape_all(self.web_paths)
        for path, soup in zip(self.web_paths, results):
            text = soup.get_text(**self.bs_get_text_kwargs)
            metadata = extract_metadata(soup, path)
            yield Document(page_content=text, metadata=metadata)

    async def aload(self) -> list[Document]:
        """Collect all documents into a list."""
        return [doc async for doc in self.alazy_load()]


# ---------------------------------------------------------------------------
# Loader engine registry
# ---------------------------------------------------------------------------

RAG_WEB_LOADER_ENGINES: defaultdict[str, type] = defaultdict(lambda: SafeWebBaseLoader)
RAG_WEB_LOADER_ENGINES["playwright"] = SafePlaywrightURLLoader
RAG_WEB_LOADER_ENGINES["safe_web"] = SafeWebBaseLoader
RAG_WEB_LOADER_ENGINES["firecrawl"] = SafeFireCrawlLoader
RAG_WEB_LOADER_ENGINES["tavily"] = SafeTavilyLoader


def get_web_loader(
    urls: Union[str, Sequence[str]],
    verify_ssl: bool = True,
    requests_per_second: int = 2,
    trust_env: bool = False,
) -> BaseLoader:
    """Construct a web document loader based on the configured engine.

    Selects among :class:`SafeWebBaseLoader`, :class:`SafePlaywrightURLLoader`,
    :class:`SafeFireCrawlLoader`, and :class:`SafeTavilyLoader` according to
    ``RAG_WEB_LOADER_ENGINE`` and injects the appropriate credentials.

    Args:
        urls: One URL or a sequence of URLs to load.
        verify_ssl: Verify SSL certificates during fetches.
        requests_per_second: Rate-limit for outgoing requests.
        trust_env: Honour environment proxy settings.

    Returns:
        An instance of the selected loader class.
    """
    url_list = [urls] if isinstance(urls, str) else list(urls)
    safe_urls = safe_validate_urls(url_list)

    loader_kwargs: Dict[str, Any] = {
        "web_paths": safe_urls,
        "verify_ssl": verify_ssl,
        "requests_per_second": requests_per_second,
        "continue_on_failure": True,
        "trust_env": trust_env,
    }

    engine = RAG_WEB_LOADER_ENGINE.value

    if engine == "playwright":
        loader_kwargs["playwright_timeout"] = PLAYWRIGHT_TIMEOUT.value * 1000
        if PLAYWRIGHT_WS_URI.value:
            loader_kwargs["playwright_ws_url"] = PLAYWRIGHT_WS_URI.value

    elif engine == "firecrawl":
        loader_kwargs["api_key"] = FIRECRAWL_API_KEY.value
        loader_kwargs["api_url"] = FIRECRAWL_API_BASE_URL.value

    elif engine == "tavily":
        loader_kwargs["api_key"] = TAVILY_API_KEY.value
        loader_kwargs["extract_depth"] = TAVILY_EXTRACT_DEPTH.value

    loader_cls = RAG_WEB_LOADER_ENGINES[engine]
    loader = loader_cls(**loader_kwargs)

    log.debug(
        "Using RAG_WEB_LOADER_ENGINE %s for %d URLs",
        loader.__class__.__name__,
        len(safe_urls),
    )
    return loader
