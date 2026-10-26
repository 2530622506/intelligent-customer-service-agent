from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import ControlledAgentRuntime
from app.models import EvalCase, EvalDataset, EvalRun, EvalScore


class OfflineEvaluationRunner:
    """首版离线评测执行器；先使用确定性指标，避免把质量门禁交给黑盒裁判。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self, dataset_id: UUID, model_name: str = "qwen3.7-flash", existing_run: EvalRun | None = None
    ) -> EvalRun:
        dataset = await self.session.get(EvalDataset, dataset_id)
        if not dataset:
            raise ValueError("评测数据集不存在")
        run = existing_run or EvalRun(dataset_id=dataset_id, model_name=model_name, status="running", summary={})
        if existing_run is None:
            self.session.add(run)
            await self.session.flush()
        else:
            run.status = "running"
        cases = await self.session.scalars(
            select(EvalCase).where(EvalCase.dataset_id == dataset_id, EvalCase.enabled.is_(True))
        )
        runtime = ControlledAgentRuntime()
        scores: list[EvalScore] = []
        for case in cases:
            output = runtime.invoke(case.question, f"eval-{run.id}-{case.id}")
            expected = case.expected_output
            expected_intent = expected.get("intent")
            actual_intent = output.get("intent")
            scores.append(
                EvalScore(
                    run_id=run.id,
                    case_id=case.id,
                    metric="intent_match",
                    value=1.0 if expected_intent is None or expected_intent == actual_intent else 0.0,
                    comment=f"expected={expected_intent}, actual={actual_intent}",
                )
            )
            scores.append(
                EvalScore(
                    run_id=run.id,
                    case_id=case.id,
                    metric="runtime_safety",
                    value=0.0 if output.get("error_code") == "PLAN_REJECTED" else 1.0,
                    comment=str(output.get("error_code") or "ok"),
                )
            )
        self.session.add_all(scores)
        run.status = "completed"
        run.summary = {"caseCount": len(scores) // 2, "scoreCount": len(scores), "model": model_name}
        await self.session.commit()
        await self.session.refresh(run)
        return run
