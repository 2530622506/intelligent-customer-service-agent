from app.conversation.router import _answer, _answer_chunks, _troubleshooting_result


def test_troubleshooting_requests_missing_model() -> None:
    answer, events = _troubleshooting_result("设备坏了怎么办？")

    assert "产品型号" in answer
    assert any(event_type == "tool_result" for event_type, _ in events)


def test_troubleshooting_escalates_after_attempts() -> None:
    answer, events = _troubleshooting_result("云台摄像机 C1 无法开机，已经重启维修")

    assert "人工" in answer
    assert any(event_type == "handoff" for event_type, _ in events)


def test_answer_chunks_preserve_order_and_reconstruct_text() -> None:
    answer = "产品无法开机，请先检查电源连接。"

    chunks = _answer_chunks(answer, chunk_size=5)

    assert "".join(chunks) == answer
    assert all(0 < len(chunk) <= 5 for chunk in chunks)


def test_policy_fallback_is_user_facing_and_not_demo_text() -> None:
    answer = _answer({"intent": "policy"})

    assert "知识库" in answer
    assert "完成受控分析" not in answer
