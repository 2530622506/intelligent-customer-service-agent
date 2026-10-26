import pytest

from app.core.config import Settings
from app.retrieval.providers import DashScopeEmbeddingProvider, DashScopeRerankerProvider


@pytest.mark.asyncio
async def test_embedding_requires_key() -> None:
    provider = DashScopeEmbeddingProvider(Settings(embedding_api_key=""))

    with pytest.raises(RuntimeError, match="EMBEDDING_API_KEY"):
        await provider.embed(["文本"], "document")


@pytest.mark.asyncio
async def test_reranker_returns_none_when_disabled() -> None:
    provider = DashScopeRerankerProvider(Settings(rerank_enabled=False))

    assert await provider.rerank("问题", ["候选"], 1) is None
