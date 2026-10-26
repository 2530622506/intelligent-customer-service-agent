
from app.business.agents import AnalyticsAgent, PolicyAgent, TroubleshootingAgent
from app.business.schemas import AnalyticsQuery, TroubleshootingState
from app.business.sql_gateway import ReadOnlySQLGateway


def test_policy_agent_requires_citations_for_grounded_answer() -> None:
    agent = PolicyAgent()

    assert agent.answer("有依据", ["chunk-1"]).grounded
    assert not agent.answer("没有依据", []).grounded


def test_troubleshooting_agent_is_structured_and_escalates() -> None:
    agent = TroubleshootingAgent()
    state = TroubleshootingState(product_model="C1", symptom="无法开机", attempted_steps=["重启", "换电源"])

    next_state = agent.next_step(state)

    assert next_state.escalation_required


def test_analytics_agent_returns_policy_failure_as_data() -> None:
    agent = AnalyticsAgent(ReadOnlySQLGateway())
    result = agent.validate_query(
        AnalyticsQuery(question="查密码", sql="SELECT password_hash FROM app_user")
    )

    assert not result.accepted
