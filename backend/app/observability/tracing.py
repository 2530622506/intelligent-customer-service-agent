from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


class AgentTracer:
    """可选 Langfuse Trace；未配置凭据时降级为本地结构化日志。"""

    def __init__(self, settings: Settings) -> None:
        self._client: Any | None = None
        if settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_base_url,
                )
            except Exception as error:  # noqa: BLE001
                logger.warning("Langfuse 初始化失败，降级本地 Trace：%s", type(error).__name__)

    @contextmanager
    def run(self, run_id: str, question: str) -> Iterator[dict[str, Any]]:
        # Trace 中只放问题长度，不上传原始客户内容，避免敏感字段泄露。
        metadata = {"run_id": run_id, "question_length": len(question)}
        if not self._client:
            logger.info("agent_trace local=%s", metadata)
            yield metadata
            return
        with self._client.start_as_current_observation(
            as_type="span", name="customer-service-agent", input=metadata
        ) as observation:
            try:
                yield metadata
            finally:
                observation.update(output={"run_id": run_id})
                self._client.flush()
