from __future__ import annotations

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.agent.contracts import AgentPlan
from app.core.config import Settings


class QwenSupervisorPlanner:
    """使用 Qwen 生成结构化计划；返回结果仍必须经过 Runtime policy guard。"""

    def __init__(self, settings: Settings) -> None:
        self.model = ChatOpenAI(
            api_key=SecretStr(settings.dashscope_api_key),
            model=settings.chat_model,
            temperature=0,
            timeout=settings.chat_timeout_seconds,
            max_retries=0,
            base_url=settings.chat_base_url,
            use_responses_api=False,
            http_client=httpx.Client(
                trust_env=settings.model_http_trust_env,
                timeout=settings.chat_timeout_seconds,
            ),
        ).with_structured_output(AgentPlan)

    def plan(self, question: str) -> AgentPlan:
        result = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        "你是电商售后 Supervisor。只能从 policy、troubleshooting、"
                        "order_logistics、analytics、ticket 中选择 Agent；只能输出结构化计划，"
                        "不要执行工具，不要编造订单事实。工具名只能从以下白名单选择："
                        "knowledge_search、graph_search、ticket_draft、order_lookup、"
                        "logistics_lookup、readonly_sql、approval_preview。"
                    )
                ),
                HumanMessage(content=question),
            ]
        )
        return AgentPlan.model_validate(result)
