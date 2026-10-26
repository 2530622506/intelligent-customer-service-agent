import { FormEvent, useState } from 'react'
import { CircleStop, LogIn, Send, ShieldCheck } from 'lucide-react'
import { createConversation, createRun, login } from './lib/api'
import { useAgentStream } from './hooks/use-agent-stream'

function App() {
  const [username, setUsername] = useState('demo-customer')
  const [password, setPassword] = useState('demo123456')
  const [signedIn, setSignedIn] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { state, send, stop } = useAgentStream()

  async function handleLogin(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await login(username, password)
      const conversation = await createConversation('售后助手')
      setConversationId(conversation.id)
      setSignedIn(true)
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : '登录失败')
    }
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    if (!input.trim() || !conversationId || state.status === 'connecting' || state.status === 'streaming') return
    setError(null)
    try {
      const run = await createRun(conversationId, input.trim())
      setInput('')
      await send({ conversationId, runId: run.id })
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : '发送失败')
    }
  }

  if (!signedIn) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
        <section className="mx-auto max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
          <div className="flex items-center gap-3 text-cyan-300"><ShieldCheck size={22} /><span className="text-sm font-semibold">售后服务工作台</span></div>
          <h1 className="mt-6 text-3xl font-semibold tracking-tight">登录售后助手</h1>
          <p className="mt-3 text-sm text-slate-400">使用演示账号体验受控 Agent 对话链路。</p>
          <form className="mt-8 space-y-4" onSubmit={handleLogin}>
            <label className="block text-sm text-slate-300">账号<input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 outline-none focus:border-cyan-400" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
            <label className="block text-sm text-slate-300">密码<input type="password" className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 outline-none focus:border-cyan-400" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {error ? <p className="text-sm text-rose-300">{error}</p> : null}
            <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2.5 font-medium text-slate-950 transition hover:bg-cyan-300" type="submit"><LogIn size={17} />进入工作台</button>
          </form>
        </section>
      </main>
    )
  }

  const busy = state.status === 'connecting' || state.status === 'streaming'
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between"><div><p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-300">Customer Service Agent</p><h1 className="mt-1 text-lg font-semibold">售后助手</h1></div><span className="rounded-full border border-emerald-400/30 px-3 py-1 text-xs text-emerald-300">客户模式</span></div>
      </header>
      <section className="mx-auto flex min-h-[calc(100vh-81px)] max-w-6xl flex-col px-6 py-8">
        <div className="flex-1 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4"><div><h2 className="font-semibold">今天需要什么帮助？</h2><p className="mt-1 text-sm text-slate-400">答案会展示 Agent 处理状态和可追溯依据。</p></div><span className="text-xs text-slate-500">{state.status}</span></div>
          <div className="space-y-5 py-8">
            {state.answer ? <div className="max-w-3xl rounded-xl border border-slate-700 bg-slate-950/80 p-5 leading-7 text-slate-200"><p className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-300">Agent 回复</p>{state.answer}</div> : <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">可以询问退换货政策、订单物流或产品故障排查。</div>}
            {state.events.length > 0 ? <div className="text-xs text-slate-500">已接收 {state.events.length} 个运行事件</div> : null}
            {state.error || error ? <p className="text-sm text-rose-300">{state.error || error}</p> : null}
          </div>
        </div>
        <form className="mt-5 flex gap-3" onSubmit={handleSend}><input className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 outline-none focus:border-cyan-400" placeholder="例如：签收后几天内可以退货？" value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} />{busy ? <button type="button" onClick={stop} className="flex items-center gap-2 rounded-xl border border-rose-400/40 px-4 py-3 text-rose-300"><CircleStop size={18} />停止</button> : <button type="submit" className="flex items-center gap-2 rounded-xl bg-cyan-400 px-5 py-3 font-medium text-slate-950"><Send size={18} />发送</button>}</form>
      </section>
    </main>
  )
}

export default App
