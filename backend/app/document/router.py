from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.document.service import DocumentPipelineService

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
