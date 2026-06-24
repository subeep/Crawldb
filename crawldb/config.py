"""Centralized configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # MongoDB
    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db: str = "crawldb"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    # Elasticsearch
    elasticsearch_url: str = "http://elasticsearch:9200"

    # Crawler
    crawler_concurrency: int = 20
    crawler_delay_ms: int = 200
    max_depth: int = 3
    user_agent: str = "CrawlDB/1.0 (+https://github.com/crawldb)"
    same_domain_only: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
