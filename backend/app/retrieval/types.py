from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    content: str
    section_path: str | None = None
    is_published: bool = True
    owner_id: UUID | None = None
    team_id: UUID | None = None

    def as_milvus_row(self, dense_vector: list[float]) -> dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "version_id": str(self.version_id),
            "content": self.content,
            "section_path": self.section_path or "",
            "is_published": self.is_published,
            "owner_id": str(self.owner_id) if self.owner_id else "",
            "team_id": str(self.team_id) if self.team_id else "",
            "dense_vector": dense_vector,
        }


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    version_id: str
    content: str
    section_path: str | None
    score: float
    source: str


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float
