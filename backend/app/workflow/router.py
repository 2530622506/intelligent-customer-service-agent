from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal, RoleCode
from app.db.base import get_db
from app.models import ConversationMessage, HandoffTask
from app.workflow.service import HandoffApprovalService, WorkflowPermissionError

router = APIRouter(prefix="/workflow", tags=["workflow"])


class HandoffRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    risk_level: str = Field(default="normal", max_length=32)
    context_snapshot: dict[str, object] = Field(default_factory=dict)


class ActionPreviewRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    payload: dict[str, object] = Field(default_factory=dict)


class ApprovalNote(BaseModel):
    note: str = Field(default="", max_length=500)


class StaffMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    internal: bool = False


def _task_view(task: HandoffTask) -> dict[str, object]:
    return {
        "id": str(task.id),
        "conversationId": str(task.conversation_id),
        "status": task.status,
        "reason": task.reason,
        "riskLevel": task.risk_level,
        "assignedUserId": str(task.assigned_user_id) if task.assigned_user_id else None,
    }


@router.post("/conversations/{conversation_id}/handoff", dependencies=[Depends(require_csrf)])
async def request_handoff(
    conversation_id: UUID,
    payload: HandoffRequest,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    task = await HandoffApprovalService().request_handoff(
        session,
        conversation_id,
        payload.reason,
        payload.risk_level,
        payload.context_snapshot,
        principal.user_id,
    )
    return _task_view(task)


@router.get("/handoff/queue")
async def handoff_queue(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    if not principal.can("conversation:read:assigned") and not principal.has_role(RoleCode.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看人工队列")
    tasks = await session.scalars(
        select(HandoffTask).where(HandoffTask.status.in_(("queued", "human_active"))).order_by(HandoffTask.created_at.asc())
    )
    return [_task_view(task) for task in tasks]


@router.post("/handoff/{task_id}/claim", dependencies=[Depends(require_csrf)])
async def claim_handoff(
    task_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    try:
        task = await HandoffApprovalService().claim_handoff(session, task_id, principal)
    except WorkflowPermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return _task_view(task)


@router.post("/handoff/{task_id}/resolve", dependencies=[Depends(require_csrf)])
async def resolve_handoff(
    task_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    try:
        task = await HandoffApprovalService().resolve_handoff(session, task_id, principal)
    except WorkflowPermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return _task_view(task)


@router.post("/handoff/{task_id}/message", dependencies=[Depends(require_csrf)])
async def staff_message(
    task_id: UUID,
    payload: StaffMessage,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    task = await session.get(HandoffTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="人工任务不存在")
    if task.assigned_user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="不是该人工任务的处理人")
    if task.status != "human_active":
        raise HTTPException(status_code=409, detail="会话不在人工处理中")
    message = ConversationMessage(
        conversation_id=task.conversation_id,
        turn_id=uuid4(),
        author_type="internal_note" if payload.internal else "staff",
        actor_id=principal.user_id,
        content=payload.content,
        status="completed",
    )
    session.add(message)
    await session.commit()
    return {"messageId": str(message.id), "authorType": message.author_type, "status": "completed"}


@router.post("/handoff/{task_id}/resume-agent", dependencies=[Depends(require_csrf)])
async def resume_agent(
    task_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    try:
        task = await HandoffApprovalService().resume_agent(session, task_id, principal)
    except WorkflowPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return _task_view(task)


@router.post("/conversations/{conversation_id}/actions/preview", dependencies=[Depends(require_csrf)])
async def preview_action(
    conversation_id: UUID,
    payload: ActionPreviewRequest,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    approval = await HandoffApprovalService().create_action_preview(
        session, conversation_id, principal.user_id, payload.action_id, payload.idempotency_key, payload.payload
    )
    return {"approvalId": str(approval.id), "actionId": approval.action_id, "status": approval.status}


@router.post("/actions/{approval_id}/confirm", dependencies=[Depends(require_csrf)])
async def confirm_action(
    approval_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    approval = await HandoffApprovalService().confirm_action(session, approval_id, principal.user_id)
    return {"approvalId": str(approval.id), "status": approval.status, "userConfirmed": True}


@router.post("/actions/{approval_id}/approve", dependencies=[Depends(require_csrf)])
async def approve_action(
    approval_id: UUID,
    payload: ApprovalNote,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    execution = await HandoffApprovalService().approve_action(session, approval_id, principal, payload.note)
    return {"approvalId": str(approval_id), "executionStatus": execution.status, "result": execution.result}
