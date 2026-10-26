from fastapi.testclient import TestClient

from app.main import app


def test_analytics_route_is_registered() -> None:
    assert "/api/v1/analytics/query" in app.openapi()["paths"]


def test_analytics_write_without_auth_is_rejected() -> None:
    response = TestClient(app).post("/api/v1/analytics/query", json={"question": "x", "sql": "SELECT 1"})
    assert response.status_code in {401, 403}
