import { useState } from 'react'
import { Bot, BriefcaseBusiness, Database, Menu, PanelLeftClose, Settings2, ShieldCheck, Sparkles, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { IconButton, cn, StatusPill } from './ui'

export type WorkspaceView = 'assistant' | 'inbox' | 'operations' | 'admin'

interface NavItem {
  id: WorkspaceView
  label: string
  description: string
  icon: ReactNode
}

interface WorkspaceShellProps {
  activeView: WorkspaceView
  onNavigate: (view: WorkspaceView) => void
  roles: string[]
  displayName: string
  children: ReactNode
}

const navItems: NavItem[] = [
  { id: 'assistant', label: '智能助手', description: '客户对话与知识依据', icon: <Bot size={18} /> },
  { id: 'inbox', label: '人工工作台', description: '接管与客服队列', icon: <BriefcaseBusiness size={18} /> },
  { id: 'operations', label: '知识运营', description: '文档、图谱与评测', icon: <Database size={18} /> },
  { id: 'admin', label: '系统配置', description: '用户、角色与权限', icon: <ShieldCheck size={18} /> },
]

function roleLabel(roles: string[]) {
  if (roles.includes('admin')) return '系统管理员'
  if (roles.includes('supervisor')) return '客服主管'
  if (roles.includes('agent')) return '客服专员'
  return '客户'
}

export default function WorkspaceShell({ activeView, onNavigate, roles, displayName, children }: WorkspaceShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const canStaff = roles.some((role) => ['agent', 'supervisor', 'admin'].includes(role))
  const canOperate = roles.some((role) => ['supervisor', 'admin'].includes(role))
  const canAdmin = roles.includes('admin')
  const visibleItems = navItems.filter((item) => item.id === 'assistant' || (item.id === 'inbox' && canStaff) || (item.id === 'operations' && canOperate) || (item.id === 'admin' && canAdmin))

  function navigate(view: WorkspaceView) {
    onNavigate(view)
    setMobileOpen(false)
  }

  return (
    <div className="app-shell">
      <aside className={cn('sidebar', mobileOpen && 'sidebar-open')}>
        <div className="sidebar-brand">
          <div className="brand-mark"><Sparkles size={18} /></div>
          <div><strong>Orbit Desk</strong><span>智能服务中枢</span></div>
          <IconButton className="mobile-close" label="关闭导航" onClick={() => setMobileOpen(false)}><X size={18} /></IconButton>
        </div>
        <div className="sidebar-context"><span className="context-kicker">当前空间</span><strong>售后服务中心</strong><span className="context-status"><span className="live-dot" />服务在线</span></div>
        <nav className="sidebar-nav" aria-label="主导航">
          <span className="nav-label">工作区</span>
          {visibleItems.map((item) => <button className={cn('nav-item', activeView === item.id && 'nav-item-active')} key={item.id} type="button" onClick={() => navigate(item.id)}><span className="nav-icon">{item.icon}</span><span><strong>{item.label}</strong><small>{item.description}</small></span>{item.id === 'inbox' ? <span className="nav-badge">LIVE</span> : null}</button>)}
        </nav>
        <div className="sidebar-footer"><div className="profile-row"><div className="avatar avatar-coral">{displayName.slice(0, 1).toUpperCase()}</div><div className="profile-copy"><strong>{displayName}</strong><span>{roleLabel(roles)}</span></div><Settings2 size={15} /></div><div className="system-health"><span className="health-ring" /><div><strong>系统运行稳定</strong><span>API · RAG · SSE 正常</span></div></div></div>
      </aside>
      {mobileOpen ? <button className="sidebar-backdrop" type="button" aria-label="关闭导航" onClick={() => setMobileOpen(false)} /> : null}
      <main className="main-area">
        <header className="topbar"><div className="topbar-left"><IconButton className="mobile-menu" label="打开导航" onClick={() => setMobileOpen(true)}><Menu size={20} /></IconButton><div className="breadcrumb"><span>Orbit Desk</span><span>/</span><strong>{navItems.find((item) => item.id === activeView)?.label}</strong></div></div><div className="topbar-actions"><StatusPill tone="success" pulse>在线</StatusPill><span className="topbar-divider" /><span className="topbar-date">10 月 27 日 · 周二</span></div></header>
        <div className="page-content">{children}</div>
      </main>
    </div>
  )
}

export function CollapsedSidebarHint() {
  return <PanelLeftClose size={16} />
}
