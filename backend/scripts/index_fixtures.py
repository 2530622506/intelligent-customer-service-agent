"""将合成知识资料导入 PostgreSQL，并重建 Milvus Dense + BM25 索引。"""

import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import session_factory
from app.models import KnowledgeDocument, KnowledgeDocumentVersion
from app.retrieval.index_service import KnowledgeIndexService


async def main() -> None:
    root = Path(__file__).resolve().parents[2] / "fixtures" / "knowledge"
    async with session_factory() as session:
        for path in sorted(root.glob("*.md")):
            content = path.read_text(encoding="utf-8").strip()
            document = await session.scalar(
                select(KnowledgeDocument).where(KnowledgeDocument.title == path.name)
            )
            if document is None:
                document = KnowledgeDocument(title=path.name, status="published")
                session.add(document)
                await session.flush()
            version = await session.scalar(
                select(KnowledgeDocumentVersion)
                .where(KnowledgeDocumentVersion.document_id == document.id)
                .order_by(KnowledgeDocumentVersion.version_number.desc())
            )
            if version is None or version.content_hash != hashlib.sha256(content.encode()).hexdigest():
                version = KnowledgeDocumentVersion(
                    document_id=document.id,
                    version_number=(version.version_number + 1) if version else 1,
                    content_markdown=content,
                    content_structure={"source": "synthetic_fixture"},
                    source_object_key=f"fixtures/knowledge/{path.name}",
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    parser_version="fixture-v1",
                    status="published",
                )
                session.add(version)
                await session.flush()
            document.current_version_id = version.id
            document.status = "published"
            await session.commit()
            count = await KnowledgeIndexService(get_settings(), session).rebuild_version(version.id)
            print(f"indexed {path.name}: chunks={count}")


if __name__ == "__main__":
    asyncio.run(main())
