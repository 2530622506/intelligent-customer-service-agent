from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MockOrder:
    order_no: str
    customer_id: UUID
    status: str
    product_name: str
    masked_address: str
    tracking_no: str


@dataclass(frozen=True)
class MockTicket:
    ticket_no: str
    customer_id: UUID
    category: str
    status: str
    summary: str


class MockAfterSalesData:
    """只用于本地演示和单元测试的合成数据，不代表真实业务数据。"""

    def __init__(self, customer_id: UUID) -> None:
        self.orders = {
            "CS202610270001": MockOrder(
                order_no="CS202610270001",
                customer_id=customer_id,
                status="shipping",
                product_name="云台摄像机 C1",
                masked_address="上海市浦东新区****",
                tracking_no="SF10000001",
            )
        }
        self.tickets: dict[str, MockTicket] = {}
