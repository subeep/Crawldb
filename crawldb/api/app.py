"""
FastAPI application factory with lifespan management.

Creates the main app, mounts routes, static files, and middleware.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from crawldb.storage.mongo import MongoStore
from crawldb.storage.elastic import SearchIndex
from crawldb.crawler.frontier import Frontier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("crawldb.api")

# Shared service instances (set during lifespan)
mongo_store: MongoStore | None = None
search_index: SearchIndex | None = None
frontier: Frontier | None = None


def get_mongo() -> MongoStore:
    return mongo_store


def get_elastic() -> SearchIndex:
    return search_index


def get_frontier() -> Frontier:
    return frontier


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown of database connections."""
    global mongo_store, search_index, frontier

    # Startup
    mongo_store = MongoStore()
    await mongo_store.connect()

    search_index = SearchIndex()
    await search_index.connect()

    frontier = Frontier()
    await frontier.connect()

    logger.info("All services connected — API ready")

    yield

    # Shutdown
    await frontier.close()
    await search_index.close()
    await mongo_store.close()
    logger.info("All services disconnected — API shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CrawlDB",
        description="Distributed Web Crawler & Search Index API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics endpoint at /metrics
    Instrumentator().instrument(app).expose(app)

    # Import and include API routes
    from crawldb.api.routes.search import router as search_router
    from crawldb.api.routes.crawl import router as crawl_router
    from crawldb.api.routes.pages import router as pages_router
    from crawldb.api.routes.stats import router as stats_router
    from crawldb.api.websocket import router as ws_router

    app.include_router(search_router, prefix="/api", tags=["Search"])
    app.include_router(crawl_router, prefix="/api", tags=["Crawl"])
    app.include_router(pages_router, prefix="/api", tags=["Pages"])
    app.include_router(stats_router, prefix="/api", tags=["Stats"])
    app.include_router(ws_router, tags=["WebSocket"])

    # Mount the dashboard static files
    dashboard_path = Path(__file__).parent.parent / "dashboard"
    if dashboard_path.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(dashboard_path)),
            name="dashboard",
        )

        @app.get("/", include_in_schema=False)
        async def serve_dashboard():
            return FileResponse(str(dashboard_path / "index.html"))

    return app
