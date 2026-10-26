from uuid import uuid4

import pytest
from langgraph.types import Command

from app.agent.checkpointer import postgres_runtime


@pytest.mark.asyncio
async def test_postgres_checkpointer_resumes_interrupt() -> None:
    async with postgres_runtime(
        "postgresql+asyncpg://app:app@127.0.0.1:15432/customer_service"
    ) as runtime:
        config = {"configurable": {"thread_id": f"postgres-interrupt-{uuid4()}"}}
        initial = await runtime.graph.ainvoke(
            {
                "question": "申请退款",
                "user_id": "demo",
                "plan": {
                    "intent": "ticket",
                    "agents": ["ticket"],
                    "tools": ["approval_preview"],
                    "requires_approval": True,
                },
                "events": [],
                "results": [],
            },
            config,
        )
        assert "__interrupt__" in initial
        resumed = await runtime.graph.ainvoke(
            Command(resume={"approved": True, "note": "同意演示"}), config
        )
        assert resumed["approval_status"] == "approved"
