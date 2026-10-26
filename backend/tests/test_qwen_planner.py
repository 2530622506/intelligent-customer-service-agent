from app.agent.planner import QwenSupervisorPlanner
from app.core.config import Settings


def test_planner_can_be_constructed_with_openai_compatible_config() -> None:
    planner = QwenSupervisorPlanner(
        Settings(
            dashscope_api_key="test-key",
            chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            chat_model="qwen3.7-flash",
        )
    )

    assert planner.model is not None
