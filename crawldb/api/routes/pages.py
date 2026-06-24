"""Pages API routes — list and retrieve crawled pages from MongoDB."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from crawldb.api.app import get_mongo

router = APIRouter()


@router.get("/pages")
async def list_pages(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
) -> dict:
    """List crawled pages with optional domain filtering."""
    mongo = get_mongo()
    pages = await mongo.list_pages(domain=domain, page=page, size=size)
    total = await mongo.count_pages(domain=domain)

    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": [
            {
                "url": p.url,
                "domain": p.domain,
                "title": p.title,
                "status_code": p.status_code,
                "depth": p.depth,
                "links_found": p.links_found,
                "fetch_time_ms": p.fetch_time_ms,
                "crawled_at": p.crawled_at.isoformat() if p.crawled_at else None,
            }
            for p in pages
        ],
    }


@router.get("/pages/{url:path}")
async def get_page(url: str, raw_html: bool = Query(False, description="Include raw HTML in JSON response")) -> dict:
    """Get a single crawled page by URL."""
    mongo = get_mongo()

    # Try with both http and https
    page = await mongo.get_page(url)
    if not page and not url.startswith("http"):
        page = await mongo.get_page(f"https://{url}")
        if not page:
            page = await mongo.get_page(f"http://{url}")

    if not page:
        return {"error": "Page not found", "url": url}

    result = {
        "url": page.url,
        "domain": page.domain,
        "title": page.title,
        "text_content": page.text_content[:5000],  # Limit response size
        "content_hash": page.content_hash,
        "status_code": page.status_code,
        "depth": page.depth,
        "parent_url": page.parent_url,
        "links_found": page.links_found,
        "fetch_time_ms": page.fetch_time_ms,
        "crawled_at": page.crawled_at.isoformat() if page.crawled_at else None,
    }
    if raw_html:
        result["html"] = page.html
    return result


from fastapi.responses import HTMLResponse

@router.get("/pages/{url:path}/html", response_class=HTMLResponse)
async def get_page_html(url: str):
    """Get the raw HTML content of a crawled page to view in browser."""
    mongo = get_mongo()
    page = await mongo.get_page(url)
    if not page and not url.startswith("http"):
        page = await mongo.get_page(f"https://{url}")
        if not page:
            page = await mongo.get_page(f"http://{url}")

    if not page:
        return HTMLResponse(content="<h1>Page not found</h1>", status_code=404)

    return HTMLResponse(content=page.html)

