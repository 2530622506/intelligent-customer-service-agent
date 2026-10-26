import json
from uuid import uuid4

from app.conversation.router import _format_sse


def test_sse_payload_contains_cross_layer_identity_fields() -> None:
    conversation_id, turn_id, run_id = uuid4(), uuid4(), uuid4()
    payload = _format_sse(3, "token", conversation_id, turn_id, run_id, {"text": "ok"})
    data = next(line.removeprefix("data: ") for line in payload.splitlines() if line.startswith("data:"))
    event = json.loads(data)
    assert event == {
        "eventId": 3,
        "conversationId": str(conversation_id),
        "turnId": str(turn_id),
        "runId": str(run_id),
        "type": "token",
        "data": {"text": "ok"},
    }
