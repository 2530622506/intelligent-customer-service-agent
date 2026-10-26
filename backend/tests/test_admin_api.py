from fastapi.testclient import TestClient

from app.main import app


def test_admin_routes_are_registered() -> None:
    assert "/api/v1/admin/users" in app.openapi()["paths"]
    assert "/api/v1/admin/users/{user_id}/roles" in app.openapi()["paths"]


def test_admin_write_requires_authentication() -> None:
    response = TestClient(app).get("/api/v1/admin/users")
    assert response.status_code in {401, 403}
