"""Pydantic models for CrawlDB data structures."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    """Request to start a crawl."""
    urls: list[str]
    max_depth: int = 3


class CrawlMessage(BaseModel):
    """Message published to RabbitMQ crawl frontier."""
    url: str
    depth: int = 0
    parent_url: Optional[str] = None
    domain: str = ""
    enqueued_at: datetime = Field(default_factory=datetime.utcnow)


class CrawledPage(BaseModel):
    """A fully crawled and parsed page stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    url: str
    domain: str
    title: str = ""
    text_content: str = ""
    html: str = ""
    content_hash: str = ""
    depth: int = 0
    parent_url: Optional[str] = None
    status_code: int = 0
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    links_found: int = 0
    fetch_time_ms: float = 0.0

    model_config = {"populate_by_name": True}


class SearchResult(BaseModel):
    """A single search result from Elasticsearch."""
    url: str
    title: str
    snippet: str = ""
    domain: str = ""
    score: float = 0.0
    crawled_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Paginated search response."""
    query: str
    total: int
    page: int
    size: int
    results: list[SearchResult]
    took_ms: float = 0.0


class CrawlStats(BaseModel):
    """Aggregated crawl statistics."""
    pages_crawled: int = 0
    pages_indexed: int = 0
    unique_domains: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    queue_depth: int = 0
    index_size_bytes: int = 0


class CrawlEvent(BaseModel):
    """Real-time crawl event for WebSocket broadcast."""
    event_type: str  # "crawled", "duplicate", "error", "queued"
    url: str
    detail: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
