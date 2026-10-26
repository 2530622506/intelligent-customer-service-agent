from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.agent.contracts import AgentName, AgentResult

AgentHandler = Callable[[AgentName, list[str]], AgentResult]


@dataclass(frozen=True)
class AgentDefinition:
    name: AgentName
    allowed_tools: frozenset[str]
    handler: AgentHandler


class RegistryError(ValueError):
    """注册表中不存在或不允许使用的 Agent / Tool。"""


class AgentRegistry:
    def __init__(self, definitions: list[AgentDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}

    def get(self, name: str) -> AgentDefinition:
        try:
            return self._definitions[name]  # type: ignore[index]
        except KeyError as error:
            raise RegistryError(f"Agent 未注册：{name}") from error

    def validate_plan(self, names: Sequence[AgentName], max_agents: int) -> None:
        if not names or len(names) > max_agents:
            raise RegistryError(f"Agent 数量超出限制：{len(names)}/{max_agents}")
        for name in names:
            self.get(name)


class ToolRegistry:
    def __init__(self, tools: set[str]) -> None:
        self._tools = frozenset(tools)

    def validate(self, tools: list[str]) -> None:
        unknown = set(tools) - self._tools
        if unknown:
            raise RegistryError(f"Tool 未注册：{sorted(unknown)}")


def default_agent_registry() -> AgentRegistry:
    def handler(name: AgentName, tools: list[str]) -> AgentResult:
        return AgentResult(
            agent=name,
            summary=f"{name} 已完成受控演示处理",
            tool_calls=tools,
        )

    return AgentRegistry(
        [
            AgentDefinition("policy", frozenset({"knowledge_search", "graph_search"}), handler),
            AgentDefinition("troubleshooting", frozenset({"knowledge_search", "graph_search", "ticket_draft"}), handler),
            AgentDefinition("order_logistics", frozenset({"order_lookup", "logistics_lookup"}), handler),
            AgentDefinition("analytics", frozenset({"readonly_sql"}), handler),
            AgentDefinition("ticket", frozenset({"ticket_draft", "approval_preview"}), handler),
        ]
    )


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        {
            "knowledge_search",
            "graph_search",
            "ticket_draft",
            "order_lookup",
            "logistics_lookup",
            "readonly_sql",
            "approval_preview",
        }
    )
