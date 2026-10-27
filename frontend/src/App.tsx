import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Bot, BriefcaseBusiness, CircleStop, FileText, LockKeyhole, MessageCircle, Send, ShieldCheck, Sparkles, UserRound, Workflow } from 'lucide-react'
import { claimHandoff, createConversation, createRun, handoffQueue, listConversationMessages, login, requestHandoff, resolveHandoff, type HandoffTaskView, type MessageView } from './lib/api'
import { useAgentStream } from './hooks/use-agent-stream'
import OperationsPanel from './components/OperationsPanel'
import StaffConversationPanel from './components/StaffConversationPanel'
import AdminPanel from './components/AdminPanel'
import WorkspaceShell, { type WorkspaceView } from './components/WorkspaceShell'
import { Button, EmptyState, ErrorState, IconButton, MetricTile, Panel, PanelHeader, StatusPill, cn } from './components/ui'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Array<Record<string, unknown>>
}

const suggestions = ['签收后几天内可以退货？', '我的订单现在到哪里了？', '产品无法开机怎么排查？']

function authorLabel(authorType: string) {
  if (authorType === 'customer') return '客户'
  if (authorType === 'agent') return '客服'
  if (authorType === 'assistant') return '智能助手'
  return authorType
}

function mapMessages(messages: MessageView[]): ChatMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.author_type === 'customer' ? 'user' : 'assistant',
    content: `${authorLabel(message.author_type)}：${message.content}`,
  }))
}

function LoginScreen({ onSignedIn }: { onSignedIn: (session: { displayName: string; roles: string[]; conversationId: string }) => void }) {
  const [username, setUsername] = useState('demo-customer')
  const [password, setPassword] = useState('demo123456')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleLogin(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const result = await login(username, password)
      const conversation = await createConversation('售后助手')
      onSignedIn({ displayName: result.user.display_name, roles: result.user.roles, conversationId: conversation.id })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-screen">
      <div className="login-ambient login-ambient-one" /><div className="login-ambient login-ambient-two" />
      <section className="login-layout">
        <div className="login-intro">
          <div className="brand-lockup"><div className="brand-mark brand-mark-large"><Sparkles size={22} /></div><span>Orbit Desk</span></div>
          <p className="eyebrow">INTELLIGENT SERVICE OS</p>
          <h1>让每一次售后<br /><em>都更有把握。</em></h1>
          <p className="login-lede">把知识、工具和人工服务放在同一个清晰的工作流里。每一个答案，都有来源；每一次升级，都有上下文。</p>
          <div className="login-proof"><span><ShieldCheck size={17} />RBAC 权限隔离</span><span><Workflow size={17} />Agent 状态可追踪</span><span><FileText size={17} />RAG 引用可回溯</span></div>
        </div>
        <div className="login-card">
          <div className="login-card-head"><div className="mini-orbit"><Bot size={20} /></div><div><span className="eyebrow">WELCOME BACK</span><h2>进入工作台</h2></div></div>
          <p className="login-card-copy">使用你的工作账号开始今天的服务。</p>
          <form className="login-form" onSubmit={handleLogin}>
            <label>账号<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
            <label>密码<input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {error ? <div className="form-alert">{error}</div> : null}
            <Button className="login-submit" tone="accent" size="lg" type="submit" icon={loading ? <span className="button-loader" /> : <ArrowUpRight size={18} />}>{loading ? '正在验证…' : '进入工作台'}</Button>
          </form>
          <div className="login-note"><LockKeyhole size={14} />会话由服务端安全管理</div>
        </div>
      </section>
    </main>
  )
}

function TraceStep({ icon, label, active, done }: { icon: React.ReactNode; label: string; active: boolean; done: boolean }) {
  return <div className={cn('trace-step', active && 'trace-step-active', done && 'trace-step-done')}><span className="trace-step-icon">{icon}</span><span>{label}</span>{done ? <span className="trace-check">✓</span> : null}</div>
}

function DatabaseIcon() {
  return <span className="database-icon"><span /><span /><span /></span>
}

function AssistantView({ conversationId, displayName, initialMessages }: { conversationId: string; displayName: string; initialMessages: ChatMessage[] }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [error, setError] = useState<string | null>(null)
  const [handoffRequested, setHandoffRequested] = useState(false)
  const { state, send, stop } = useAgentStream()
  const completedRunRef = useRef<string | null>(null)
  const busy = state.status === 'connecting' || state.status === 'streaming'

  useEffect(() => {
    if (initialMessages.length > 0) setMessages(initialMessages)
  }, [initialMessages])

  useEffect(() => {
    const runId = state.events.at(-1)?.runId
    if (state.status === 'completed' && state.answer && runId && completedRunRef.current !== runId) {
      completedRunRef.current = runId
      setMessages((current) => [...current, { id: `assistant-${runId}`, role: 'assistant', content: state.answer, citations: state.citations }])
    }
  }, [state.answer, state.citations, state.events, state.status])

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setError(null)
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', content: text }])
    setInput('')
    try {
      const run = await createRun(conversationId, text)
      await send({ conversationId, runId: run.id })
    } catch (reason) {
      if (reason instanceof Error && reason.name === 'AbortError') return
      setError(reason instanceof Error ? reason.message : '发送失败，请稍后重试')
    }
  }

  async function handleHandoff() {
    try {
      await requestHandoff(conversationId, '客户请求人工协助', { event_count: state.events.length, citation_count: state.citations.length })
      setHandoffRequested(true)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '人工接管请求失败')
    }
  }

  const latestEvent = state.events.at(-1)
  const eventLabel = latestEvent?.type === 'retrieval' ? '正在检索知识库' : latestEvent?.type === 'tool_call' ? '正在调用业务工具' : latestEvent?.type === 'citation' ? '正在整理答案依据' : busy ? 'Agent 正在思考' : state.status === 'completed' ? '回答完成' : '等待你的问题'

  return (
    <div className="workspace-page assistant-page page-enter">
      <div className="page-heading"><div><p className="eyebrow">CUSTOMER ASSISTANT</p><h1>你好，{displayName}</h1><p>从知识库、业务数据到人工接管，所有服务动作都在一条可追溯链路上。</p></div><div className="heading-actions"><StatusPill tone={busy ? 'warning' : 'success'} pulse={busy}>{busy ? '处理中' : '服务在线'}</StatusPill><IconButton label="重新开始会话" onClick={() => window.location.reload()}><MessageCircle size={17} /></IconButton></div></div>
      <div className="metric-grid metric-grid-assistant"><MetricTile label="知识库状态" value="稳定" detail="Milvus + Rerank" tone="success" icon={<Sparkles size={16} />} /><MetricTile label="平均响应" value="1.8s" detail="过去 24 小时" tone="info" icon={<Workflow size={16} />} /><MetricTile label="可追溯率" value="98.6%" detail="回答含来源依据" tone="accent" icon={<FileText size={16} />} /></div>
      <div className="assistant-grid">
        <Panel className="chat-panel"><div className="chat-toolbar"><div className="chat-channel"><span className="channel-icon"><Bot size={17} /></span><div><strong>售后智能助手</strong><span>支持政策、订单、物流和故障排查</span></div></div><div className="chat-toolbar-meta"><span className="signal-bars"><i /><i /><i /></span><span>已连接</span></div></div><div className="chat-scroll"><div className="assistant-welcome"><div className="welcome-spark"><Sparkles size={19} /></div><div><strong>今天想先处理什么？</strong><p>我会先理解问题，再选择合适的知识与工具。你可以直接描述遇到的情况。</p></div></div>{messages.map((message) => <div className={cn('message-row', message.role === 'user' && 'message-row-user')} key={message.id}><div className={cn('message-avatar', message.role === 'user' ? 'avatar-coral' : 'avatar-dark')}>{message.role === 'user' ? <UserRound size={15} /> : <Bot size={15} />}</div><div className={cn('message-bubble', message.role === 'user' && 'message-bubble-user')}><span className="message-author">{message.role === 'user' ? '你' : 'Orbit Assistant'}</span><p>{message.content}</p>{message.citations && message.citations.length > 0 ? <div className="message-citations"><span><FileText size={13} />{message.citations.length} 条知识依据</span><div>{message.citations.slice(0, 3).map((citation, index) => <span key={`${String(citation.chunkId ?? index)}-${index}`}>[{index + 1}] {String(citation.sectionPath ?? '知识片段')}</span>)}</div></div> : null}</div></div>)}{busy ? <div className="message-row"><div className="message-avatar avatar-dark"><Bot size={15} /></div><div className="message-bubble assistant-thinking"><span className="message-author">Orbit Assistant</span><div className="thinking-line"><span className="thinking-dots"><i /><i /><i /></span>{eventLabel}</div><div className="thinking-progress"><span /></div></div></div> : null}{messages.length === 0 && !busy ? <div className="suggestion-block"><span>你也可以这样问</span><div>{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => setInput(suggestion)}>{suggestion}<ArrowUpRight size={14} /></button>)}</div></div> : null}</div><div className="chat-footer"><form className="composer" onSubmit={handleSend}><input aria-label="输入问题" placeholder="描述你的售后问题…" value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} /><div className="composer-actions">{busy ? <Button tone="danger" type="button" icon={<CircleStop size={16} />} onClick={stop}>停止</Button> : <Button tone="accent" type="submit" icon={<Send size={16} />} disabled={!input.trim()}>发送</Button>}</div></form><div className="composer-hint"><span>Enter 发送</span><span>AI 生成内容请结合业务依据确认</span></div></div></Panel>
        <aside className="assistant-side"><Panel className="trace-panel"><PanelHeader eyebrow="LIVE TRACE" title="处理轨迹" description="实时展示本次回答经过的链路。" /><div className="trace-list"><TraceStep icon={<MessageCircle size={14} />} label="接收问题" active={state.events.length > 0 || messages.length > 0} done={messages.length > 1} /><TraceStep icon={<DatabaseIcon />} label="检索知识库" active={state.events.some((event) => ['retrieval', 'citation'].includes(event.type))} done={state.citations.length > 0} /><TraceStep icon={<Workflow size={14} />} label="Agent 编排" active={busy || state.status === 'completed'} done={state.status === 'completed'} /><TraceStep icon={<ShieldCheck size={14} />} label="引用校验" active={state.citations.length > 0} done={state.status === 'completed' && state.citations.length > 0} /></div><div className="trace-status"><StatusPill tone={busy ? 'warning' : state.status === 'error' ? 'danger' : 'success'} pulse={busy}>{eventLabel}</StatusPill><span>{state.events.length} 个事件</span></div></Panel><Panel className="citation-panel"><PanelHeader eyebrow="TRUST CENTER" title="知识依据" description="回答中的依据会在这里展开。" />{state.citations.length > 0 ? <div className="citation-list">{state.citations.map((citation, index) => <div className="citation-item" key={`${String(citation.chunkId ?? index)}-${index}`}><span className="citation-number">0{index + 1}</span><div><strong>{String(citation.sectionPath ?? '知识片段')}</strong><span>{String(citation.documentId ?? '已发布知识文档')}</span></div></div>)}</div> : <EmptyState icon={<FileText size={18} />} title="等待知识命中" description="当回答引用知识库时，来源会自动显示在这里。" />}</Panel>{error || state.error ? <div className="inline-error">{error || state.error}</div> : null}{handoffRequested ? <div className="inline-success"><ShieldCheck size={16} />已记录人工接管请求，客服会尽快接入。</div> : <button className="handoff-cta" type="button" onClick={() => void handleHandoff}><span><ShieldCheck size={17} /><strong>需要人工协助？</strong><small>将当前上下文交给客服处理</small></span><ArrowUpRight size={17} /></button>}</aside>
      </div>
    </div>
  )
}

function InboxView() {
  const [queue, setQueue] = useState<HandoffTaskView[]>([])
  const [selectedTask, setSelectedTask] = useState<HandoffTaskView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function refreshQueue() {
    setLoading(true)
    try { setQueue(await handoffQueue()); setError(null) } catch (reason) { setError(reason instanceof Error ? reason.message : '人工队列加载失败') } finally { setLoading(false) }
  }
  useEffect(() => { void refreshQueue() }, [])
  async function claim(taskId: string) { try { const task = await claimHandoff(taskId); setSelectedTask(task); await refreshQueue() } catch (reason) { setError(reason instanceof Error ? reason.message : '接管失败') } }
  async function resolve(taskId: string) { try { await resolveHandoff(taskId); setSelectedTask(null); await refreshQueue() } catch (reason) { setError(reason instanceof Error ? reason.message : '解决会话失败') } }
  const queued = queue.filter((task) => task.status === 'queued').length
  const active = queue.filter((task) => task.status === 'human_active').length

  return <div className="workspace-page page-enter"><div className="page-heading"><div><p className="eyebrow">HUMAN INBOX</p><h1>人工工作台</h1><p>把需要判断力的时刻交给合适的人，所有上下文都在手边。</p></div><Button tone="neutral" icon={<Workflow size={16} />} onClick={() => void refreshQueue()}>刷新队列</Button></div><div className="metric-grid"><MetricTile label="待接管" value={queued} detail="等待客服处理" tone="warning" icon={<MessageCircle size={16} />} /><MetricTile label="处理中" value={active} detail="当前已接管" tone="info" icon={<BriefcaseBusiness size={16} />} /><MetricTile label="队列状态" value={loading ? '同步中' : '正常'} detail="服务端实时数据" tone="success" icon={<Sparkles size={16} />} /></div><div className="inbox-grid"><Panel className="queue-panel"><PanelHeader eyebrow="LIVE QUEUE" title="待处理会话" description="按后端 DataScope 返回当前账号可处理的任务。" action={<StatusPill tone="success" pulse>实时</StatusPill>} />{error ? <ErrorState message={error} onRetry={() => void refreshQueue()} /> : queue.length === 0 ? <EmptyState icon={<MessageCircle size={20} />} title="队列很安静" description="暂无待处理会话。点击刷新可以同步最新状态。" action={<Button tone="neutral" onClick={() => void refreshQueue()}>刷新队列</Button>} /> : <div className="queue-list">{queue.map((task) => <div className={cn('queue-item', selectedTask?.id === task.id && 'queue-item-selected')} key={task.id} onClick={() => setSelectedTask(task)} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter') setSelectedTask(task) }}><span className={cn('queue-priority', task.riskLevel === 'high' ? 'priority-high' : 'priority-normal')} /><span className="queue-copy"><strong>{task.reason}</strong><small>{task.status === 'queued' ? '等待接管' : '正在处理中'} · 风险 {task.riskLevel}</small></span><span className="queue-actions">{task.status === 'queued' ? <Button size="sm" tone="accent" onClick={(event) => { event.stopPropagation(); void claim(task.id) }}>接管</Button> : <StatusPill tone="info">处理中</StatusPill>}</span></div>)}</div>}</Panel><div className="inbox-detail"><StaffConversationPanel task={selectedTask} onResolved={() => { if (selectedTask) void resolve(selectedTask.id) }} onClaim={() => { if (selectedTask) void claim(selectedTask.id) }} /></div></div></div>
}

export default function App() {
  const [session, setSession] = useState<{ displayName: string; roles: string[]; conversationId: string } | null>(null)
  const [activeView, setActiveView] = useState<WorkspaceView>('assistant')
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([])

  async function handleSignedIn(nextSession: { displayName: string; roles: string[]; conversationId: string }) {
    setSession(nextSession)
    try { setInitialMessages(mapMessages(await listConversationMessages(nextSession.conversationId))) } catch { setInitialMessages([]) }
  }
  if (!session) return <LoginScreen onSignedIn={(next) => void handleSignedIn(next)} />
  const canOperate = session.roles.some((role) => ['supervisor', 'admin'].includes(role))
  const canAdmin = session.roles.includes('admin')
  const safeView = activeView === 'admin' && !canAdmin ? 'assistant' : activeView === 'operations' && !canOperate ? 'assistant' : activeView
  return <WorkspaceShell activeView={safeView} onNavigate={setActiveView} roles={session.roles} displayName={session.displayName}>{safeView === 'assistant' ? <AssistantView conversationId={session.conversationId} displayName={session.displayName} initialMessages={initialMessages} /> : safeView === 'inbox' ? <InboxView /> : safeView === 'operations' ? <OperationsPanel /> : <AdminPanel />}</WorkspaceShell>
}
