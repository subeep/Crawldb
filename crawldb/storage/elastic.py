"""Elasticsearch search index layer."""

from __future__ import annotations

import logging
from typing import Optional

from elasticsearch import AsyncElasticsearch

from crawldb.config import settings
from crawldb.storage.models import CrawledPage, SearchResponse, SearchResult

logger = logging.getLogger("crawldb.elastic")

# Index mapping for crawled pages
INDEX_NAME = "crawldb_pages"
INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "url": {"type": "keyword"},
            "domain": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "standard",
            },
            "content": {
                "type": "text",
                "analyzer": "standard",
            },
            "meta_description": {
                "type": "text",
            },
            "content_hash": {"type": "keyword"},
            "crawled_at": {"type": "date"},
            "status_code": {"type": "integer"},
            "depth": {"type": "integer"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "5s",
    },
}


class SearchIndex:
    """Async Elasticsearch client for full-text search indexing."""

    def __init__(self) -> None:
        self.client: Optional[AsyncElasticsearch] = None

    async def connect(self) -> None:
        """Connect to Elasticsearch and create index if needed."""
        self.client = AsyncElasticsearch(
            settings.elasticsearch_url,
            request_timeout=30,
        )

        # Create index if it doesn't exist
        exists = await self.client.indices.exists(index=INDEX_NAME)
        if not exists:
            await self.client.indices.create(
                index=INDEX_NAME,
                body=INDEX_MAPPING,
            )
            logger.info("Created Elasticsearch index '%s'", INDEX_NAME)

        logger.info("Connected to Elasticsearch at %s", settings.elasticsearch_url)

    async def close(self) -> None:
        """Close the Elasticsearch connection."""
        if self.client:
            await self.client.close()
            logger.info("Elasticsearch connection closed")

    async def index_page(self, page: CrawledPage) -> None:
        """Index a crawled page for full-text search."""
        doc = {
            "url": page.url,
            "domain": page.domain,
            "title": page.title,
            "content": page.text_content[:50000],  # Limit content size
            "content_hash": page.content_hash,
            "crawled_at": page.crawled_at.isoformat(),
            "status_code": page.status_code,
            "depth": page.depth,
        }
        await self.client.index(
            index=INDEX_NAME,
            id=page.url,  # Use URL as doc ID for upsert
            document=doc,
        )

    async def search(
        self,
        query: str,
        page: int = 1,
        size: int = 10,
    ) -> SearchResponse:
        """Full-text search with highlighted snippets."""
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "meta_description^2", "url"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
            "highlight": {
                "fields": {
                    "content": {
                        "fragment_size": 200,
                        "number_of_fragments": 2,
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                    },
                    "title": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                    },
                },
            },
            "from": (page - 1) * size,
            "size": size,
            "_source": ["url", "title", "domain", "crawled_at"],
        }

        resp = await self.client.search(index=INDEX_NAME, body=body)

        results = []
        for hit in resp["hits"]["hits"]:
            source = hit["_source"]
            highlight = hit.get("highlight", {})
            snippet = ""
            if "content" in highlight:
                snippet = " ... ".join(highlight["content"])
            elif "title" in highlight:
                snippet = " ... ".join(highlight["title"])

            results.append(
                SearchResult(
                    url=source["url"],
                    title=source.get("title", ""),
                    snippet=snippet,
                    domain=source.get("domain", ""),
                    score=hit["_score"],
                    crawled_at=source.get("crawled_at"),
                )
            )

        total = resp["hits"]["total"]["value"]
        took_ms = resp.get("took", 0)

        return SearchResponse(
            query=query,
            total=total,
            page=page,
            size=size,
            results=results,
            took_ms=took_ms,
        )

    async def get_stats(self) -> dict:
        """Get index statistics."""
        try:
            stats = await self.client.indices.stats(index=INDEX_NAME)
            idx_stats = stats["indices"].get(INDEX_NAME, {}).get("primaries", {})
            return {
                "docs_count": idx_stats.get("docs", {}).get("count", 0),
                "size_bytes": idx_stats.get("store", {}).get("size_in_bytes", 0),
            }
        except Exception:
            return {"docs_count": 0, "size_bytes": 0}

    async def delete_index(self) -> None:
        """Delete the search index (for testing/reset)."""
        exists = await self.client.indices.exists(index=INDEX_NAME)
        if exists:
            await self.client.indices.delete(index=INDEX_NAME)
            logger.info("Deleted index '%s'", INDEX_NAME)
