from enum import StrEnum


class HandoffStatus(StrEnum):
    PENDING = "handoff_pending"
    QUEUED = "queued"
    HUMAN_ACTIVE = "human_active"
    AGENT_RESUMED = "agent_resumed"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class WorkflowTransitionError(ValueError):
    """拒绝非法的人工接管或审批状态迁移。"""


HANDOFF_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({HandoffStatus.PENDING}),
    "waiting_customer": frozenset({HandoffStatus.PENDING}),
    HandoffStatus.PENDING: frozenset({HandoffStatus.QUEUED}),
    HandoffStatus.QUEUED: frozenset({HandoffStatus.HUMAN_ACTIVE}),
    HandoffStatus.HUMAN_ACTIVE: frozenset(
        {HandoffStatus.AGENT_RESUMED, HandoffStatus.RESOLVED, HandoffStatus.CLOSED}
    ),
    HandoffStatus.AGENT_RESUMED: frozenset({HandoffStatus.PENDING, HandoffStatus.RESOLVED}),
    HandoffStatus.RESOLVED: frozenset({HandoffStatus.CLOSED}),
}


APPROVAL_TRANSITIONS: dict[str, frozenset[str]] = {
    ApprovalStatus.PENDING: frozenset({ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}),
    ApprovalStatus.APPROVED: frozenset({ApprovalStatus.EXECUTED, ApprovalStatus.FAILED}),
}


def ensure_transition(table: dict[str, frozenset[str]], current: str, target: str) -> None:
    allowed = table.get(current, frozenset())
    if target not in allowed:
        raise WorkflowTransitionError(f"非法状态迁移：{current} -> {target}")
