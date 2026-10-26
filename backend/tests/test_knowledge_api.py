from fastapi.testclient import TestClient

from app.main import app


def test_knowledge_graph_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/knowledge/entities" in paths
    assert "/api/v1/knowledge/relations" in paths


def test_knowledge_graph_write_requires_authentication() -> None:
    response = TestClient(app).post(
        "/api/v1/knowledge/entities",
        json={"name": "退货政策", "entity_type": "policy"},
    )
    assert response.status_code in {401, 403}
