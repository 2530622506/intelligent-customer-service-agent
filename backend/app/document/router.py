from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.document.service import DocumentPipelineService
from app.models import ParseTask

router = APIRouter(prefix="/knowledge/documents", tags=["knowledge"])


@router.post("/upload", dependencies=[Depends(require_csrf)])
async def upload_document(
    upload: Annotated[UploadFile, File()],
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    task = await DocumentPipelineService(settings, session).submit(upload)
    return {"taskId": str(task.id), "documentId": str(task.document_id), "status": task.status}


@router.get("/tasks/{task_id}")
async def get_parse_task(
    task_id: UUID,
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    task = await session.scalar(select(ParseTask).where(ParseTask.id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析任务不存在")
    return {
        "taskId": str(task.id),
        "documentId": str(task.document_id),
        "status": task.status,
        "attempts": task.attempts,
        "error": task.error_message,
    }
