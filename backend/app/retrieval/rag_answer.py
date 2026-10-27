from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import Settings
from app.retrieval.milvus import MilvusIndex
from app.retrieval.providers import (
    DashScopeEmbeddingProvider,
    DashScopeRerankerProvider,
    ProviderError,
)
from app.retrieval.types import SearchHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    citations: list[dict[str, str | float | None]]
    used_retrieval: bool


class PolicyRAGService:
    """政策问答垂直切片：检索证据优先，模型只负责基于证据组织答案。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedding = DashScopeEmbeddingProvider(settings)
        self.milvus = MilvusIndex(settings)
        self.reranker = DashScopeRerankerProvider(settings)

    async def answer(self, question: str) -> RAGAnswer | None:
        if not self.settings.embedding_api_key:
            return None
        try:
            vector = (await self.embedding.embed([question], "query"))[0]
            candidates = self.milvus.hybrid_search(question, vector, limit=10)
            if not candidates:
                return RAGAnswer("知识库中没有找到足够依据，建议转人工客服。", [], True)
            ranked = await self.reranker.rerank(question, [item.content for item in candidates], len(candidates))
            ordered = [candidates[item.index] for item in ranked] if ranked else candidates
            selected = ordered[:5]
            answer = await self._generate(question, selected)
            return RAGAnswer(answer, [self._citation(hit) for hit in selected], True)
        except (ProviderError, httpx.HTTPError, OSError, TimeoutError) as error:
            logger.warning("RAG provider unavailable, falling back to agent response: %s", type(error).__name__)
            return None
        except Exception as error:  # noqa: BLE001  # Milvus SDK 的异常类型跨版本不稳定，必须显式降级。
            logger.warning("RAG service unavailable, falling back to agent response: %s", type(error).__name__)
            return None

    async def _generate(self, question: str, hits: list[SearchHit]) -> str:
        context = "\n\n".join(
            f"[{index}] {hit.content}" for index, hit in enumerate(hits, 1)
        )
        model = ChatOpenAI(
            api_key=SecretStr(self.settings.dashscope_api_key),
            model=self.settings.chat_model,
            temperature=0,
            timeout=self.settings.chat_timeout_seconds,
            max_retries=1,
            base_url=self.settings.chat_base_url,
        )
        response = await model.ainvoke(
            [
                SystemMessage(
                    content="只能依据给定知识库证据回答。证据不足时明确说没有依据，不得编造政策。回答中引用 [n]。"
                ),
                HumanMessage(content=f"知识库证据：\n{context}\n\n用户问题：{question}"),
            ]
        )
        return str(response.content)

    @staticmethod
    def _citation(hit: SearchHit) -> dict[str, str | float | None]:
        return {
            "chunkId": hit.chunk_id,
            "documentId": hit.document_id,
            "versionId": hit.version_id,
            "sectionPath": hit.section_path,
            "score": hit.score,
        }
