from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Mapping
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import QwenSupervisorPlanner
from app.agent.runtime import ControlledAgentRuntime
from app.auth.dependencies import get_principal, require_csrf
from app.auth.policy import scope_for_roles
from app.auth.types import AuthPrincipal, RoleCode
from app.business.agents import OrderLogisticsAgent, TroubleshootingAgent
from app.business.mock_data import MockAfterSalesData
from app.business.schemas import TroubleshootingState
from app.business.tools import MockLogisticsTool, MockOrderTool, ToolPolicyError
from app.conversation.schemas import (
    ConversationView,
    CreateConversationRequest,
    CreateRunRequest,
    MessageView,
    RunView,
    SSEEvent,
)
from app.core.config import Settings, get_settings
from app.db.base import get_db, session_factory
from app.models import AgentRun, Conversation, ConversationMessage
from app.observability.tracing import AgentTracer
from app.retrieval.rag_answer import PolicyRAGService

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


@router.post("/{conversation_id}/runs/{run_id}/stream", dependencies=[Depends(require_csrf)])
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
        event_id = 1
        try:
            # 先把连接状态发给客户端，再把同步的 LangGraph 调用移到线程，避免事件循环被模型调用阻塞。
            yield _format_sse(event_id, "run_started", conversation_id, run.turn_id, run.id, {"status": "running"})
            event_id += 1
            yield _format_sse(event_id, "agent_step", conversation_id, run.turn_id, run.id, {"node": "supervisor_plan", "status": "running"})
            event_id += 1
            await asyncio.sleep(0)
            result = await asyncio.to_thread(runtime.invoke, question, str(run.id))
            answer = _answer(result)
            sequence: list[tuple[str, Mapping[str, object]]] = [("agent_step", {"node": "supervisor_plan", "status": "completed"})]
            plan = result.get("plan")
            selected_agents = plan.get("agents", []) if isinstance(plan, dict) else []
            rag = await PolicyRAGService(settings).answer(question) if "policy" in selected_agents else None
            if rag:
                sequence.append(("retrieval", {"candidateCount": len(rag.citations)}))
                sequence.extend(("citation", citation) for citation in rag.citations)
                answer = rag.answer
            if "order_logistics" in selected_agents:
                answer, order_events = _order_result(question, principal.user_id)
                sequence.extend(order_events)
            if "troubleshooting" in selected_agents:
                answer, troubleshooting_events = _troubleshooting_result(question)
                sequence.extend(troubleshooting_events)
            sequence.extend(("token", {"text": chunk}) for chunk in _answer_chunks(answer))
            sequence.append(("done", {"status": "completed"}))
            for event_type, data in sequence:
                if await request.is_disconnected():
                    break
                yield _format_sse(event_id, event_type, conversation_id, run.turn_id, run.id, data)
                event_id += 1
                # 给 ASGI / Nginx 一个调度点，确保浏览器可以逐段消费，而不是等完整答案生成后一次性收到。
                await asyncio.sleep(0.015 if event_type == "token" else 0)
            # 客户端断开只停止网络输出，不丢弃已经完成的 Agent 结果。
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
            yield _format_sse(event_id, "error", conversation_id, run.turn_id, run.id, {"code": "RUN_FAILED"})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


async def _replay_completed(run: AgentRun, answer: str) -> AsyncIterator[str]:
    """断线重连只回放已持久化结果，不再次执行 Agent。"""
    yield _format_sse(1, "run_started", run.conversation_id, run.turn_id, run.id, {"status": "replay"})
    event_id = 2
    for chunk in _answer_chunks(answer):
        yield _format_sse(event_id, "token", run.conversation_id, run.turn_id, run.id, {"text": chunk})
        event_id += 1
        await asyncio.sleep(0.015)
    yield _format_sse(event_id, "done", run.conversation_id, run.turn_id, run.id, {"status": "completed", "replay": True})


def _answer_chunks(answer: str, chunk_size: int = 12) -> list[str]:
    """把已生成的答案切成短片段，保持 SSE 的增量消费体验。"""
    if not answer:
        return []
    return [answer[index:index + chunk_size] for index in range(0, len(answer), chunk_size)]


def _format_sse(
    event_id: int,
    event_type: str,
    conversation_id: UUID,
    turn_id: UUID,
    run_id: UUID,
    data: Mapping[str, object],
) -> str:
    event = SSEEvent(
        eventId=event_id,
        conversationId=str(conversation_id),
        turnId=str(turn_id),
        runId=str(run_id),
        type=event_type,
        data=dict(data),
    )
    return f"id: {event_id}\nevent: {event_type}\ndata: {event.model_dump_json()}\n\n"


def _answer(result: dict[str, object]) -> str:
    if result.get("error_code"):
        return "当前问题无法在安全范围内完成，我可以为你转人工客服。"
    fallback_answers = {
        "policy": "我已识别这是售后政策问题，但当前知识库暂时不可用。请稍后重试，或转人工客服继续处理。",
        "troubleshooting": "我已识别这是产品故障排查问题，请补充产品型号和具体故障现象。",
        "order_logistics": "我已识别这是订单 / 物流问题，请提供订单号，我再帮你查询。",
        "analytics": "我已识别这是售后数据分析问题，但当前分析服务暂时不可用。",
        "ticket": "我已识别这是工单处理问题，请补充需要处理的售后事项。",
    }
    return fallback_answers.get(str(result.get("intent", "policy")), "当前服务暂时不可用，请稍后重试或转人工客服。")


def _order_result(question: str, customer_id: UUID) -> tuple[str, list[tuple[str, dict[str, object]]]]:
    order_match = re.search(r"CS\d{12}", question, flags=re.IGNORECASE)
    if not order_match:
        return "请提供订单号（例如 CS202610270001），我再帮你查询订单和物流。", []
    order_no = order_match.group(0).upper()
    data = MockAfterSalesData(customer_id)
    scope = scope_for_roles(customer_id, frozenset({RoleCode.CUSTOMER}), ())
    agent = OrderLogisticsAgent(MockOrderTool(data), MockLogisticsTool(data))
    try:
        order, logistics = agent.lookup(order_no, scope)
    except ToolPolicyError:
        return "当前账号无权查询该订单。", [("tool_result", {"tool": "order_lookup", "status": "forbidden"})]
    if not order.found:
        return "没有找到该订单，请确认订单号是否正确。", [("tool_result", {"tool": "order_lookup", "status": "not_found"})]
    return (
        f"订单 {order_no} 当前状态为：{order.status}。物流单号 {logistics.get('trackingNo')}，当前状态：{logistics.get('status')}。",
        [
            ("tool_call", {"tool": "order_lookup", "orderNo": order_no}),
            ("tool_call", {"tool": "logistics_lookup", "orderNo": order_no}),
            ("tool_result", {"tool": "order_logistics", "status": "ok", "orderNo": order_no}),
        ],
    )


def _troubleshooting_result(question: str) -> tuple[str, list[tuple[str, dict[str, object]]]]:
    state = TroubleshootingState(
        product_model="C1" if "摄像机" in question or "C1" in question else None,
        symptom=question if any(keyword in question for keyword in ("故障", "坏", "无法", "开机", "维修")) else None,
        attempted_steps=[step for step in ("重启", "换电源", "维修") if step in question],
    )
    next_state = TroubleshootingAgent().next_step(state)
    if next_state.escalation_required:
        return "基础排查仍未解决，建议转人工客服创建维修工单。", [
            ("tool_result", {"tool": "troubleshooting", "status": "escalation_required"}),
            ("handoff", {"reason": "基础排查未解决", "riskLevel": "normal"}),
        ]
    return next_state.next_question or "请补充产品型号和故障现象。", [
        ("tool_call", {"tool": "troubleshooting", "status": "collecting_slots"}),
        ("tool_result", {"tool": "troubleshooting", "status": "needs_input"}),
    ]
