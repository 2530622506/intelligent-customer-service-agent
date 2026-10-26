"""执行一个评测数据集并把结果写入 PostgreSQL。"""

import argparse
import asyncio
from uuid import UUID

from app.db.base import session_factory
from app.evaluation.runner import OfflineEvaluationRunner


async def main(dataset_id: UUID) -> None:
    async with session_factory() as session:
        run = await OfflineEvaluationRunner(session).run(dataset_id)
        print({"runId": str(run.id), "status": run.status, "summary": run.summary})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_id", type=UUID)
    args = parser.parse_args()
    asyncio.run(main(args.dataset_id))
