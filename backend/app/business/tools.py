from uuid import UUID

from app.auth.types import DataScope, ScopeType
from app.business.mock_data import MockAfterSalesData, MockTicket
from app.business.schemas import OrderLookupResult, TicketDraft


class ToolPolicyError(PermissionError):
    """业务工具拒绝越权或不安全请求。"""


class MockOrderTool:
    def __init__(self, data: MockAfterSalesData) -> None:
        self.data = data

    def lookup(self, order_no: str, scope: DataScope) -> OrderLookupResult:
        order = self.data.orders.get(order_no)
        if order is None:
            return OrderLookupResult(found=False, order_no=order_no)
        if scope.scope_type is ScopeType.SELF and order.customer_id != scope.user_id:
            raise ToolPolicyError("无权访问该订单")
        return OrderLookupResult(
            found=True,
            order_no=order.order_no,
            status=order.status,
            product_name=order.product_name,
            masked_address=order.masked_address,
        )


class MockLogisticsTool:
    def __init__(self, data: MockAfterSalesData) -> None:
        self.data = data

    def lookup(self, order_no: str, scope: DataScope) -> dict[str, str | bool]:
        order = MockOrderTool(self.data).lookup(order_no, scope)
        if not order.found:
            return {"found": False, "orderNo": order_no}
        source = self.data.orders[order_no]
        return {"found": True, "orderNo": order_no, "trackingNo": source.tracking_no, "status": "运输中"}


class MockTicketTool:
    def __init__(self, data: MockAfterSalesData) -> None:
        self.data = data

    def preview(self, draft: TicketDraft, customer_id: UUID) -> dict[str, object]:
        # 这里只生成预览，不改变订单、退款或工单状态。
        return {
            "action": "create_ticket",
            "customerId": str(customer_id),
            "category": draft.category,
            "summary": draft.summary,
            "priority": draft.priority,
            "riskLevel": draft.risk_level,
            "requiresApproval": draft.risk_level == "high",
        }

    def execute_simulation(self, draft: TicketDraft, customer_id: UUID, action_id: str) -> MockTicket:
        if draft.risk_level == "high":
            raise ToolPolicyError("高风险工单必须先审批")
        ticket_no = f"TK-{action_id[:8].upper()}"
        ticket = MockTicket(ticket_no, customer_id, draft.category, "open", draft.summary)
        self.data.tickets[ticket_no] = ticket
        return ticket
