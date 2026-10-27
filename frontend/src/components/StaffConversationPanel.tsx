import { FormEvent, useEffect, useState } from 'react'
import { CheckCircle2, MessageSquare, Send, UserRound } from 'lucide-react'
import { listConversationMessages, sendStaffMessage, type HandoffTaskView, type MessageView } from '../lib/api'
import { Button, EmptyState, ErrorState, Panel, PanelHeader, StatusPill, cn } from './ui'

interface Props {
  task: HandoffTaskView | null
  onResolved?: () => void
  onClaim?: () => void
}

export default function StaffConversationPanel({ task, onResolved, onClaim }: Props) {
  const [messages, setMessages] = useState<MessageView[]>([])
  const [content, setContent] = useState('')
  const [internal, setInternal] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!task) { setMessages([]); return }
    setError(null)
    void listConversationMessages(task.conversationId).then(setMessages).catch((reason) => setError(reason instanceof Error ? reason.message : '消息加载失败'))
  }, [task])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!task || !content.trim() || sending) return
    setSending(true)
    try {
      await sendStaffMessage(task.id, content.trim(), internal)
      setContent('')
      setInternal(false)
      setMessages(await listConversationMessages(task.conversationId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '消息发送失败')
    } finally { setSending(false) }
  }

  if (!task) return <Panel className="conversation-panel conversation-empty"><EmptyState icon={<MessageSquare size={20} />} title="选择一条会话" description="从左侧队列选择任务，查看上下文并开始处理。" /></Panel>
  return <Panel className="conversation-panel"><PanelHeader eyebrow="CONVERSATION" title="会话详情" description={`任务 ${task.id.slice(0, 8)} · ${task.reason}`} action={<StatusPill tone={task.status === 'human_active' ? 'info' : 'warning'}>{task.status === 'human_active' ? '已接管' : '待接管'}</StatusPill>} /><div className="conversation-meta"><span><UserRound size={14} />客户会话</span><span>风险：<strong className={task.riskLevel === 'high' ? 'text-danger' : ''}>{task.riskLevel}</strong></span></div>{error ? <ErrorState message={error} /> : <div className="conversation-messages">{messages.length === 0 ? <EmptyState icon={<MessageSquare size={18} />} title="暂无消息" description="这条会话还没有可展示的上下文。" /> : messages.map((message) => <div className={cn('staff-message', message.author_type === 'agent' && 'staff-message-agent')} key={message.id}><div className="staff-message-head"><span>{message.author_type}</span><small>{message.status}</small></div><p>{message.content}</p></div>)}</div>}<form className="staff-composer" onSubmit={submit}><textarea aria-label="客服消息" placeholder={internal ? '写一条内部备注…' : '回复客户…'} value={content} onChange={(event) => setContent(event.target.value)} rows={3} /><div className="staff-composer-footer"><button className={cn('internal-toggle', internal && 'internal-toggle-active')} type="button" onClick={() => setInternal((current) => !current)}>内部备注</button><div className="staff-actions">{task.status === 'queued' ? <Button tone="accent" type="button" onClick={onClaim}>接管会话</Button> : <Button tone="success" type="button" onClick={onResolved} icon={<CheckCircle2 size={15} />}>完成处理</Button>}<Button tone={internal ? 'warning' : 'accent'} type="submit" disabled={!content.trim() || sending} icon={<Send size={15} />}>{sending ? '发送中…' : internal ? '保存备注' : '发送回复'}</Button></div></div></form></Panel>
}
