"""robots.txt parser and cache."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from crawldb.config import settings

logger = logging.getLogger("crawldb.robots")


class RobotsCache:
    """
    Async robots.txt fetcher and cache.

    Caches parsed robots.txt per domain with a configurable TTL.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self, session: aiohttp.ClientSession = None) -> None:
        """Initialize with an optional shared session."""
        if session:
            self._session = session
        else:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
            )

    async def close(self) -> None:
        """Close the session if we own it."""
        # Don't close shared sessions
        pass

    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given page URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    async def _fetch_robots(self, domain: str, robots_url: str) -> RobotFileParser:
        """Fetch and parse robots.txt for a domain."""
        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            async with self._session.get(
                robots_url,
                headers={"User-Agent": settings.user_agent},
                allow_redirects=True,
            ) as response:
                if response.status == 200:
                    text = await response.text(errors="replace")
                    rp.parse(text.splitlines())
                else:
                    # If robots.txt doesn't exist or errors, allow everything
                    rp.parse([])
        except Exception as e:
            logger.debug("Could not fetch robots.txt for %s: %s", domain, e)
            rp.parse([])  # Allow everything on error

        return rp

    async def is_allowed(self, url: str) -> bool:
        """
        Check if crawling a URL is allowed by robots.txt.

        Returns True if allowed or if robots.txt cannot be fetched.
        """
        domain = self._get_domain(url)

        # Check cache
        if domain in self._cache:
            rp, cached_at = self._cache[domain]
            if time.monotonic() - cached_at < self.ttl:
                return rp.can_fetch(settings.user_agent, url)

        # Fetch with per-domain lock to avoid thundering herd
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()

        async with self._locks[domain]:
            # Double-check after acquiring lock
            if domain in self._cache:
                rp, cached_at = self._cache[domain]
                if time.monotonic() - cached_at < self.ttl:
                    return rp.can_fetch(settings.user_agent, url)

            robots_url = self._get_robots_url(url)
            rp = await self._fetch_robots(domain, robots_url)
            self._cache[domain] = (rp, time.monotonic())

        return rp.can_fetch(settings.user_agent, url)
