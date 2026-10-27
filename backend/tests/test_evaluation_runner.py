from typing import Any
from uuid import uuid4

import pytest

from app.agent.runtime import ControlledAgentRuntime
from app.evaluation.runner import OfflineEvaluationRunner


def test_evaluation_runtime_has_deterministic_intent() -> None:
    result = ControlledAgentRuntime().invoke("订单物流到哪里了？", str(uuid4()))
    assert result["intent"] == "order_logistics"


@pytest.mark.asyncio
async def test_runner_rejects_missing_dataset() -> None:
    # Runner 在真实数据库测试中覆盖；此处只验证明确错误契约类型。
    class MissingSession:
        async def get(self, *_args: Any) -> None:
            return None

    with pytest.raises(ValueError, match="评测数据集不存在"):
        await OfflineEvaluationRunner(MissingSession()).run(uuid4())  # type: ignore[arg-type]
