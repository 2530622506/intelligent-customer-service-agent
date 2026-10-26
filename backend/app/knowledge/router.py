from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.graph.neo4j import Neo4jGraph
from app.knowledge.schemas import EntityCreate, EntityView, RelationCreate, RelationView
from app.models import GraphEntity, GraphRelation

router = APIRouter(prefix="/knowledge", tags=["knowledge-graph"])
logger = getLogger(__name__)


def require_knowledge_write(principal: AuthPrincipal) -> None:
    if not principal.can("knowledge:write"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有知识图谱写权限")


@router.get("/entities", response_model=list[EntityView])
async def list_entities(
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[EntityView]:
    rows = await session.scalars(select(GraphEntity).order_by(GraphEntity.updated_at.desc()))
    return [
        EntityView(id=str(row.id), name=row.name, entity_type=row.entity_type, status=row.status, description=row.description)
        for row in rows
    ]


@router.post("/entities", response_model=EntityView, dependencies=[Depends(require_csrf)])
async def create_entity(
    payload: EntityCreate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EntityView:
    require_knowledge_write(principal)
    entity = GraphEntity(name=payload.name, entity_type=payload.entity_type, description=payload.description, status="candidate")
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    try:
        graph = Neo4jGraph(settings)
        await graph.ensure_constraints()
        await graph.close()
    except Exception as error:  # noqa: BLE001
        # PostgreSQL 是治理事实源，图数据库短暂不可用不丢失候选实体。
        logger.warning("Neo4j 投影暂不可用，保留 PostgreSQL 候选实体：%s", error)
    return EntityView(id=str(entity.id), name=entity.name, entity_type=entity.entity_type, status=entity.status, description=entity.description)


@router.post("/entities/{entity_id}/publish", response_model=EntityView, dependencies=[Depends(require_csrf)])
async def publish_entity(
    entity_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EntityView:
    require_knowledge_write(principal)
    entity = await session.get(GraphEntity, entity_id, with_for_update=True)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    entity.status = "published"
    entity.version += 1
    await session.commit()
    return EntityView(id=str(entity.id), name=entity.name, entity_type=entity.entity_type, status=entity.status, description=entity.description)


@router.get("/relations", response_model=list[RelationView])
async def list_relations(
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RelationView]:
    rows = await session.scalars(select(GraphRelation).order_by(GraphRelation.updated_at.desc()))
    return [
        RelationView(id=str(row.id), source_entity_id=str(row.source_entity_id), target_entity_id=str(row.target_entity_id), relation_type=row.relation_type, status=row.status)
        for row in rows
    ]


@router.post("/relations", response_model=RelationView, dependencies=[Depends(require_csrf)])
async def create_relation(
    payload: RelationCreate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RelationView:
    require_knowledge_write(principal)
    for entity_id in (payload.source_entity_id, payload.target_entity_id):
        if not await session.get(GraphEntity, entity_id):
            raise HTTPException(status_code=404, detail="关系引用的实体不存在")
    relation = GraphRelation(
        source_entity_id=payload.source_entity_id,
        target_entity_id=payload.target_entity_id,
        relation_type=payload.relation_type,
        status="candidate",
    )
    session.add(relation)
    await session.commit()
    await session.refresh(relation)
    return RelationView(id=str(relation.id), source_entity_id=str(relation.source_entity_id), target_entity_id=str(relation.target_entity_id), relation_type=relation.relation_type, status=relation.status)
