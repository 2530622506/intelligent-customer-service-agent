
import pytest

from app.workflow.state import (
    APPROVAL_TRANSITIONS,
    HANDOFF_TRANSITIONS,
    ApprovalStatus,
    HandoffStatus,
    WorkflowTransitionError,
    ensure_transition,
)


def test_handoff_state_machine_allows_claim_and_resume() -> None:
    ensure_transition(HANDOFF_TRANSITIONS, "queued", HandoffStatus.HUMAN_ACTIVE)
    ensure_transition(HANDOFF_TRANSITIONS, "human_active", HandoffStatus.AGENT_RESUMED)


def test_handoff_state_machine_rejects_direct_close_from_queue() -> None:
    with pytest.raises(WorkflowTransitionError):
        ensure_transition(HANDOFF_TRANSITIONS, "queued", HandoffStatus.CLOSED)


def test_approval_state_machine_rejects_execution_without_approval() -> None:
    with pytest.raises(WorkflowTransitionError):
        ensure_transition(APPROVAL_TRANSITIONS, ApprovalStatus.PENDING, ApprovalStatus.EXECUTED)
