from __future__ import annotations

from typing import Any

from pymilvus import (  # type: ignore[import-untyped]
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from app.core.config import Settings
from app.retrieval.types import SearchHit


class MilvusIndex:
    """Milvus Dense + BM25 索引；Reranker 在本适配器之外执行。"""

    collection_name = "customer_service_chunks"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token or None)

    def ensure_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("version_id", DataType.VARCHAR, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=65535, enable_analyzer=True)
        schema.add_field("section_path", DataType.VARCHAR, max_length=1024)
        schema.add_field("is_published", DataType.BOOL)
        schema.add_field("owner_id", DataType.VARCHAR, max_length=64)
        schema.add_field("team_id", DataType.VARCHAR, max_length=64)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=self.settings.embedding_dimension)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="content_bm25",
                input_field_names=["content"],
                output_field_names=["sparse_vector"],
                function_type=FunctionType.BM25,
            )
        )
        indexes = self.client.prepare_index_params()
        indexes.add_index("dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index(
            "sparse_vector",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            params={"bm25_k1": 1.2, "bm25_b": 0.75},
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=indexes,
            consistency_level="Strong",
        )

    def insert(self, rows: list[dict[str, Any]]) -> None:
        self.ensure_collection()
        self.client.insert(collection_name=self.collection_name, data=rows)
        self.client.flush(self.collection_name)

    def hybrid_search(self, query: str, vector: list[float], limit: int = 20) -> list[SearchHit]:
        self.ensure_collection()
        dense = AnnSearchRequest(
            data=[vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE"},
            limit=limit,
        )
        sparse = AnnSearchRequest(
            data=[query],
            anns_field="sparse_vector",
            param={"metric_type": "BM25"},
            limit=limit,
        )
        results = self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense, sparse],
            ranker=RRFRanker(k=60),
            limit=limit,
            output_fields=["document_id", "version_id", "content", "section_path"],
        )
        return [
            SearchHit(
                chunk_id=str(hit["chunk_id"]),
                document_id=hit["entity"]["document_id"],
                version_id=hit["entity"]["version_id"],
                content=hit["entity"]["content"],
                section_path=hit["entity"].get("section_path") or None,
                score=float(hit["distance"]),
                source="milvus_rrf",
            )
            for hit in results[0]
        ]
