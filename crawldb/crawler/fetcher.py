"""Async HTTP fetcher with rate limiting, retries, and connection pooling."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from crawldb.config import settings

logger = logging.getLogger("crawldb.fetcher")

# Rotate user agents to reduce blocking
USER_AGENTS = [
    settings.user_agent,
    "Mozilla/5.0 (compatible; CrawlDB/1.0; +https://github.com/crawldb)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class FetchResult:
    """Result of an HTTP fetch operation."""
    url: str
    status: int = 0
    html: str = ""
    headers: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    success: bool = False


class AsyncFetcher:
    """
    High-performance async HTTP fetcher.

    Features:
    - Connection pooling via aiohttp.TCPConnector
    - Global concurrency semaphore
    - Per-domain rate limiting
    - Exponential backoff retry on 429/5xx
    - User-Agent rotation
    """

    def __init__(self, concurrency: int = None) -> None:
        self.concurrency = concurrency or settings.crawler_concurrency
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.session: Optional[aiohttp.ClientSession] = None
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._domain_last_request: dict[str, float] = {}
        self._ua_index = 0

    async def start(self) -> None:
        """Create the aiohttp session with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=5,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        logger.info("AsyncFetcher started with concurrency=%d", self.concurrency)

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("AsyncFetcher closed")

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def _next_user_agent(self) -> str:
        """Rotate user agents."""
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def _rate_limit(self, domain: str) -> None:
        """Enforce per-domain rate limiting."""
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()

        async with self._domain_locks[domain]:
            last = self._domain_last_request.get(domain, 0)
            delay = settings.crawler_delay_ms / 1000.0
            elapsed = time.monotonic() - last
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            self._domain_last_request[domain] = time.monotonic()

    async def fetch(self, url: str, max_retries: int = 3) -> FetchResult:
        """
        Fetch a URL with rate limiting, retries, and error handling.

        Returns a FetchResult with the HTML content or error details.
        """
        domain = self._get_domain(url)
        result = FetchResult(url=url)

        for attempt in range(max_retries):
            try:
                # Rate limit per domain
                await self._rate_limit(domain)

                # Global concurrency limit
                async with self.semaphore:
                    start = time.monotonic()
                    headers = {"User-Agent": self._next_user_agent()}

                    async with self.session.get(
                        url,
                        headers=headers,
                        allow_redirects=True,
                        max_redirects=5,
                    ) as response:
                        elapsed = (time.monotonic() - start) * 1000
                        result.status = response.status
                        result.elapsed_ms = elapsed
                        result.headers = dict(response.headers)

                        # Only process HTML responses
                        content_type = response.headers.get("Content-Type", "")
                        if "text/html" not in content_type and "application/xhtml" not in content_type:
                            result.error = f"Non-HTML content: {content_type}"
                            result.success = False
                            return result

                        if response.status == 200:
                            result.html = await response.text(errors="replace")
                            result.success = True
                            return result

                        # Retry on 429 or 5xx
                        if response.status == 429 or response.status >= 500:
                            wait = (2 ** attempt) * 1.0
                            logger.warning(
                                "Retry %d/%d for %s (status %d), waiting %.1fs",
                                attempt + 1, max_retries, url, response.status, wait,
                            )
                            await asyncio.sleep(wait)
                            continue

                        # Non-retryable error (4xx except 429)
                        result.error = f"HTTP {response.status}"
                        result.success = False
                        return result

            except asyncio.TimeoutError:
                result.error = "Timeout"
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                result.error = str(e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                result.error = f"Unexpected: {e}"
                logger.exception("Unexpected error fetching %s", url)
                return result

        result.success = False
        return result
