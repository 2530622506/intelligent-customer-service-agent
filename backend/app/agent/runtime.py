from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent.contracts import AgentPlan, ResumeDecision
from app.agent.registry import (
    AgentRegistry,
    RegistryError,
    ToolRegistry,
    default_agent_registry,
    default_tool_registry,
)


class AgentState(TypedDict, total=False):
    question: str
    user_id: str
    intent: str
    plan: dict[str, Any]
    results: list[dict[str, Any]]
    events: list[dict[str, Any]]
    error_code: str | None
    approval_status: Literal["not_required", "pending", "approved", "rejected"]
    handoff_status: Literal["not_required", "pending", "queued"]
    node_steps: int
    tool_calls: int


class RuntimePolicy:
    def __init__(
        self,
        max_steps: int = 8,
        max_agents: int = 4,
        max_tool_calls: int = 6,
        max_tool_retries: int = 1,
    ) -> None:
        self.max_steps = max_steps
        self.max_agents = max_agents
        self.max_tool_calls = max_tool_calls
        self.max_tool_retries = max_tool_retries


class ControlledAgentRuntime:
    """固定安全节点包裹动态 Agent 选择，模型不能绕过这些节点。"""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        tools: ToolRegistry | None = None,
        policy: RuntimePolicy | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self.registry = registry or default_agent_registry()
        self.tools = tools or default_tool_registry()
        self.policy = policy or RuntimePolicy()
        self.graph = self._build_graph(checkpointer)

    def _build_graph(self, checkpointer: Any | None = None) -> Any:
        builder = StateGraph(AgentState)
        builder.add_node("precheck", self._precheck)
        builder.add_node("supervisor_plan", self._supervisor_plan)
        builder.add_node("policy_guard", self._policy_guard)
        builder.add_node("dispatch_agents", self._dispatch_agents)
        builder.add_node("approval_interrupt", self._approval_interrupt)
        builder.add_node("handoff_interrupt", self._handoff_interrupt)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "precheck")
        builder.add_edge("precheck", "supervisor_plan")
        builder.add_edge("supervisor_plan", "policy_guard")
        builder.add_conditional_edges("policy_guard", self._route_after_guard)
        builder.add_edge("dispatch_agents", "approval_interrupt")
        builder.add_conditional_edges("approval_interrupt", self._route_after_approval)
        builder.add_conditional_edges("handoff_interrupt", self._route_after_handoff)
        builder.add_edge("finalize", END)
        # 未注入生产 checkpointer 时使用内存版，保证纯单测无需数据库。
        return builder.compile(checkpointer=checkpointer or InMemorySaver())

    def invoke(self, question: str, thread_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], self.graph.invoke(
            {"question": question, "user_id": "demo", "events": [], "results": []},
            {"configurable": {"thread_id": thread_id}},
        ))

    def resume(self, thread_id: str, decision: ResumeDecision) -> dict[str, Any]:
        return cast(dict[str, Any], self.graph.invoke(
            Command(resume=decision.model_dump()),
            {"configurable": {"thread_id": thread_id}},
        ))

    def _precheck(self, state: AgentState) -> dict[str, Any]:
        question = state.get("question", "").strip()
        if not question:
            return {"error_code": "EMPTY_QUESTION", "node_steps": 1}
        return {"node_steps": 1, "events": [{"type": "run_started"}]}

    def _supervisor_plan(self, state: AgentState) -> dict[str, Any]:
        if state.get("plan"):
            return {"node_steps": state.get("node_steps", 0) + 1}
        question = state["question"]
        # 首版使用确定性规划器；接入 Qwen 后只替换该节点，安全 Guard 不变。
        if any(keyword in question for keyword in ("订单", "物流", "快递")):
            plan = AgentPlan(
                intent="order_logistics",
                agents=["order_logistics"],
                tools=["order_lookup", "logistics_lookup"],
                reason="命中订单 / 物流关键词",
            )
        elif any(keyword in question for keyword in ("故障", "坏", "维修")):
            plan = AgentPlan(
                intent="troubleshooting",
                agents=["troubleshooting"],
                tools=["knowledge_search", "ticket_draft"],
                reason="命中产品排障关键词",
            )
        else:
            plan = AgentPlan(
                intent="policy",
                agents=["policy"],
                tools=["knowledge_search", "graph_search"],
                reason="默认进入政策知识 Agent",
            )
        return {
            "intent": plan.intent,
            "plan": plan.model_dump(),
            "node_steps": state.get("node_steps", 0) + 1,
            "events": [{"type": "agent_step", "node": "supervisor_plan", "intent": plan.intent}],
        }

    def _policy_guard(self, state: AgentState) -> dict[str, Any]:
        plan = AgentPlan.model_validate(state["plan"])
        try:
            self.registry.validate_plan(plan.agents, self.policy.max_agents)
            self.tools.validate(plan.tools)
            allowed_tools = set().union(*(self.registry.get(agent).allowed_tools for agent in plan.agents))
            unauthorized = set(plan.tools) - allowed_tools
            if unauthorized:
                raise RegistryError(f"Agent 不允许调用 Tool：{sorted(unauthorized)}")
            if state.get("node_steps", 0) >= self.policy.max_steps:
                raise RegistryError("Agent 节点跳转超过预算")
            return {"node_steps": state.get("node_steps", 0) + 1}
        except RegistryError as error:
            return {"error_code": "PLAN_REJECTED", "events": [{"type": "error", "message": str(error)}]}

    def _route_after_guard(self, state: AgentState) -> str:
        return "finalize" if state.get("error_code") else "dispatch_agents"

    def _dispatch_agents(self, state: AgentState) -> dict[str, Any]:
        plan = AgentPlan.model_validate(state["plan"])
        results: list[dict[str, Any]] = []
        tool_count = state.get("tool_calls", 0)
        for agent_name in plan.agents:
            definition = self.registry.get(agent_name)
            allowed_tools = [tool for tool in plan.tools if tool in definition.allowed_tools]
            tool_count += len(allowed_tools)
            if tool_count > self.policy.max_tool_calls:
                return {"error_code": "TOOL_BUDGET_EXCEEDED"}
            results.append(definition.handler(agent_name, allowed_tools).model_dump())
        return {"results": results, "tool_calls": tool_count, "node_steps": state.get("node_steps", 0) + 1}

    def _approval_interrupt(self, state: AgentState) -> dict[str, Any]:
        plan = AgentPlan.model_validate(state["plan"])
        if not plan.requires_approval:
            return {"approval_status": "not_required", "node_steps": state.get("node_steps", 0) + 1}
        decision = ResumeDecision.model_validate(
            interrupt({"kind": "approval", "question": "是否批准该模拟动作？"})
        )
        return {
            "approval_status": "approved" if decision.approved else "rejected",
            "node_steps": state.get("node_steps", 0) + 1,
        }

    def _route_after_approval(self, state: AgentState) -> str:
        plan = AgentPlan.model_validate(state["plan"])
        if plan.requires_handoff:
            return "handoff_interrupt"
        return "finalize"

    def _handoff_interrupt(self, state: AgentState) -> dict[str, Any]:
        plan = AgentPlan.model_validate(state["plan"])
        if not plan.requires_handoff:
            return {"handoff_status": "not_required"}
        decision = ResumeDecision.model_validate(
            interrupt({"kind": "handoff", "question": "是否进入人工客服队列？"})
        )
        return {"handoff_status": "queued" if decision.approved else "not_required"}

    def _route_after_handoff(self, state: AgentState) -> str:
        return "finalize"

    def _finalize(self, state: AgentState) -> dict[str, Any]:
        return {
            "events": [{"type": "done"}],
            "node_steps": state.get("node_steps", 0) + 1,
        }
