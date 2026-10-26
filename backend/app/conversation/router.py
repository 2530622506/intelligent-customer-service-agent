from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import QwenSupervisorPlanner
from app.agent.runtime import ControlledAgentRuntime
from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal
from app.conversation.schemas import (
    ConversationView,
    CreateConversationRequest,
    CreateRunRequest,
    MessageView,
    RunView,
)
from app.core.config import Settings, get_settings
from app.db.base import get_db, session_factory
from app.models import AgentRun, Conversation, ConversationMessage
from app.observability.tracing import AgentTracer

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationView, dependencies=[Depends(require_csrf)])
async def create_conversation(
    payload: CreateConversationRequest,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationView:
    conversation = Conversation(
        owner_user_id=principal.user_id,
        title=payload.title,
        channel=payload.channel,
        status="active",
        data_scope=principal.data_scope.as_dict(),
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return ConversationView(
        id=str(conversation.id), title=conversation.title, channel=conversation.channel, status=conversation.status
    )


@router.get("", response_model=list[ConversationView])
async def list_conversations(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConversationView]:
    rows = await session.scalars(
        select(Conversation)
        .where(Conversation.owner_user_id == principal.user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return [
        ConversationView(id=str(row.id), title=row.title, channel=row.channel, status=row.status)
        for row in rows
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageView])
async def list_messages(
    conversation_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MessageView]:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_user_id == principal.user_id,
        )
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    rows = await session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
    )
    return [
        MessageView(id=str(row.id), turn_id=str(row.turn_id), author_type=row.author_type, content=row.content, status=row.status)
        for row in rows
    ]


@router.post("/{conversation_id}/runs", response_model=RunView, dependencies=[Depends(require_csrf)])
async def create_run(
    conversation_id: UUID,
    payload: CreateRunRequest,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunView:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.owner_user_id == principal.user_id)
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if payload.turn_id:
        turn_id = UUID(payload.turn_id)
    elif idempotency_key:
        turn_id = uuid5(NAMESPACE_URL, f"customer-service-run:{principal.user_id}:{idempotency_key}")
    else:
        turn_id = uuid4()
    existing = await session.scalar(select(AgentRun).where(AgentRun.turn_id == turn_id))
    if existing:
        if existing.conversation_id != conversation_id:
            raise HTTPException(status_code=409, detail="幂等键已用于其他会话")
        return RunView(id=str(existing.id), turn_id=str(existing.turn_id), status=existing.status)
    run = AgentRun(conversation_id=conversation_id, turn_id=turn_id, status="queued")
    session.add(run)
    session.add(ConversationMessage(conversation_id=conversation_id, turn_id=turn_id, author_type="customer", actor_id=principal.user_id, content=payload.message, status="completed"))
    await session.commit()
    await session.refresh(run)
    return RunView(id=str(run.id), turn_id=str(run.turn_id), status=run.status)


@router.post("/{conversation_id}/runs/{run_id}/stream")
async def stream_run(
    conversation_id: UUID,
    run_id: UUID,
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    run = await session.scalar(
        select(AgentRun)
        .join(Conversation, Conversation.id == AgentRun.conversation_id)
        .where(AgentRun.id == run_id, AgentRun.conversation_id == conversation_id, Conversation.owner_user_id == principal.user_id)
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
    question = await session.scalar(
        select(ConversationMessage.content).where(ConversationMessage.conversation_id == conversation_id, ConversationMessage.turn_id == run.turn_id, ConversationMessage.author_type == "customer")
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行缺少用户问题")
    if run.status == "completed":
        answer = await session.scalar(
            select(ConversationMessage.content).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.turn_id == run.turn_id,
                ConversationMessage.author_type == "agent",
            )
        )
        return StreamingResponse(
            _replay_completed(run, answer or ""),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    run.status = "running"
    await session.commit()

    async def events() -> AsyncIterator[str]:
        planner = QwenSupervisorPlanner(settings) if settings.dashscope_api_key else None
        runtime = ControlledAgentRuntime(planner=planner, tracer=AgentTracer(settings))
        try:
            result = runtime.invoke(question, str(run.id))
            answer = _answer(result)
            sequence = [
                ("run_started", {"status": "running"}),
                ("agent_step", {"node": "supervisor_plan", "status": "completed"}),
                ("token", {"text": answer}),
                ("done", {"status": "completed"}),
            ]
            for event_id, (event_type, data) in enumerate(sequence, 1):
                if await request.is_disconnected():
                    return
                yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
            async with session_factory() as write_session:
                stored_run = await write_session.get(AgentRun, run_id, with_for_update=True)
                if stored_run and stored_run.status != "completed":
                    stored_run.status = "completed"
                    write_session.add(ConversationMessage(conversation_id=conversation_id, turn_id=run.turn_id, author_type="agent", content=answer, status="completed"))
                    await write_session.commit()
        except Exception as error:  # noqa: BLE001
            async with session_factory() as write_session:
                stored_run = await write_session.get(AgentRun, run_id, with_for_update=True)
                if stored_run:
                    stored_run.status = "failed"
                    stored_run.error_code = str(error)[:80]
                    await write_session.commit()
            yield 'event: error\ndata: {"type":"error","data":{"code":"RUN_FAILED"}}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


async def _replay_completed(run: AgentRun, answer: str) -> AsyncIterator[str]:
    """断线重连只回放已持久化结果，不再次执行 Agent。"""
    yield 'id: 1\nevent: run_started\ndata: {"type":"run_started","data":{"status":"replay"}}\n\n'
    yield f'id: 2\nevent: token\ndata: {{"type":"token","data":{{"text":{json.dumps(answer, ensure_ascii=False)}}}}}\n\n'
    yield 'id: 3\nevent: done\ndata: {"type":"done","data":{"status":"completed","replay":true}}\n\n'


def _answer(result: dict[str, object]) -> str:
    if result.get("error_code"):
        return "当前问题无法在安全范围内完成，我可以为你转人工客服。"
    return f"已由 {result.get('intent', 'policy')} Agent 完成受控分析。"
