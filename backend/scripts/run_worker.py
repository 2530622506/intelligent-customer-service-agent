"""启动文档解析 worker：只消费 task_id，正文从 RustFS 读取。"""

import asyncio
from uuid import UUID

import aio_pika

from app.core.config import get_settings
from app.document.service import DocumentPipelineService
from app.mq.rabbit import RabbitPublisher, parse_task_id


async def main() -> None:
    settings = get_settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        RabbitPublisher.exchange_name, aio_pika.ExchangeType.DIRECT, durable=True
    )
    queue = await channel.declare_queue(RabbitPublisher.queue_name, durable=True)
    await queue.bind(exchange, routing_key=RabbitPublisher.routing_key)

    async with queue.iterator() as messages:
        async for message in messages:
            async with message.process(requeue=False):
                task_id = parse_task_id(message)
                # Worker 自己创建数据库 session，避免复用 HTTP 请求生命周期。
                await DocumentPipelineService(settings, None).process(UUID(task_id))


if __name__ == "__main__":
    asyncio.run(main())
