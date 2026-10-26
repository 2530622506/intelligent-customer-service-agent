from fastapi.testclient import TestClient

from app.main import app


def test_conversation_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/conversations" in paths
    assert "/api/v1/conversations/{conversation_id}/runs/{run_id}/stream" in paths


def test_unauthenticated_conversation_creation_is_rejected() -> None:
    response = TestClient(app).post("/api/v1/conversations", json={"title": "test"})
    # Cookie 认证接口先经过 CSRF 防护；未登录请求可能先得到 403。
    assert response.status_code in {401, 403}
