from __future__ import annotations

from typing import Any
from uuid import UUID

from neo4j import AsyncGraphDatabase

from app.core.config import Settings


class Neo4jGraph:
    def __init__(self, settings: Settings) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def close(self) -> None:
        await self._driver.close()

    async def ensure_constraints(self) -> None:
        async with self._driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT graph_entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
            )

    async def upsert_entity(
        self,
        entity_id: UUID,
        name: str,
        entity_type: str,
        document_id: UUID,
        version_id: UUID,
        chunk_id: UUID | None,
    ) -> None:
        query = """
        MERGE (entity:Entity {id: $entity_id})
        SET entity.name = $name, entity.entity_type = $entity_type,
            entity.status = 'candidate'
        MERGE (document:Document {id: $document_id})
        MERGE (entity)-[source:MENTIONED_IN {version_id: $version_id}]->(document)
        SET source.chunk_id = $chunk_id
        """
        async with self._driver.session() as session:
            await session.run(
                query,
                entity_id=str(entity_id),
                name=name,
                entity_type=entity_type,
                document_id=str(document_id),
                version_id=str(version_id),
                chunk_id=str(chunk_id) if chunk_id else None,
            )

    async def upsert_relation(
        self,
        relation_id: UUID,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relation_type: str,
    ) -> None:
        query = """
        MATCH (source:Entity {id: $source_id}), (target:Entity {id: $target_id})
        MERGE (source)-[relation:RELATED {id: $relation_id}]->(target)
        SET relation.relation_type = $relation_type,
            relation.status = 'candidate'
        """
        async with self._driver.session() as session:
            await session.run(
                query,
                relation_id=str(relation_id),
                source_id=str(source_entity_id),
                target_id=str(target_entity_id),
                relation_type=relation_type,
            )

    async def find_entity(self, name: str) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (entity:Entity {name: $name}) RETURN entity.id AS id, entity.entity_type AS entity_type",
                name=name,
            )
            return [dict(record) async for record in result]
