"""把 fixtures/eval/golden.jsonl 导入 PostgreSQL，重复运行不会创建重复用例。"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.base import session_factory
from app.models import EvalCase, EvalDataset


async def main() -> None:
    source = Path(__file__).resolve().parents[2] / "fixtures" / "eval" / "golden.jsonl"
    dataset_name = "synthetic-after-sales-v1"
    async with session_factory() as session:
        dataset = await session.scalar(select(EvalDataset).where(EvalDataset.name == dataset_name))
        if dataset is None:
            dataset = EvalDataset(name=dataset_name, description="合成电商售后金标集", status="published")
            session.add(dataset)
            await session.flush()
        for line in source.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            exists = await session.scalar(
                select(EvalCase).where(EvalCase.dataset_id == dataset.id, EvalCase.case_key == item["caseKey"])
            )
            if exists is None:
                session.add(EvalCase(
                    dataset_id=dataset.id,
                    case_key=item["caseKey"],
                    question=item["question"],
                    expected_output=item["expectedOutput"],
                    enabled=True,
                ))
        await session.commit()
        print(dataset.id)


if __name__ == "__main__":
    asyncio.run(main())
