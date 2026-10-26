import pytest

from app.core.config import Settings
from app.retrieval.rag_answer import PolicyRAGService


@pytest.mark.asyncio
async def test_rag_answer_degrades_without_embedding_key() -> None:
    result = await PolicyRAGService(Settings(embedding_api_key="")).answer("退货政策")

    assert result is None
