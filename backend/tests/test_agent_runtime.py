from langgraph.types import Command

from app.agent.runtime import ControlledAgentRuntime, RuntimePolicy


def test_runtime_routes_policy_and_enforces_registered_tools() -> None:
    runtime = ControlledAgentRuntime()
    result = runtime.invoke("退货政策是什么？", "policy-test")

    assert result["intent"] == "policy"
    assert result["results"][0]["agent"] == "policy"


def test_runtime_rejects_budget_overflow() -> None:
    runtime = ControlledAgentRuntime(policy=RuntimePolicy(max_tool_calls=1))
    result = runtime.invoke("我的订单物流到哪里了？", "budget-test")

    assert result["error_code"] == "TOOL_BUDGET_EXCEEDED"


def test_runtime_interrupt_can_resume() -> None:
    runtime = ControlledAgentRuntime()
    runtime.registry.get("ticket")
    # 使用 graph 直接注入审批计划，验证 LangGraph checkpoint / Command resume。
    graph = runtime.graph
    config = {"configurable": {"thread_id": "interrupt-test"}}
    initial = graph.invoke(
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
    resumed = graph.invoke(Command(resume={"approved": True, "note": "同意演示"}), config)
    assert resumed["approval_status"] == "approved"
