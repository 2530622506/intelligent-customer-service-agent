from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.runtime import ControlledAgentRuntime


@asynccontextmanager
async def postgres_runtime(database_url: str) -> AsyncIterator[ControlledAgentRuntime]:
    """创建生产 Runtime；checkpointer 与 PostgreSQL 连接在上下文结束时释放。"""
    psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(psycopg_url) as saver:
        await saver.setup()
        yield ControlledAgentRuntime(checkpointer=saver)
