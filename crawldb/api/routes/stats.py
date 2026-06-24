"""Stats API route — aggregated crawl statistics."""

from fastapi import APIRouter

from crawldb.api.app import get_mongo, get_elastic, get_frontier

router = APIRouter()


@router.get("/stats")
async def get_stats() -> dict:
    """Get aggregated crawl statistics from all data stores."""
    mongo = get_mongo()
    elastic = get_elastic()
    frontier = get_frontier()

    mongo_stats = await mongo.get_stats()
    es_stats = await elastic.get_stats()
    queue_depth = await frontier.get_queue_depth()

    return {
        "pages_crawled": mongo_stats.pages_crawled,
        "pages_indexed": es_stats.get("docs_count", 0),
        "unique_domains": mongo_stats.unique_domains,
        "duplicates_skipped": mongo_stats.duplicates_skipped,
        "queue_depth": queue_depth,
        "index_size_bytes": es_stats.get("size_bytes", 0),
        "queue_status": "active" if queue_depth > 0 else "idle",
    }
