"""
CrawlDB Worker — the main async crawl loop.

This is the heart of the distributed crawler. Each worker:
1. Consumes URL messages from RabbitMQ
2. Checks robots.txt compliance
3. Fetches pages via AsyncFetcher
4. Parses HTML to extract content and links
5. Deduplicates via SHA-256 content hashing
6. Stores raw pages in MongoDB
7. Indexes searchable content in Elasticsearch
8. Re-queues discovered links back to the frontier

Run as: python -m crawldb.crawler.worker
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from urllib.parse import urlparse

from crawldb.config import settings
from crawldb.crawler.dedup import compute_content_hash
from crawldb.crawler.fetcher import AsyncFetcher
from crawldb.crawler.frontier import Frontier
from crawldb.crawler.parser import parse_page
from crawldb.crawler.robots import RobotsCache
from crawldb.metrics.collectors import metrics
from crawldb.storage.elastic import SearchIndex
from crawldb.storage.models import CrawledPage, CrawlEvent, CrawlMessage
from crawldb.storage.mongo import MongoStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("crawldb.worker")

# Global event bus for WebSocket broadcasting
# When running in the same process as API, this list is shared
event_listeners: list[asyncio.Queue] = []


def broadcast_event(event: CrawlEvent) -> None:
    """Broadcast a crawl event to all connected WebSocket listeners."""
    for q in event_listeners:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop events for slow consumers


class CrawlWorker:
    """Async crawl worker that processes URLs from the frontier."""

    def __init__(self) -> None:
        self.mongo = MongoStore()
        self.elastic = SearchIndex()
        self.frontier = Frontier()
        self.fetcher = AsyncFetcher()
        self.robots = RobotsCache()
        self._seen_urls: set[str] = set()
        self._running = True

    async def start(self) -> None:
        """Initialize all connections."""
        await self.mongo.connect()
        await self.elastic.connect()
        await self.frontier.connect()
        await self.fetcher.start()
        await self.robots.start(self.fetcher.session)
        logger.info(
            "CrawlWorker started — concurrency=%d, max_depth=%d",
            settings.crawler_concurrency,
            settings.max_depth,
        )

    async def stop(self) -> None:
        """Gracefully shut down all connections."""
        self._running = False
        await self.fetcher.close()
        await self.frontier.close()
        await self.elastic.close()
        await self.mongo.close()
        logger.info("CrawlWorker stopped")

    async def process_url(self, message: CrawlMessage) -> None:
        """Process a single URL from the crawl frontier."""
        url = message.url
        depth = message.depth

        # Skip if already seen in this session
        if url in self._seen_urls:
            return
        self._seen_urls.add(url)

        # Cap seen URLs set to prevent memory bloat
        if len(self._seen_urls) > 500000:
            # Keep only the most recent half
            self._seen_urls = set(list(self._seen_urls)[-250000:])

        domain = urlparse(url).netloc

        try:
            # 1. Check robots.txt
            allowed = await self.robots.is_allowed(url)
            if not allowed:
                logger.debug("Blocked by robots.txt: %s", url)
                metrics.errors_total.labels(error_type="robots_blocked").inc()
                return

            # 2. Fetch the page
            result = await self.fetcher.fetch(url)
            metrics.fetch_duration.observe(result.elapsed_ms / 1000.0)

            if not result.success:
                logger.debug("Fetch failed for %s: %s", url, result.error)
                metrics.errors_total.labels(error_type="fetch_failed").inc()
                broadcast_event(CrawlEvent(
                    event_type="error",
                    url=url,
                    detail=result.error or "Unknown error",
                ))
                return

            # 3. Parse HTML
            parsed = parse_page(result.html, url)

            # 4. Content deduplication
            content_hash = compute_content_hash(parsed.text_content)
            is_dup = await self.mongo.is_duplicate(content_hash)

            if is_dup:
                logger.debug("Duplicate content: %s", url)
                metrics.duplicates_total.inc()
                broadcast_event(CrawlEvent(
                    event_type="duplicate",
                    url=url,
                    detail=f"Content hash: {content_hash[:16]}...",
                ))
                return

            # 5. Mark hash as seen
            await self.mongo.mark_hash_seen(content_hash, url)

            # 6. Store in MongoDB
            page = CrawledPage(
                url=url,
                domain=domain,
                title=parsed.title,
                text_content=parsed.text_content,
                html=result.html,
                content_hash=content_hash,
                depth=depth,
                parent_url=message.parent_url,
                status_code=result.status,
                crawled_at=datetime.utcnow(),
                links_found=len(parsed.links),
                fetch_time_ms=result.elapsed_ms,
            )
            await self.mongo.insert_page(page)
            metrics.pages_crawled.inc()

            # 7. Index in Elasticsearch
            await self.elastic.index_page(page)
            metrics.pages_indexed.inc()

            logger.info(
                "✓ Crawled [depth=%d] %s — %s (%d links, %.0fms)",
                depth, url, parsed.title[:60], len(parsed.links), result.elapsed_ms,
            )
            broadcast_event(CrawlEvent(
                event_type="crawled",
                url=url,
                detail=f"{parsed.title[:80]} | {len(parsed.links)} links | {result.elapsed_ms:.0f}ms",
            ))

            # 8. Re-queue discovered links
            if depth < settings.max_depth:
                links = parsed.internal_links if settings.same_domain_only else parsed.links
                new_messages = []
                for link in links:
                    if link not in self._seen_urls:
                        new_messages.append(CrawlMessage(
                            url=link,
                            depth=depth + 1,
                            parent_url=url,
                            domain=urlparse(link).netloc,
                        ))

                if new_messages:
                    count = await self.frontier.publish_batch(new_messages)
                    metrics.queue_depth.inc(count)
                    logger.debug("Re-queued %d links from %s", count, url)

        except Exception as e:
            logger.error("Error processing %s: %s", url, e, exc_info=True)
            metrics.errors_total.labels(error_type="processing_error").inc()
            broadcast_event(CrawlEvent(
                event_type="error",
                url=url,
                detail=str(e),
            ))


async def main() -> None:
    """Main entry point for the crawler worker process."""
    worker = CrawlWorker()

    # Handle graceful shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
        logger.info("Waiting for crawl messages...")

        # Start consuming from RabbitMQ
        await worker.frontier.consume(worker.process_url)

    except asyncio.CancelledError:
        pass
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
