from fastapi.testclient import TestClient

from app.main import app


def test_document_operations_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/knowledge/documents" in paths
    assert "/api/v1/knowledge/documents/{document_id}/publish" in paths


def test_document_publish_requires_authentication() -> None:
    response = TestClient(app).post(
        "/api/v1/knowledge/documents/00000000-0000-0000-0000-000000000000/publish"
    )
    assert response.status_code in {401, 403}
