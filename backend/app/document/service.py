from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from typing import cast
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import session_factory
from app.document.mineru import MineruClient, MineruError, ParsedDocument
from app.models import KnowledgeDocument, KnowledgeDocumentVersion, ParseTask
from app.mq.rabbit import RabbitPublisher
from app.storage.rustfs import RustFSStorage

SUPPORTED_LOCAL = {"md", "txt"}


class DocumentPipelineService:
    """上传、解析和正文版本落库；索引写入由后续 T-05 负责。"""

    def __init__(self, settings: Settings, session: AsyncSession | None) -> None:
        self.settings = settings
        self.session = session
        self.storage = RustFSStorage(settings)
        self.mineru = MineruClient(settings)
        self.rabbit = RabbitPublisher(settings)

    async def submit(self, upload: UploadFile) -> ParseTask:
        if self.session is None:
            raise RuntimeError("提交文档必须提供请求数据库 session")
        filename = PurePosixPath(upload.filename or "document").name
        content_type = upload.content_type or "application/octet-stream"
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail="文件不能为空")
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="单文件不能超过 50 MB")

        stored = await self.storage.put_bytes(data, filename, content_type)
        document = KnowledgeDocument(title=filename, status="draft")
        self.session.add(document)
        await self.session.flush()
        task = ParseTask(
            document_id=document.id,
            source_object_key=stored.key,
            status="queued",
        )
        self.session.add(task)
        await self.session.commit()
        try:
            await self.rabbit.publish_parse(str(task.id))
        except Exception as error:  # noqa: BLE001  # 投递失败必须落 retryable 状态。
            task.status = "retryable"
            task.error_message = f"任务投递失败：{error}"
            await self.session.commit()
        return task

    async def process(self, task_id: UUID) -> None:
        async with session_factory() as session:
            claimed = cast(CursorResult[tuple[object, ...]], await session.execute(
                update(ParseTask)
                .where(ParseTask.id == task_id, ParseTask.status.in_(("queued", "retryable")))
                .values(status="processing", attempts=ParseTask.attempts + 1)
            ))
            if claimed.rowcount != 1:
                return
            await session.commit()
            task = await session.get(ParseTask, task_id)
            if not task:
                return
            try:
                data = await self.storage.get_bytes(task.source_object_key)
                parsed = await self._parse(task.source_object_key, data)
                version_number = await session.scalar(
                    select(func.coalesce(func.max(KnowledgeDocumentVersion.version_number), 0)).where(
                        KnowledgeDocumentVersion.document_id == task.document_id
                    )
                )
                version = KnowledgeDocumentVersion(
                    document_id=task.document_id,
                    version_number=int(version_number or 0) + 1,
                    content_markdown=parsed.markdown,
                    content_structure=parsed.structure,
                    source_object_key=task.source_object_key,
                    content_hash=hashlib.sha256(parsed.markdown.encode()).hexdigest(),
                    parser_version=parsed.parser_version,
                    status="draft",
                )
                session.add(version)
                task.status = "succeeded"
                task.error_message = None
                await session.commit()
            except Exception as error:  # noqa: BLE001  # 任务失败必须持久化重试状态。
                task.status = "retryable" if task.attempts < 3 else "failed"
                task.error_message = str(error)
                await session.commit()

    async def _parse(self, object_key: str, data: bytes) -> ParsedDocument:
        suffix = PurePosixPath(object_key).suffix.lower().lstrip(".")
        if suffix in SUPPORTED_LOCAL:
            text = data.decode("utf-8", errors="replace").strip()
            if not text:
                raise MineruError("文本文件为空")
            return ParsedDocument(
                markdown=text,
                structure={"source": "plain-text"},
                parser_version="plain-text-v1",
            )
        return await self.mineru.parse(PurePosixPath(object_key).name, data)
