from uuid import uuid4

import pytest

from app.auth.policy import scope_for_roles
from app.auth.types import RoleCode
from app.business.mock_data import MockAfterSalesData
from app.business.schemas import TicketDraft
from app.business.sql_gateway import ReadOnlySQLGateway, SQLPolicyError
from app.business.tools import MockOrderTool, MockTicketTool, ToolPolicyError


def test_order_tool_enforces_self_scope() -> None:
    customer_id = uuid4()
    data = MockAfterSalesData(customer_id)
    scope = scope_for_roles(customer_id, frozenset({RoleCode.CUSTOMER}), ())

    assert MockOrderTool(data).lookup("CS202610270001", scope).found
    with pytest.raises(ToolPolicyError):
        MockOrderTool(data).lookup("CS202610270001", scope_for_roles(uuid4(), frozenset({RoleCode.CUSTOMER}), ()))


def test_high_risk_ticket_cannot_execute_without_approval() -> None:
    data = MockAfterSalesData(uuid4())
    draft = TicketDraft(category="refund", summary="模拟退款", risk_level="high")

    with pytest.raises(ToolPolicyError):
        MockTicketTool(data).execute_simulation(draft, uuid4(), "action-123")


def test_sql_gateway_rejects_write_unknown_table_and_large_limit() -> None:
    gateway = ReadOnlySQLGateway()
    gateway.validate("SELECT issue_type FROM after_sale_metrics LIMIT 10")
    for sql in (
        "DELETE FROM after_sale_metrics",
        "SELECT password_hash FROM app_user",
        "SELECT issue_type FROM after_sale_metrics LIMIT 1000",
    ):
        with pytest.raises(SQLPolicyError):
            gateway.validate(sql)
