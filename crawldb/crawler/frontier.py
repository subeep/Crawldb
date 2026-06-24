"""RabbitMQ crawl frontier — publish and consume URL messages."""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from crawldb.config import settings
from crawldb.storage.models import CrawlMessage

logger = logging.getLogger("crawldb.frontier")

EXCHANGE_NAME = "crawl_frontier"
QUEUE_NAME = "crawl_queue"
ROUTING_KEY = "crawl.url"


class Frontier:
    """Async RabbitMQ client for the crawl frontier queue."""

    def __init__(self) -> None:
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self.queue: Optional[aio_pika.Queue] = None

    async def connect(self) -> None:
        """Connect to RabbitMQ and declare exchange + queue."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Set prefetch for fair dispatching
        await self.channel.set_qos(prefetch_count=10)

        # Declare exchange and queue
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.DIRECT,
            durable=True,
        )
        self.queue = await self.channel.declare_queue(
            QUEUE_NAME,
            durable=True,
            arguments={
                "x-max-length": 100000,  # Cap queue size
                "x-overflow": "reject-publish",
            },
        )
        await self.queue.bind(self.exchange, routing_key=ROUTING_KEY)

        logger.info("Connected to RabbitMQ at %s", settings.rabbitmq_url)

    async def close(self) -> None:
        """Close the RabbitMQ connection."""
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed")

    async def publish(self, message: CrawlMessage) -> None:
        """Publish a URL message to the crawl frontier."""
        body = json.dumps(message.model_dump(mode="json")).encode()
        await self.exchange.publish(
            Message(
                body=body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=ROUTING_KEY,
        )

    async def publish_batch(self, messages: list[CrawlMessage]) -> int:
        """Publish a batch of URL messages. Returns count published."""
        count = 0
        for msg in messages:
            try:
                await self.publish(msg)
                count += 1
            except Exception as e:
                logger.warning("Failed to publish %s: %s", msg.url, e)
        return count

    async def consume(self, callback: Callable) -> None:
        """Start consuming messages. Callback receives CrawlMessage."""
        async with self.queue.iterator() as queue_iter:
            async for rmq_message in queue_iter:
                async with rmq_message.process():
                    try:
                        data = json.loads(rmq_message.body.decode())
                        crawl_msg = CrawlMessage(**data)
                        await callback(crawl_msg)
                    except Exception as e:
                        logger.error("Error processing message: %s", e)

    async def get_queue_depth(self) -> int:
        """Get the current number of messages in the queue."""
        if self.queue:
            # Re-declare to get updated message count
            queue = await self.channel.declare_queue(
                QUEUE_NAME, durable=True, passive=True,
            )
            return queue.declaration_result.message_count
        return 0
