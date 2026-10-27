from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.document.service import DocumentPipelineService
from app.models import KnowledgeDocument, KnowledgeDocumentVersion, ParseTask
from app.retrieval.index_service import KnowledgeIndexService

router = APIRouter(prefix="/knowledge/documents", tags=["knowledge"])


class DocumentVersionView(BaseModel):
    id: str
    version_number: int
    status: str
    parser_version: str
    content_hash: str


class DocumentView(BaseModel):
    id: str
    title: str
    status: str
    current_version_id: str | None
    versions: list[DocumentVersionView]


def require_knowledge_write(principal: AuthPrincipal) -> None:
    if not principal.can("knowledge:write"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有知识库写权限")


@router.post("/upload", dependencies=[Depends(require_csrf)])
async def upload_document(
    upload: Annotated[UploadFile, File()],
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    require_knowledge_write(principal)
    task = await DocumentPipelineService(settings, session).submit(upload)
    return {"taskId": str(task.id), "documentId": str(task.document_id), "status": task.status}


@router.get("/tasks/{task_id}")
async def get_parse_task(
    task_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    require_knowledge_write(principal)
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


@router.get("", response_model=list[DocumentView])
async def list_documents(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentView]:
    require_knowledge_write(principal)
    documents = await session.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.deleted.is_(False))
        .order_by(KnowledgeDocument.updated_at.desc())
    )
    result: list[DocumentView] = []
    for document in documents:
        versions = await session.scalars(
            select(KnowledgeDocumentVersion)
            .where(KnowledgeDocumentVersion.document_id == document.id)
            .order_by(KnowledgeDocumentVersion.version_number.desc())
        )
        result.append(
            DocumentView(
                id=str(document.id),
                title=document.title,
                status=document.status,
                current_version_id=str(document.current_version_id) if document.current_version_id else None,
                versions=[
                    DocumentVersionView(
                        id=str(version.id),
                        version_number=version.version_number,
                        status=version.status,
                        parser_version=version.parser_version,
                        content_hash=version.content_hash,
                    )
                    for version in versions
                ],
            )
        )
    return result


@router.post("/{document_id}/publish", response_model=DocumentView, dependencies=[Depends(require_csrf)])
async def publish_document(
    document_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentView:
    require_knowledge_write(principal)
    document = await session.get(KnowledgeDocument, document_id, with_for_update=True)
    if not document or document.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识文档不存在")
    version = await session.scalar(
        select(KnowledgeDocumentVersion)
        .where(KnowledgeDocumentVersion.document_id == document.id)
        .order_by(KnowledgeDocumentVersion.version_number.desc())
        .limit(1)
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="文档尚无可发布版本")
    try:
        # 只有索引成功后才切换 published，避免 PostgreSQL 状态与 Milvus 不一致。
        await KnowledgeIndexService(settings, session).rebuild_version(version.id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="文档索引失败，暂不能发布") from error
    previous_versions = await session.scalars(
        select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == document.id,
            KnowledgeDocumentVersion.id != version.id,
        )
    )
    for previous in previous_versions:
        previous.status = "archived"
    version.status = "published"
    document.current_version_id = version.id
    document.status = "published"
    await session.commit()
    versions = await session.scalars(
        select(KnowledgeDocumentVersion)
        .where(KnowledgeDocumentVersion.document_id == document.id)
        .order_by(KnowledgeDocumentVersion.version_number.desc())
    )
    return DocumentView(
        id=str(document.id),
        title=document.title,
        status=document.status,
        current_version_id=str(document.current_version_id),
        versions=[
            DocumentVersionView(
                id=str(item.id),
                version_number=item.version_number,
                status=item.status,
                parser_version=item.parser_version,
                content_hash=item.content_hash,
            )
            for item in versions
        ],
    )
