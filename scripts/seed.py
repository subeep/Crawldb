"""
CLI script to submit seed URLs to the CrawlDB crawl frontier.

Usage:
    python -m scripts.seed https://example.com --depth 2
    python -m scripts.seed https://example.com https://python.org --depth 3
"""

import argparse
import asyncio
import sys
from urllib.parse import urlparse

# Adjust path for running from project root
sys.path.insert(0, ".")

from crawldb.crawler.frontier import Frontier
from crawldb.storage.models import CrawlMessage


async def seed_urls(urls: list[str], max_depth: int) -> None:
    """Connect to RabbitMQ and publish seed URLs."""
    frontier = Frontier()
    await frontier.connect()

    messages = []
    for url in urls:
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
    print(f"✓ Published {count} seed URL(s) to crawl frontier")
    print(f"  Max depth: {max_depth}")
    for m in messages:
        print(f"  → {m.url}")

    await frontier.close()


def main():
    parser = argparse.ArgumentParser(description="Seed URLs into CrawlDB")
    parser.add_argument("urls", nargs="+", help="URLs to crawl")
    parser.add_argument("--depth", type=int, default=2, help="Max crawl depth (default: 2)")
    args = parser.parse_args()

    asyncio.run(seed_urls(args.urls, args.depth))


if __name__ == "__main__":
    main()
