"""Prometheus metrics collectors for CrawlDB."""

from prometheus_client import Counter, Gauge, Histogram


class CrawlDBMetrics:
    """Custom Prometheus metrics for the crawler."""

    def __init__(self) -> None:
        self.pages_crawled = Counter(
            "crawldb_pages_crawled_total",
            "Total number of pages successfully crawled",
        )
        self.pages_indexed = Counter(
            "crawldb_pages_indexed_total",
            "Total number of pages indexed in Elasticsearch",
        )
        self.duplicates_total = Counter(
            "crawldb_duplicates_skipped_total",
            "Total number of duplicate pages skipped",
        )
        self.errors_total = Counter(
            "crawldb_errors_total",
            "Total number of crawl errors",
            labelnames=["error_type"],
        )
        self.queue_depth = Gauge(
            "crawldb_queue_depth",
            "Current number of URLs in the crawl frontier queue",
        )
        self.fetch_duration = Histogram(
            "crawldb_fetch_duration_seconds",
            "HTTP fetch duration in seconds",
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        )
        self.active_workers = Gauge(
            "crawldb_active_workers",
            "Number of currently active crawler workers",
        )


# Singleton
metrics = CrawlDBMetrics()
