from uuid import uuid4

from app.conversation.router import _order_result


def test_order_result_requires_order_number() -> None:
    answer, events = _order_result("我的订单什么时候到？", uuid4())

    assert "订单号" in answer
    assert events == []


def test_order_result_returns_synthetic_order() -> None:
    answer, events = _order_result("查询订单 CS202610270001 的物流", uuid4())

    assert "CS202610270001" in answer
    assert any(event_type == "tool_result" for event_type, _ in events)
