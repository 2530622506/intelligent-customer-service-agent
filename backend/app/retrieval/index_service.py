from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import KnowledgeChunk, KnowledgeDocumentVersion
from app.retrieval.chunking import split_markdown
from app.retrieval.milvus import MilvusIndex
from app.retrieval.providers import DashScopeEmbeddingProvider


class KnowledgeIndexService:
    """从 PostgreSQL 正文版本重建 chunk 和 Milvus 索引。"""

    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        self.settings = settings
        self.session = session
        self.embedding = DashScopeEmbeddingProvider(settings)
        self.milvus = MilvusIndex(settings)

    async def rebuild_version(self, version_id: UUID) -> int:
        version = await self.session.get(KnowledgeDocumentVersion, version_id)
        if version is None:
            raise ValueError(f"正文版本不存在：{version_id}")

        drafts = split_markdown(
            version.content_markdown,
            version.document_id,
            version.id,
        )
        await self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.version_id == version.id))
        chunks = [
            KnowledgeChunk(
                id=draft.chunk_id,
                document_id=draft.document_id,
                version_id=draft.version_id,
                chunk_index=draft.chunk_index,
                content=draft.content,
                section_path=draft.section_path,
                parent_chunk_id=draft.parent_chunk_id,
                chunking_version=draft.chunking_version,
                index_status="pending",
            )
            for draft in drafts
        ]
        self.session.add_all(chunks)
        await self.session.flush()

        vectors = await self.embedding.embed(
            [draft.content for draft in drafts],
            text_type="document",
        )
        rows = [draft.as_milvus_row(vector) for draft, vector in zip(drafts, vectors, strict=True)]
        self.milvus.insert(rows)
        for chunk in chunks:
            chunk.index_status = "indexed"
        await self.session.commit()
        return len(chunks)
