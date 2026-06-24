"""MongoDB storage layer using Motor (async driver)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from crawldb.config import settings
from crawldb.storage.models import CrawledPage, CrawlStats

logger = logging.getLogger("crawldb.mongo")


class MongoStore:
    """Async MongoDB client for storing crawled pages and dedup hashes."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        """Establish connection and create indexes."""
        self.client = AsyncIOMotorClient(settings.mongo_uri)
        self.db = self.client[settings.mongo_db]

        # Create indexes
        pages = self.db.pages
        await pages.create_index("url", unique=True)
        await pages.create_index("domain")
        await pages.create_index("content_hash")
        await pages.create_index("crawled_at")

        hashes = self.db.content_hashes
        await hashes.create_index("hash", unique=True)

        logger.info("Connected to MongoDB at %s", settings.mongo_uri)

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    # ─── Pages ───

    async def insert_page(self, page: CrawledPage) -> str:
        """Insert a crawled page. Returns the inserted ID."""
        doc = page.model_dump(by_alias=True, exclude={"id"})
        doc["crawled_at"] = datetime.utcnow()
        result = await self.db.pages.update_one(
            {"url": page.url},
            {"$set": doc},
            upsert=True,
        )
        return str(result.upserted_id or "updated")

    async def get_page(self, url: str) -> Optional[CrawledPage]:
        """Get a single page by URL."""
        doc = await self.db.pages.find_one({"url": url})
        if doc:
            doc["_id"] = str(doc["_id"])
            return CrawledPage(**doc)
        return None

    async def list_pages(
        self,
        domain: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> list[CrawledPage]:
        """List crawled pages with optional domain filter."""
        query = {}
        if domain:
            query["domain"] = domain
        cursor = (
            self.db.pages.find(query)
            .sort("crawled_at", -1)
            .skip((page - 1) * size)
            .limit(size)
        )
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # Don't include full HTML in list responses
            doc.pop("html", None)
            results.append(CrawledPage(**doc))
        return results

    async def count_pages(self, domain: Optional[str] = None) -> int:
        """Count total pages."""
        query = {}
        if domain:
            query["domain"] = domain
        return await self.db.pages.count_documents(query)

    # ─── Deduplication ───

    async def is_duplicate(self, content_hash: str) -> bool:
        """Check if content hash already exists."""
        doc = await self.db.content_hashes.find_one({"hash": content_hash})
        return doc is not None

    async def mark_hash_seen(self, content_hash: str, url: str) -> None:
        """Mark a content hash as seen."""
        await self.db.content_hashes.update_one(
            {"hash": content_hash},
            {"$set": {"hash": content_hash, "url": url, "seen_at": datetime.utcnow()}},
            upsert=True,
        )

    # ─── Stats ───

    async def get_stats(self) -> CrawlStats:
        """Get aggregated crawl statistics."""
        pages_crawled = await self.db.pages.count_documents({})
        unique_domains = len(await self.db.pages.distinct("domain"))
        duplicates_skipped = await self.db.content_hashes.count_documents({})

        return CrawlStats(
            pages_crawled=pages_crawled,
            unique_domains=unique_domains,
            duplicates_skipped=duplicates_skipped,
        )
