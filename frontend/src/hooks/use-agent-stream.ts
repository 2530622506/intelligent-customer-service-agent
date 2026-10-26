import { useCallback, useMemo, useRef, useState } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { AgentEvent, AgentEventType, AgentStreamState } from '../types/agent'
import { readCsrfToken } from '../lib/api'

interface StreamPayload {
  conversationId: string
  runId: string
}

interface RawEvent {
  eventId?: number
  conversationId?: string
  turnId?: string
  runId?: string
  type?: AgentEventType
  data?: Record<string, unknown>
}

const initialState: AgentStreamState = {
  status: 'idle',
  answer: '',
  events: [],
  citations: [],
  error: null,
}

export function useAgentStream() {
  const [state, setState] = useState<AgentStreamState>(initialState)
  const controllerRef = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setState((current) => ({ ...current, status: 'cancelled' }))
  }, [])

  const send = useCallback(async ({ conversationId, runId }: StreamPayload) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const seen = new Set<number>()
    setState({ ...initialState, status: 'connecting' })

    try {
      await fetchEventSource(`/api/v1/conversations/${conversationId}/runs/${runId}/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'text/event-stream',
          ...(readCsrfToken() ? { 'X-CSRF-Token': readCsrfToken()! } : {}),
        },
        signal: controller.signal,
        onopen: async (response) => {
          if (!response.ok) throw new Error(`SSE 连接失败：${response.status}`)
          setState((current) => ({ ...current, status: 'streaming' }))
        },
        onmessage: (message) => {
          if (!message.data) return
          const event = JSON.parse(message.data) as RawEvent
          const eventId = event.eventId ?? Number(message.id)
          if (Number.isFinite(eventId) && seen.has(eventId)) return
          if (Number.isFinite(eventId)) seen.add(eventId)
          const normalized: AgentEvent = {
            eventId,
            conversationId: event.conversationId ?? conversationId,
            turnId: event.turnId ?? '',
            runId: event.runId ?? runId,
            type: event.type ?? (message.event as AgentEventType),
            data: event.data ?? {},
          }
          setState((current) => {
            const nextAnswer = normalized.type === 'token'
              ? current.answer + String(normalized.data.text ?? '')
              : current.answer
            const nextCitations = normalized.type === 'citation'
              ? [...current.citations, normalized.data]
              : current.citations
            return {
              ...current,
              answer: nextAnswer,
              events: [...current.events, normalized],
              citations: nextCitations,
              status: normalized.type === 'done' ? 'completed' : current.status,
              error: normalized.type === 'error' ? String(normalized.data.message ?? '运行失败') : current.error,
            }
          })
        },
        onerror: (error) => {
          throw error instanceof Error ? error : new Error('SSE 连接异常')
        },
      })
    } catch (error) {
      if (controller.signal.aborted) return
      setState((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'SSE 运行失败',
      }))
      throw error
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
    }
  }, [])

  return useMemo(() => ({ state, send, stop }), [send, state, stop])
}
