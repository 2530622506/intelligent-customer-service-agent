from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.auth.types import DataScope
from app.business.schemas import (
    AnalyticsQuery,
    AnalyticsResult,
    OrderLookupResult,
    PolicyAnswer,
    TicketDraft,
    TroubleshootingState,
)
from app.business.sql_gateway import ReadOnlySQLGateway, SQLPolicyError
from app.business.tools import MockLogisticsTool, MockOrderTool, MockTicketTool


@dataclass
class PolicyAgent:
    """政策 Agent 只消费外部检索证据，禁止凭空补写制度。"""

    def answer(self, answer: str, citations: list[str]) -> PolicyAnswer:
        return PolicyAnswer(answer=answer, citations=citations, grounded=bool(citations))


@dataclass
class TroubleshootingAgent:
    def next_step(self, state: TroubleshootingState) -> TroubleshootingState:
        if not state.product_model:
            return state.model_copy(update={"next_question": "请提供产品型号。"})
        if not state.symptom:
            return state.model_copy(update={"next_question": "请描述具体故障现象。"})
        if len(state.attempted_steps) < 2:
            return state.model_copy(update={"next_question": "请尝试重启设备后告诉我结果。"})
        return state.model_copy(update={"escalation_required": True, "next_question": None})


@dataclass
class OrderLogisticsAgent:
    order_tool: MockOrderTool
    logistics_tool: MockLogisticsTool

    def lookup(self, order_no: str, scope: DataScope) -> tuple[OrderLookupResult, dict[str, str | bool]]:
        return self.order_tool.lookup(order_no, scope), self.logistics_tool.lookup(order_no, scope)


@dataclass
class AnalyticsAgent:
    gateway: ReadOnlySQLGateway

    def validate_query(self, query: AnalyticsQuery) -> AnalyticsResult:
        try:
            self.gateway.validate(query.sql)
            return AnalyticsResult(accepted=True)
        except SQLPolicyError as error:
            return AnalyticsResult(accepted=False, reason=str(error))


@dataclass
class TicketAgent:
    ticket_tool: MockTicketTool

    def preview(self, draft: TicketDraft, customer_id: UUID) -> dict[str, object]:
        return self.ticket_tool.preview(draft, customer_id)
