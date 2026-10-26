from typing import Literal

from pydantic import BaseModel, Field


class PolicyAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    grounded: bool = False


class TroubleshootingState(BaseModel):
    product_model: str | None = None
    symptom: str | None = None
    attempted_steps: list[str] = Field(default_factory=list)
    next_question: str | None = None
    escalation_required: bool = False


class OrderLookupResult(BaseModel):
    found: bool
    order_no: str
    status: str | None = None
    product_name: str | None = None
    masked_address: str | None = None


class AnalyticsQuery(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    sql: str = Field(min_length=1, max_length=4000)


class AnalyticsResult(BaseModel):
    accepted: bool
    rows: list[dict[str, object]] = Field(default_factory=list)
    reason: str | None = None


class TicketDraft(BaseModel):
    category: str
    summary: str
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    risk_level: Literal["normal", "high"] = "normal"
    action_preview: dict[str, object] = Field(default_factory=dict)
