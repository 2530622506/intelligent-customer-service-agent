from uuid import UUID

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entity_type: str = Field(min_length=1, max_length=80)
    description: str | None = None


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    entity_type: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None


class EntityMerge(BaseModel):
    target_entity_id: UUID


class RelationCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str = Field(min_length=1, max_length=120)


class RelationUpdate(BaseModel):
    relation_type: str = Field(min_length=1, max_length=120)


class EntityView(BaseModel):
    id: str
    name: str
    entity_type: str
    status: str
    description: str | None


class RelationView(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    status: str


class EntitySourceView(BaseModel):
    id: str
    document_id: str
    version_id: str
    chunk_id: str | None
