import { FormEvent, useEffect, useState } from 'react'
import { MessageSquare, Send } from 'lucide-react'
import { listConversationMessages, sendStaffMessage, type HandoffTaskView, type MessageView } from '../lib/api'

interface Props {
  task: HandoffTaskView | null
}

export default function StaffConversationPanel({ task }: Props) {
  const [messages, setMessages] = useState<MessageView[]>([])
  const [content, setContent] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!task) return
    void listConversationMessages(task.conversationId).then(setMessages).catch((reason) => setError(reason instanceof Error ? reason.message : '消息加载失败'))
  }, [task])

  async function submit(event: FormEvent, internal: boolean) {
    event.preventDefault()
    if (!task || !content.trim()) return
    await sendStaffMessage(task.id, content.trim(), internal)
    setContent('')
    setMessages(await listConversationMessages(task.conversationId))
  }

  if (!task) return <div className="rounded-xl border border-dashed border-slate-700 p-6 text-sm text-slate-500">选择一条人工会话查看上下文。</div>
  return <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"><div className="flex items-center gap-2"><MessageSquare size={16} className="text-cyan-300" /><h3 className="text-sm font-semibold">会话详情</h3></div><div className="mt-3 max-h-52 space-y-2 overflow-auto">{messages.map((message) => <div className="rounded-lg border border-slate-800 p-3 text-sm" key={message.id}><span className="mr-2 text-xs text-cyan-300">{message.author_type}</span>{message.content}</div>)}</div><form className="mt-3 flex gap-2" onSubmit={(event) => void submit(event, false)}><input className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm" placeholder="回复客户" value={content} onChange={(event) => setContent(event.target.value)} /><button className="flex items-center gap-1 rounded-lg bg-cyan-400 px-3 py-2 text-sm text-slate-950" type="submit"><Send size={14} />回复</button><button className="rounded-lg border border-slate-700 px-3 py-2 text-sm" type="button" onClick={(event) => void submit(event, true)}>内部备注</button></form>{error ? <p className="mt-2 text-xs text-rose-300">{error}</p> : null}</section>
}
