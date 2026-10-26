from app.core.config import Settings
from app.observability.tracing import AgentTracer


def test_tracer_without_credentials_uses_local_fallback() -> None:
    tracer = AgentTracer(Settings(langfuse_enabled=True, langfuse_public_key="", langfuse_secret_key=""))

    with tracer.run("run-test", "敏感问题") as metadata:
        assert metadata["question_length"] == 4
