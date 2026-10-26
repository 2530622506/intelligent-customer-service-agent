from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )


class RefreshSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_session"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    token_jti: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_to_jti: Mapped[str | None] = mapped_column(String(128))


class RolePermission(Base):
    __tablename__ = "role_permission"

    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True
    )


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "team"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class TeamMember(Base):
    __tablename__ = "team_member"

    team_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("team.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation"

    owner_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), default="web", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    title: Mapped[str | None] = mapped_column(String(160))
    data_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    assigned_agent_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))

    __table_args__ = (Index("ix_conversation_owner_status", "owner_user_id", "status"),)


class ConversationMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversation_message"

    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_masked: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_message_conversation_created", "conversation_id", "created_at"),
        UniqueConstraint("conversation_id", "turn_id", "author_type", name="uq_message_turn_author"),
    )


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_run"

    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    intent: Mapped[str | None] = mapped_column(String(80))
    trace_id: Mapped[str | None] = mapped_column(String(128))
    state_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))


class AgentStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_step"

    agent_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("agent_run_id", "sequence", name="uq_agent_step_sequence"),)


class HandoffTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "handoff_task"

    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    assigned_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class CustomerOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_order"

    customer_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    masked_address: Mapped[str | None] = mapped_column(String(255))
    data_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class LogisticsRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "logistics_record"

    order_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("customer_order.id", ondelete="CASCADE"), nullable=False
    )
    tracking_no: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_location: Mapped[str | None] = mapped_column(String(120))


class AfterSaleRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "after_sale_record"

    order_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("customer_order.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ticket"

    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("customer_order.id"))
    ticket_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_request"

    ticket_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("ticket.id"))
    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    requested_by: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)


class ActionExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "action_execution"

    action_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    approval_request_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("approval_request.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_document"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    access_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class KnowledgeDocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_document_version"

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_structure: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source_object_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
    )


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunk"

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document_version.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str | None] = mapped_column(String(500))
    parent_chunk_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    chunking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    index_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)

    __table_args__ = (UniqueConstraint("version_id", "chunk_index", name="uq_chunk_version_index"),)


class ParseTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parse_task"

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    source_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    mineru_task_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class GraphEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "graph_entity"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class GraphRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "graph_relation"

    source_entity_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("graph_entity.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("graph_entity.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class GraphEntitySource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "graph_entity_source"

    entity_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("graph_entity.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_document_version.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))


class GraphChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "graph_change"

    actor_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    relation_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_log"

    actor_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128))
    request_id: Mapped[str | None] = mapped_column(String(128))
    trace_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_dataset"

    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)


class EvalCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_case"

    dataset_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_dataset.id", ondelete="CASCADE"), nullable=False
    )
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("dataset_id", "case_key", name="uq_eval_case_key"),)


class EvalRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_run"

    dataset_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_dataset.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    filter_value: Mapped[str | None] = mapped_column(String(160))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class EvalScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "eval_score"

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_run.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_case.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("run_id", "case_id", "metric", name="uq_eval_score_metric"),)
