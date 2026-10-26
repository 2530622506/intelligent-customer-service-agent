from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ChunkDraft:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    content: str
    chunk_index: int
    section_path: str | None
    parent_chunk_id: UUID | None
    chunking_version: str

    def as_milvus_row(self, dense_vector: list[float]) -> dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "version_id": str(self.version_id),
            "content": self.content,
            "section_path": self.section_path or "",
            "is_published": True,
            "owner_id": "",
            "team_id": "",
            "dense_vector": dense_vector,
        }


def split_markdown(
    content: str,
    document_id: UUID,
    version_id: UUID,
    max_chars: int = 1200,
) -> list[ChunkDraft]:
    """按标题和段落生成可追溯 chunk；首版不做模型摘要，避免丢失原文证据。"""
    sections: list[tuple[str | None, str]] = []
    heading: str | None = None
    buffer: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            if buffer:
                sections.append((heading, "\n".join(buffer).strip()))
                buffer = []
            heading = line.lstrip("#").strip() or None
        elif line:
            buffer.append(line)
    if buffer:
        sections.append((heading, "\n".join(buffer).strip()))

    chunks: list[ChunkDraft] = []
    index = 0
    for section_path, text in sections:
        if not text:
            continue
        parent_id = uuid4()
        parent = ChunkDraft(
            chunk_id=parent_id,
            document_id=document_id,
            version_id=version_id,
            content=text,
            chunk_index=index,
            section_path=section_path,
            parent_chunk_id=None,
            chunking_version="markdown-parent-child-v1",
        )
        chunks.append(parent)
        index += 1
        for offset in range(0, len(text), max_chars):
            child = text[offset : offset + max_chars].strip()
            if not child:
                continue
            chunks.append(
                ChunkDraft(
                    chunk_id=uuid4(),
                    document_id=document_id,
                    version_id=version_id,
                    content=child,
                    chunk_index=index,
                    section_path=section_path,
                    parent_chunk_id=parent_id,
                    chunking_version="markdown-parent-child-v1",
                )
            )
            index += 1
    return chunks
