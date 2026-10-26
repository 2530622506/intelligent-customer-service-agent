from __future__ import annotations

import json
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import Settings


class RabbitPublisher:
    """最小 RabbitMQ publisher；任务 body 只传 ID，不把正文塞进消息。"""

    exchange_name = "customer_service.tasks"
    queue_name = "customer_service.document_parse"
    routing_key = "document.parse"

    def __init__(self, settings: Settings) -> None:
        self._url = settings.rabbitmq_url

    async def publish_parse(self, task_id: str) -> None:
        connection = await aio_pika.connect_robust(self._url)
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self.exchange_name, ExchangeType.DIRECT, durable=True
            )
            queue = await channel.declare_queue(self.queue_name, durable=True)
            await queue.bind(exchange, routing_key=self.routing_key)
            await exchange.publish(
                Message(
                    json.dumps({"type": "document.parse", "taskId": task_id}).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key=self.routing_key,
            )
        finally:
            await connection.close()


def parse_task_id(message: aio_pika.IncomingMessage) -> str:
    payload: dict[str, Any] = json.loads(message.body.decode("utf-8"))
    task_id = payload.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("RabbitMQ parse message 缺少 taskId")
    return task_id
