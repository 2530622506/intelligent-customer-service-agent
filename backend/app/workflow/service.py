from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.types import AuthPrincipal, RoleCode
from app.models import ActionExecution, ApprovalRequest, AuditLog, Conversation, HandoffTask
from app.workflow.state import (
    APPROVAL_TRANSITIONS,
    HANDOFF_TRANSITIONS,
    ApprovalStatus,
    HandoffStatus,
    WorkflowTransitionError,
    ensure_transition,
)


class WorkflowPermissionError(PermissionError):
    """当前用户没有执行工作流操作的权限。"""


class HandoffApprovalService:
    """所有状态迁移和幂等执行都在服务端完成，不接受模型直接改状态。"""

    async def request_handoff(
        self,
        session: AsyncSession,
        conversation_id: UUID,
        reason: str,
        risk_level: str,
        context_snapshot: dict[str, Any],
        actor_id: UUID,
    ) -> HandoffTask:
        conversation = await session.get(Conversation, conversation_id, with_for_update=True)
        if not conversation:
            raise ValueError("会话不存在")
        ensure_transition(HANDOFF_TRANSITIONS, conversation.status, HandoffStatus.PENDING)
        conversation.status = HandoffStatus.QUEUED
        task = HandoffTask(
            conversation_id=conversation_id,
            reason=reason,
            risk_level=risk_level,
            status=HandoffStatus.QUEUED,
            context_snapshot=context_snapshot,
        )
        session.add(task)
        await self._audit(session, actor_id, "handoff.request", "conversation", conversation_id)
        await session.commit()
        await session.refresh(task)
        return task

    async def claim_handoff(
        self, session: AsyncSession, task_id: UUID, principal: AuthPrincipal
    ) -> HandoffTask:
        if not principal.can("conversation:reply:assigned") and not principal.has_role(RoleCode.SUPERVISOR):
            raise WorkflowPermissionError("没有接管人工会话的权限")
        task = await session.get(HandoffTask, task_id, with_for_update=True)
        if not task:
            raise ValueError("人工任务不存在")
        ensure_transition(HANDOFF_TRANSITIONS, task.status, HandoffStatus.HUMAN_ACTIVE)
        conversation = await session.get(Conversation, task.conversation_id, with_for_update=True)
        if not conversation:
            raise ValueError("会话不存在")
        task.status = HandoffStatus.HUMAN_ACTIVE
        task.assigned_user_id = principal.user_id
        conversation.status = HandoffStatus.HUMAN_ACTIVE
        await self._audit(session, principal.user_id, "handoff.claim", "handoff_task", task.id)
        await session.commit()
        await session.refresh(task)
        return task

    async def resume_agent(
        self, session: AsyncSession, task_id: UUID, principal: AuthPrincipal
    ) -> HandoffTask:
        task = await self._assigned_task(session, task_id, principal)
        ensure_transition(HANDOFF_TRANSITIONS, task.status, HandoffStatus.AGENT_RESUMED)
        task.status = HandoffStatus.AGENT_RESUMED
        conversation = await session.get(Conversation, task.conversation_id, with_for_update=True)
        if not conversation:
            raise ValueError("会话不存在")
        conversation.status = HandoffStatus.AGENT_RESUMED
        await self._audit(session, principal.user_id, "handoff.resume_agent", "handoff_task", task.id)
        await session.commit()
        return task

    async def resolve_handoff(
        self, session: AsyncSession, task_id: UUID, principal: AuthPrincipal
    ) -> HandoffTask:
        task = await self._assigned_task(session, task_id, principal)
        ensure_transition(HANDOFF_TRANSITIONS, task.status, HandoffStatus.RESOLVED)
        task.status = HandoffStatus.RESOLVED
        conversation = await session.get(Conversation, task.conversation_id, with_for_update=True)
        if not conversation:
            raise ValueError("会话不存在")
        conversation.status = HandoffStatus.RESOLVED
        await self._audit(session, principal.user_id, "handoff.resolve", "handoff_task", task.id)
        await session.commit()
        return task

    async def create_action_preview(
        self,
        session: AsyncSession,
        conversation_id: UUID,
        requested_by: UUID,
        action_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> ApprovalRequest:
        existing = await session.scalar(
            select(ApprovalRequest).where(ApprovalRequest.action_id == action_id)
        )
        if existing:
            return existing
        approval = ApprovalRequest(
            conversation_id=conversation_id,
            requested_by=requested_by,
            action_id=action_id,
            action_payload={**payload, "user_confirmed": False},
            status=ApprovalStatus.PENDING,
        )
        # 先生成审批主键，再建立执行记录外键。
        session.add(approval)
        await session.flush()
        execution = ActionExecution(
            action_id=action_id,
            idempotency_key=idempotency_key,
            approval_request_id=approval.id,
            status=ApprovalStatus.PENDING,
        )
        session.add(execution)
        await self._audit(session, requested_by, "action.preview", "approval_request", approval.id)
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            existing = await session.scalar(
                select(ApprovalRequest).where(ApprovalRequest.action_id == action_id)
            )
            if existing:
                return existing
            raise ValueError("动作幂等键冲突") from error
        await session.refresh(approval)
        return approval

    async def confirm_action(
        self, session: AsyncSession, approval_id: UUID, customer_id: UUID
    ) -> ApprovalRequest:
        approval = await session.get(ApprovalRequest, approval_id, with_for_update=True)
        if not approval or approval.requested_by != customer_id:
            raise WorkflowPermissionError("无权确认该动作")
        if approval.status != ApprovalStatus.PENDING:
            raise WorkflowTransitionError("动作不在待确认状态")
        approval.action_payload = {**approval.action_payload, "user_confirmed": True}
        await session.commit()
        return approval

    async def approve_action(
        self, session: AsyncSession, approval_id: UUID, reviewer: AuthPrincipal, note: str = ""
    ) -> ActionExecution:
        if not reviewer.has_role(RoleCode.SUPERVISOR) and not reviewer.has_role(RoleCode.ADMIN):
            raise WorkflowPermissionError("只有主管或管理员可以审批")
        approval = await session.get(ApprovalRequest, approval_id, with_for_update=True)
        if not approval:
            raise ValueError("审批请求不存在")
        if not approval.action_payload.get("user_confirmed"):
            raise WorkflowTransitionError("用户尚未确认动作")
        ensure_transition(APPROVAL_TRANSITIONS, approval.status, ApprovalStatus.APPROVED)
        approval.status = ApprovalStatus.APPROVED
        approval.reviewed_by = reviewer.user_id
        approval.review_note = note
        execution = await session.scalar(
            select(ActionExecution).where(ActionExecution.approval_request_id == approval.id).with_for_update()
        )
        if not execution:
            raise ValueError("动作执行记录不存在")
        # 模拟执行只允许在审批通过后完成，并且依赖唯一 action_id / idempotency_key。
        ensure_transition(APPROVAL_TRANSITIONS, execution.status, ApprovalStatus.APPROVED)
        execution.status = ApprovalStatus.APPROVED
        ensure_transition(APPROVAL_TRANSITIONS, execution.status, ApprovalStatus.EXECUTED)
        execution.status = ApprovalStatus.EXECUTED
        execution.result = {"simulated": True, "executedAt": datetime.now(UTC).isoformat()}
        approval.status = ApprovalStatus.EXECUTED
        await self._audit(session, reviewer.user_id, "action.execute_simulation", "approval_request", approval.id)
        await session.commit()
        return execution

    async def _assigned_task(
        self, session: AsyncSession, task_id: UUID, principal: AuthPrincipal
    ) -> HandoffTask:
        task = await session.get(HandoffTask, task_id, with_for_update=True)
        if not task:
            raise ValueError("人工任务不存在")
        if task.assigned_user_id != principal.user_id:
            raise WorkflowPermissionError("不是该人工任务的处理人")
        return task

    @staticmethod
    async def _audit(
        session: AsyncSession,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                payload={},
            )
        )
