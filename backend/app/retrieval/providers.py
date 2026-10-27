from __future__ import annotations

from typing import Any, cast

import httpx

from app.core.config import Settings
from app.retrieval.types import RerankResult


class ProviderError(RuntimeError):
    """Embedding / Reranker API 调用失败。"""


class DashScopeEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def embed(self, texts: list[str], text_type: str) -> list[list[float]]:
        if not self.settings.embedding_api_key:
            raise ProviderError("未配置 EMBEDDING_API_KEY")
        if text_type not in {"query", "document"}:
            raise ValueError("text_type 必须是 query 或 document")
        base_url = self.settings.embedding_base_url.rstrip("/")
        compatible = base_url.endswith("/v1")
        if compatible:
            response = await self._post(
                f"{base_url}/embeddings",
                {"model": self.settings.embedding_model, "input": texts},
            )
            items = response.get("data", [])
        else:
            response = await self._post(
                base_url,
                {
                    "model": self.settings.embedding_model,
                    "input": {"texts": texts, "text_type": text_type},
                    "parameters": {"dimension": self.settings.embedding_dimension, "output_type": "dense"},
                },
            )
            items = response.get("output", {}).get("embeddings", [])
        vectors = [item.get("embedding") for item in items]
        if len(vectors) != len(texts) or any(not isinstance(vector, list) for vector in vectors):
            raise ProviderError("Embedding 返回数量或格式不正确")
        return vectors

    async def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=30,
            trust_env=self.settings.model_http_trust_env,
        ) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {self.settings.embedding_api_key}"},
                json=body,
            )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


class DashScopeRerankerProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult] | None:
        if not self.settings.rerank_enabled or not self.settings.rerank_api_key:
            return None
        limited = documents[: self.settings.rerank_max_documents]
        limited = [document[: self.settings.rerank_max_document_chars] for document in limited]
        response = await self._post(
            {
                "model": self.settings.rerank_model,
                "input": {"query": query, "documents": limited},
                "parameters": {"return_documents": False, "top_n": min(top_n, len(limited))},
            }
        )
        results = response.get("output", {}).get("results", [])
        if not results:
            return None
        return [RerankResult(index=int(item["index"]), score=float(item["relevance_score"])) for item in results]

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        base_url = self.settings.rerank_base_url.rstrip("/")
        endpoint = (
            base_url
            if base_url.endswith("/text-rerank")
            else f"{base_url}/api/v1/services/rerank/text-rerank/text-rerank"
        )
        async with httpx.AsyncClient(
            timeout=15,
            trust_env=self.settings.model_http_trust_env,
        ) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.settings.rerank_api_key}"},
                json=body,
            )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
