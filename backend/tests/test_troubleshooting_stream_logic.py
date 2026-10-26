from app.conversation.router import _troubleshooting_result


def test_troubleshooting_requests_missing_model() -> None:
    answer, events = _troubleshooting_result("设备坏了怎么办？")

    assert "产品型号" in answer
    assert any(event_type == "tool_result" for event_type, _ in events)


def test_troubleshooting_escalates_after_attempts() -> None:
    answer, events = _troubleshooting_result("云台摄像机 C1 无法开机，已经重启维修")

    assert "人工" in answer
    assert any(event_type == "handoff" for event_type, _ in events)
