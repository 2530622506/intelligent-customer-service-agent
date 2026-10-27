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
from app.knowledge.schemas import (
    EntityCreate,
    EntityMerge,
    EntitySourceView,
    EntityUpdate,
    EntityView,
    RelationCreate,
    RelationUpdate,
    RelationView,
)
from app.models import GraphChange, GraphEntity, GraphEntitySource, GraphRelation

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
    if entity.status in {"deleted", "merged"}:
        raise HTTPException(status_code=409, detail="实体当前状态不可发布")
    entity.status = "published"
    entity.version += 1
    await session.commit()
    return EntityView(id=str(entity.id), name=entity.name, entity_type=entity.entity_type, status=entity.status, description=entity.description)


@router.patch("/entities/{entity_id}", response_model=EntityView, dependencies=[Depends(require_csrf)])
async def update_entity(
    entity_id: UUID,
    payload: EntityUpdate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EntityView:
    require_knowledge_write(principal)
    entity = await session.get(GraphEntity, entity_id, with_for_update=True)
    if not entity or entity.status in {"deleted", "merged"}:
        raise HTTPException(status_code=404, detail="实体不存在")
    before = {"name": entity.name, "entityType": entity.entity_type, "description": entity.description}
    if payload.name is not None:
        entity.name = payload.name
    if payload.entity_type is not None:
        entity.entity_type = payload.entity_type
    if payload.description is not None:
        entity.description = payload.description
    entity.status = "candidate"
    entity.version += 1
    session.add(
        GraphChange(
            actor_id=principal.user_id,
            entity_id=entity.id,
            operation="update",
            before_json=before,
            after_json={"name": entity.name, "entityType": entity.entity_type, "description": entity.description},
        )
    )
    await session.commit()
    return EntityView(id=str(entity.id), name=entity.name, entity_type=entity.entity_type, status=entity.status, description=entity.description)


@router.post("/entities/{entity_id}/merge", response_model=EntityView, dependencies=[Depends(require_csrf)])
async def merge_entity(
    entity_id: UUID,
    payload: EntityMerge,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EntityView:
    require_knowledge_write(principal)
    if entity_id == payload.target_entity_id:
        raise HTTPException(status_code=400, detail="实体不能合并到自身")
    source = await session.get(GraphEntity, entity_id, with_for_update=True)
    target = await session.get(GraphEntity, payload.target_entity_id, with_for_update=True)
    if not source or source.status in {"deleted", "merged"} or not target or target.status == "deleted":
        raise HTTPException(status_code=404, detail="实体不存在")
    relation_rows = list(
        await session.scalars(
            select(GraphRelation).where(
                (GraphRelation.source_entity_id == source.id) | (GraphRelation.target_entity_id == source.id)
            )
        )
    )
    # 合并时把源实体参与的关系迁移到目标实体；自环关系标记删除，避免产生无意义边。
    for relation in relation_rows:
        before = {
            "sourceEntityId": str(relation.source_entity_id),
            "targetEntityId": str(relation.target_entity_id),
            "status": relation.status,
        }
        if relation.source_entity_id == source.id:
            relation.source_entity_id = target.id
        if relation.target_entity_id == source.id:
            relation.target_entity_id = target.id
        if relation.source_entity_id == relation.target_entity_id:
            relation.status = "deleted"
        session.add(
            GraphChange(
                actor_id=principal.user_id,
                relation_id=relation.id,
                operation="merge_relation",
                before_json=before,
                after_json={
                    "sourceEntityId": str(relation.source_entity_id),
                    "targetEntityId": str(relation.target_entity_id),
                    "status": relation.status,
                },
            )
        )
    source.status = "merged"
    source.version += 1
    session.add(
        GraphChange(
            actor_id=principal.user_id,
            entity_id=source.id,
            operation="merge",
            before_json={"status": "candidate"},
            after_json={"status": "merged", "targetEntityId": str(target.id)},
        )
    )
    await session.commit()
    return EntityView(id=str(target.id), name=target.name, entity_type=target.entity_type, status=target.status, description=target.description)


@router.delete("/entities/{entity_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_entity(
    entity_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    require_knowledge_write(principal)
    entity = await session.get(GraphEntity, entity_id, with_for_update=True)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    if entity.status in {"deleted", "merged"}:
        raise HTTPException(status_code=409, detail="实体当前状态不可删除")
    previous_status = entity.status
    # 图谱删除采用软删除，保留来源和审计记录，避免历史引用失去可追溯性。
    entity.status = "deleted"
    entity.version += 1
    session.add(
        GraphChange(
            actor_id=principal.user_id,
            entity_id=entity.id,
            operation="delete",
            before_json={"status": previous_status},
            after_json={"status": "deleted"},
        )
    )
    related_relations = list(
        await session.scalars(
            select(GraphRelation).where(
                (GraphRelation.source_entity_id == entity.id) | (GraphRelation.target_entity_id == entity.id),
                GraphRelation.status != "deleted",
            )
        )
    )
    for relation in related_relations:
        previous_relation_status = relation.status
        # 删除实体时同步删除关联边，避免留下无法解释的悬挂关系。
        relation.status = "deleted"
        relation.version += 1
        session.add(
            GraphChange(
                actor_id=principal.user_id,
                relation_id=relation.id,
                operation="delete_by_entity",
                before_json={"status": previous_relation_status},
                after_json={"status": "deleted", "entityId": str(entity.id)},
            )
        )
    await session.commit()


@router.get("/entities/{entity_id}/sources", response_model=list[EntitySourceView])
async def list_entity_sources(
    entity_id: UUID,
    _: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[EntitySourceView]:
    if not await session.get(GraphEntity, entity_id):
        raise HTTPException(status_code=404, detail="实体不存在")
    rows = await session.scalars(select(GraphEntitySource).where(GraphEntitySource.entity_id == entity_id))
    return [
        EntitySourceView(
            id=str(row.id),
            document_id=str(row.document_id),
            version_id=str(row.version_id),
            chunk_id=str(row.chunk_id) if row.chunk_id else None,
        )
        for row in rows
    ]


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


@router.post("/relations/{relation_id}/publish", response_model=RelationView, dependencies=[Depends(require_csrf)])
async def publish_relation(
    relation_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RelationView:
    require_knowledge_write(principal)
    relation = await session.get(GraphRelation, relation_id, with_for_update=True)
    if not relation:
        raise HTTPException(status_code=404, detail="关系不存在")
    if relation.status == "deleted":
        raise HTTPException(status_code=409, detail="关系当前状态不可发布")
    source = await session.get(GraphEntity, relation.source_entity_id)
    target = await session.get(GraphEntity, relation.target_entity_id)
    if not source or not target or source.status != "published" or target.status != "published":
        raise HTTPException(status_code=409, detail="关系两端实体必须先发布")
    relation.status = "published"
    relation.version += 1
    await session.commit()
    try:
        graph = Neo4jGraph(settings)
        await graph.upsert_relation(relation.id, relation.source_entity_id, relation.target_entity_id, relation.relation_type)
        await graph.close()
    except Exception as error:  # noqa: BLE001
        logger.warning("Neo4j 关系投影暂不可用，保留 PostgreSQL 发布状态：%s", error)
    return RelationView(id=str(relation.id), source_entity_id=str(relation.source_entity_id), target_entity_id=str(relation.target_entity_id), relation_type=relation.relation_type, status=relation.status)


@router.patch("/relations/{relation_id}", response_model=RelationView, dependencies=[Depends(require_csrf)])
async def update_relation(
    relation_id: UUID,
    payload: RelationUpdate,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RelationView:
    require_knowledge_write(principal)
    relation = await session.get(GraphRelation, relation_id, with_for_update=True)
    if not relation or relation.status == "deleted":
        raise HTTPException(status_code=404, detail="关系不存在")
    before = {"relationType": relation.relation_type, "status": relation.status}
    relation.relation_type = payload.relation_type
    relation.status = "candidate"
    relation.version += 1
    session.add(
        GraphChange(
            actor_id=principal.user_id,
            relation_id=relation.id,
            operation="update",
            before_json=before,
            after_json={"relationType": relation.relation_type, "status": relation.status},
        )
    )
    await session.commit()
    return RelationView(id=str(relation.id), source_entity_id=str(relation.source_entity_id), target_entity_id=str(relation.target_entity_id), relation_type=relation.relation_type, status=relation.status)


@router.delete("/relations/{relation_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_relation(
    relation_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    require_knowledge_write(principal)
    relation = await session.get(GraphRelation, relation_id, with_for_update=True)
    if not relation:
        raise HTTPException(status_code=404, detail="关系不存在")
    previous_status = relation.status
    # 关系也只做软删除，Neo4j 投影失败时仍以 PostgreSQL 状态作为事实源。
    relation.status = "deleted"
    relation.version += 1
    session.add(
        GraphChange(
            actor_id=principal.user_id,
            relation_id=relation.id,
            operation="delete",
            before_json={"status": previous_status},
            after_json={"status": "deleted"},
        )
    )
    await session.commit()
