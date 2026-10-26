from sqlalchemy import UniqueConstraint

from app import models  # noqa: F401  # 导入全部模型，触发 metadata 注册。
from app.db.base import Base


def test_core_tables_are_registered() -> None:
    expected = {
        "app_user",
        "conversation",
        "conversation_message",
        "agent_run",
        "agent_step",
        "customer_order",
        "ticket",
        "approval_request",
        "action_execution",
        "knowledge_document",
        "knowledge_document_version",
        "knowledge_chunk",
        "parse_task",
        "graph_entity",
        "graph_relation",
        "audit_log",
    }

    assert expected.issubset(Base.metadata.tables)


def test_idempotent_and_version_constraints_exist() -> None:
    action_constraints = Base.metadata.tables["action_execution"].constraints
    version_constraints = Base.metadata.tables["knowledge_document_version"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns}
        == {"idempotency_key"}
        for constraint in action_constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns}
        == {"document_id", "version_number"}
        for constraint in version_constraints
    )
