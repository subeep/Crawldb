"""Search API routes — full-text search via Elasticsearch."""

from fastapi import APIRouter, Query

from crawldb.api.app import get_elastic
from crawldb.storage.models import SearchResponse

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Results per page"),
) -> SearchResponse:
    """Full-text search across all crawled pages."""
    elastic = get_elastic()
    return await elastic.search(query=q, page=page, size=size)
