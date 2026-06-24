"""Crawl management API routes — submit seed URLs and check status."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter

from crawldb.api.app import get_frontier
from crawldb.storage.models import CrawlMessage, CrawlRequest

logger = logging.getLogger("crawldb.api.crawl")

router = APIRouter()


@router.post("/crawl")
async def start_crawl(request: CrawlRequest) -> dict:
    """
    Submit seed URLs to begin crawling.

    Publishes each URL as a message to the RabbitMQ crawl frontier.
    """
    frontier = get_frontier()
    messages = []

    for url in request.urls:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        messages.append(CrawlMessage(
            url=url,
            depth=0,
            parent_url=None,
            domain=urlparse(url).netloc,
        ))

    count = await frontier.publish_batch(messages)
    logger.info("Submitted %d seed URLs to crawl frontier", count)

    return {
        "status": "queued",
        "urls_submitted": count,
        "max_depth": request.max_depth,
    }


@router.get("/crawl/status")
async def crawl_status() -> dict:
    """Get the current crawl queue status."""
    frontier = get_frontier()
    depth = await frontier.get_queue_depth()
    return {
        "queue_depth": depth,
        "status": "active" if depth > 0 else "idle",
    }
