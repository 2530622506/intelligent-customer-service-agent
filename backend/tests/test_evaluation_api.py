from fastapi.testclient import TestClient

from app.main import app


def test_evaluation_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/evaluations/datasets" in paths
    assert "/api/v1/evaluations/datasets/{dataset_id}/runs" in paths


def test_evaluation_write_requires_authentication() -> None:
    response = TestClient(app).post("/api/v1/evaluations/datasets", json={"name": "test"})
    assert response.status_code in {401, 403}
