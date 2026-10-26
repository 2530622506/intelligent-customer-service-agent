from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.db.base import get_db
from app.models import EvalCase, EvalDataset, EvalRun, EvalScore

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class CaseCreate(BaseModel):
    case_key: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=4000)
    expected_output: dict[str, object] = Field(default_factory=dict)


@router.get("/datasets")
async def list_datasets(
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    rows = await session.scalars(select(EvalDataset).order_by(EvalDataset.updated_at.desc()))
    return [{"id": str(row.id), "name": row.name, "description": row.description, "status": row.status} for row in rows]


@router.post("/datasets", dependencies=[Depends(require_csrf)])
async def create_dataset(
    payload: DatasetCreate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    if not principal.can("evaluation:run"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有评测权限")
    dataset = EvalDataset(name=payload.name, description=payload.description, status="draft")
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)
    return {"id": str(dataset.id), "name": dataset.name, "status": dataset.status}


@router.post("/datasets/{dataset_id}/cases", dependencies=[Depends(require_csrf)])
async def add_case(
    dataset_id: UUID,
    payload: CaseCreate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    if not principal.can("evaluation:run"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有评测权限")
    if not await session.get(EvalDataset, dataset_id):
        raise HTTPException(status_code=404, detail="评测数据集不存在")
    case = EvalCase(dataset_id=dataset_id, case_key=payload.case_key, question=payload.question, expected_output=payload.expected_output)
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return {"id": str(case.id), "caseKey": case.case_key, "question": case.question, "enabled": case.enabled}


@router.post("/datasets/{dataset_id}/runs", dependencies=[Depends(require_csrf)])
async def create_run(
    dataset_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    if not principal.can("evaluation:run"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有评测权限")
    if not await session.get(EvalDataset, dataset_id):
        raise HTTPException(status_code=404, detail="评测数据集不存在")
    run = EvalRun(dataset_id=dataset_id, model_name="qwen3.7-flash", status="queued", summary={})
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return {"id": str(run.id), "datasetId": str(dataset_id), "status": run.status, "model": run.model_name}


@router.get("/runs/{run_id}/scores")
async def list_scores(
    run_id: UUID,
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    rows = await session.scalars(select(EvalScore).where(EvalScore.run_id == run_id))
    return [{"metric": row.metric, "value": row.value, "comment": row.comment} for row in rows]
