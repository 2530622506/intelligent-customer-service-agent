from app.core.config import Settings


def test_openai_compatible_credentials_fill_provider_defaults() -> None:
    settings = Settings(
        openai_api_key="test-key",
        openai_base_url="https://example.test/v1",
    )

    assert settings.dashscope_api_key == "test-key"
    assert settings.embedding_api_key == "test-key"
    assert settings.rerank_api_key == "test-key"
    assert settings.chat_base_url == "https://example.test/v1"
