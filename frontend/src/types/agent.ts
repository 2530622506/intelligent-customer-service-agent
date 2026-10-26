export type AgentEventType =
  | 'run_started'
  | 'agent_step'
  | 'retrieval'
  | 'citation'
  | 'token'
  | 'tool_call'
  | 'tool_result'
  | 'approval_required'
  | 'handoff'
  | 'error'
  | 'done'

export interface AgentEvent<T = Record<string, unknown>> {
  eventId: number
  conversationId: string
  turnId: string
  runId: string
  type: AgentEventType
  data: T
}

export interface AgentStreamState {
  status: 'idle' | 'connecting' | 'streaming' | 'completed' | 'error' | 'cancelled'
  answer: string
  events: AgentEvent[]
  citations: Array<Record<string, unknown>>
  error: string | null
}
