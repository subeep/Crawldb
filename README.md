# CrawlDB

**Distributed Web Crawler & Search Index** — built with Python, asyncio, RabbitMQ, MongoDB, and Elasticsearch. Runs entirely locally via Docker Compose.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Dashboard   │────▶│  FastAPI API  │────▶│ Elasticsearch│
│  (Browser)   │◀────│  (port 8000) │     │  (Search)    │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐
                    │   RabbitMQ    │
                    │  (Frontier)  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌──────────────┐
                    │   Crawler    │────▶│   MongoDB    │
                    │  (Workers)   │     │  (Storage)   │
                    └──────────────┘     └──────────────┘
```

## Features

- **Async Crawl Engine** — aiohttp-based fetcher with connection pooling, per-domain rate limiting, and exponential backoff retry
- **RabbitMQ Frontier** — durable message queue for URL scheduling with priority and deduplication
- **Content Deduplication** — SHA-256 content hashing to skip duplicate pages
- **Full-Text Search** — Elasticsearch indexing with boosted title fields and highlighted snippets
- **MongoDB Storage** — raw page storage with structured metadata
- **Real-Time Dashboard** — WebSocket-powered live crawl feed, search UI, and stats
- **Prometheus + Grafana** — crawl throughput, latency percentiles, error rates, queue depth monitoring
- **robots.txt Compliance** — async robots.txt parser with per-domain caching

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- ~4-6 GB free RAM

### 1. Start Services

```bash
# Clone and start everything
docker compose up -d --build

# Watch logs
docker compose logs -f
```

### 2. Open Dashboard

Navigate to **http://localhost:8000** — you'll see the CrawlDB dashboard.

### 3. Start Crawling

**Option A: Dashboard UI**
1. Enter a seed URL (e.g., `https://example.com`)
2. Select crawl depth
3. Click "Start Crawl"

**Option B: API**
```bash
curl -X POST http://localhost:8000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"], "max_depth": 2}'
```

**Option C: CLI Script**
```bash
docker compose exec api python -m scripts.seed https://example.com --depth 2
```

### 4. Search

```bash
curl "http://localhost:8000/api/search?q=example&size=10"
```

### 5. Monitor

| Service     | URL                        | Credentials   |
|:------------|:---------------------------|:--------------|
| Dashboard   | http://localhost:8000      | —             |
| API Docs    | http://localhost:8000/docs | —             |
| RabbitMQ    | http://localhost:15672     | guest / guest |
| Grafana     | http://localhost:3000      | admin / crawldb |
| Prometheus  | http://localhost:9090      | —             |
| Elasticsearch | http://localhost:9200   | —             |

## API Endpoints

| Method | Endpoint             | Description                |
|:-------|:---------------------|:---------------------------|
| GET    | `/api/search`        | Full-text search           |
| POST   | `/api/crawl`         | Submit seed URLs           |
| GET    | `/api/crawl/status`  | Queue status               |
| GET    | `/api/pages`         | List crawled pages         |
| GET    | `/api/pages/{url}`   | Get page details           |
| GET    | `/api/stats`         | Aggregated statistics      |
| WS     | `/ws/live`           | Real-time crawl events     |
| GET    | `/metrics`           | Prometheus metrics         |

## Configuration

All settings via environment variables in `.env`:

| Variable              | Default  | Description              |
|:----------------------|:---------|:-------------------------|
| `CRAWLER_CONCURRENCY` | 20       | Max concurrent fetches   |
| `CRAWLER_DELAY_MS`    | 200      | Per-domain delay (ms)    |
| `MAX_DEPTH`           | 3        | Max link-follow depth    |
| `SAME_DOMAIN_ONLY`    | true     | Stay within seed domain  |

## Development

```bash
# Run unit tests
docker compose exec api pytest tests/ -v

# Stop services
docker compose down

# Reset all data
docker compose down -v
```

## Tech Stack

| Component   | Technology            |
|:------------|:----------------------|
| Crawler     | Python 3.12 + asyncio + aiohttp |
| Queue       | RabbitMQ 3.13         |
| Document DB | MongoDB 7.0           |
| Search      | Elasticsearch 8.15    |
| API         | FastAPI + Uvicorn     |
| Monitoring  | Prometheus + Grafana  |
| Container   | Docker Compose        |
