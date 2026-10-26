from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["policy", "troubleshooting", "order_logistics", "analytics", "ticket"]


class AgentPlan(BaseModel):
    """Supervisor 输出的受控计划，不允许携带未注册 Agent。"""

    intent: str = Field(min_length=1, max_length=80)
    agents: list[AgentName] = Field(min_length=1, max_length=4)
    tools: list[str] = Field(default_factory=list, max_length=6)
    reason: str = Field(default="", max_length=500)
    requires_approval: bool = False
    requires_handoff: bool = False


class AgentResult(BaseModel):
    agent: AgentName
    status: Literal["completed", "needs_input", "handoff", "failed"] = "completed"
    summary: str
    tool_calls: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class ResumeDecision(BaseModel):
    approved: bool
    note: str = ""
