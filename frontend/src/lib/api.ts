export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { message?: string }
    throw new Error(body.message || `请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

export function readCsrfToken(): string | null {
  const item = document.cookie
    .split('; ')
    .find((value) => value.startsWith('csa_csrf_token='))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : null
}

export interface SessionView {
  id: string
  title: string | null
  channel: string
  status: string
}

export interface RunView {
  id: string
  turn_id: string
  status: string
}

export async function login(username: string, password: string) {
  return apiRequest<{ user: { display_name: string; roles: string[] }; csrf_token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function createConversation(title: string) {
  return apiRequest<SessionView>('/conversations', {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
    body: JSON.stringify({ title }),
  })
}

export async function createRun(conversationId: string, message: string) {
  return apiRequest<RunView>(`/conversations/${conversationId}/runs`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
    body: JSON.stringify({ message }),
  })
}

export interface HandoffTaskView {
  id: string
  conversationId: string
  status: string
  reason: string
  riskLevel: string
  assignedUserId: string | null
}

export async function handoffQueue() {
  return apiRequest<HandoffTaskView[]>('/workflow/handoff/queue')
}

export async function claimHandoff(taskId: string) {
  return apiRequest<HandoffTaskView>(`/workflow/handoff/${taskId}/claim`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
}

export async function resolveHandoff(taskId: string) {
  return apiRequest<HandoffTaskView>(`/workflow/handoff/${taskId}/resolve`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
}

export interface MessageView {
  id: string
  turn_id: string
  author_type: string
  content: string
  status: string
}

export async function listConversationMessages(conversationId: string) {
  return apiRequest<MessageView[]>(`/conversations/${conversationId}/messages`)
}

export async function sendStaffMessage(taskId: string, content: string, internal: boolean) {
  return apiRequest<{ messageId: string; authorType: string; status: string }>(`/workflow/handoff/${taskId}/message`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
    body: JSON.stringify({ content, internal }),
  })
}

export async function uploadKnowledgeDocument(file: File) {
  const form = new FormData()
  form.append('upload', file)
  const response = await fetch('/api/v1/knowledge/documents/upload', {
    method: 'POST', credentials: 'include', body: form,
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
  if (!response.ok) throw new Error(`文档上传失败：${response.status}`)
  return response.json() as Promise<{ taskId: string; documentId: string; status: string }>
}

export interface KnowledgeEntityView {
  id: string
  name: string
  entity_type: string
  status: string
  description: string | null
}

export interface EvaluationDatasetView {
  id: string
  name: string
  description: string | null
  status: string
}

export async function listKnowledgeEntities() {
  return apiRequest<KnowledgeEntityView[]>('/knowledge/entities')
}

export async function createKnowledgeEntity(name: string, entityType: string) {
  return apiRequest<KnowledgeEntityView>('/knowledge/entities', {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
    body: JSON.stringify({ name, entity_type: entityType }),
  })
}

export async function publishKnowledgeEntity(id: string) {
  return apiRequest<KnowledgeEntityView>(`/knowledge/entities/${id}/publish`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
}

export async function listEvaluationDatasets() {
  return apiRequest<EvaluationDatasetView[]>('/evaluations/datasets')
}

export async function createEvaluationDataset(name: string) {
  return apiRequest<EvaluationDatasetView>('/evaluations/datasets', {
    method: 'POST',
    headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
    body: JSON.stringify({ name }),
  })
}

export interface KnowledgeRelationView {
  id: string
  source_entity_id: string
  target_entity_id: string
  relation_type: string
  status: string
}

export async function listKnowledgeRelations() {
  return apiRequest<KnowledgeRelationView[]>('/knowledge/relations')
}

export async function createEvaluationRun(datasetId: string) {
  return apiRequest<{ id: string; status: string; model: string }>(`/evaluations/datasets/${datasetId}/runs`, {
    method: 'POST', headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
}

export async function executeEvaluationRun(runId: string) {
  return apiRequest<{ id: string; status: string; summary: Record<string, unknown> }>(`/evaluations/runs/${runId}/execute`, {
    method: 'POST', headers: { 'X-CSRF-Token': readCsrfToken() ?? '' },
  })
}

export async function listEvaluationScores(runId: string) {
  return apiRequest<Array<{ metric: string; value: number; comment: string | null }>>(`/evaluations/runs/${runId}/scores`)
}
