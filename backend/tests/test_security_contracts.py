from fastapi.testclient import TestClient

from app.main import app


def test_stream_endpoint_is_in_openapi_and_requires_post() -> None:
    operation = app.openapi()["paths"][
        "/api/v1/conversations/{conversation_id}/runs/{run_id}/stream"
    ]
    assert "post" in operation
    assert "get" not in operation


def test_sensitive_write_endpoints_do_not_accept_unauthenticated_requests() -> None:
    client = TestClient(app)
    endpoints = [
        ("/api/v1/conversations", {"title": "x"}),
        ("/api/v1/evaluations/datasets", {"name": "x"}),
        ("/api/v1/knowledge/entities", {"name": "x", "entity_type": "policy"}),
    ]
    for endpoint, body in endpoints:
        response = client.post(endpoint, json=body)
        assert response.status_code in {401, 403}, endpoint
