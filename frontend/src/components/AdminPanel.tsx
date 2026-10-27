import { useEffect, useState } from 'react'
import { Check, KeyRound, RefreshCw, ShieldCheck, Users } from 'lucide-react'
import { assignUserRoles, listAdminPermissions, listAdminRoles, listAdminUsers, type AdminRoleView, type AdminUserView } from '../lib/api'
import { Button, EmptyState, ErrorState, LoadingState, MetricTile, Panel, PanelHeader } from './ui'

export default function AdminPanel() {
  const [users, setUsers] = useState<AdminUserView[]>([])
  const [roles, setRoles] = useState<AdminRoleView[]>([])
  const [permissionCount, setPermissionCount] = useState(0)
  const [selectedRole, setSelectedRole] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    try { const [nextUsers, nextRoles, permissions] = await Promise.all([listAdminUsers(), listAdminRoles(), listAdminPermissions()]); setUsers(nextUsers); setRoles(nextRoles); setPermissionCount(permissions.length); setError(null) } catch (reason) { setError(reason instanceof Error ? reason.message : '管理员配置加载失败') } finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [])
  async function saveRole(userId: string) { const role = selectedRole[userId]; if (!role) return; setSaving(userId); try { await assignUserRoles(userId, [role]); await refresh() } catch (reason) { setError(reason instanceof Error ? reason.message : '角色分配失败') } finally { setSaving(null) } }

  return <div className="workspace-page page-enter"><div className="page-heading"><div><p className="eyebrow">SYSTEM CONTROL</p><h1>系统配置</h1><p>用清晰的角色、权限和操作边界，守住服务系统的安全底线。</p></div><Button tone="neutral" icon={<RefreshCw size={16} />} onClick={() => void refresh()}>刷新配置</Button></div><div className="metric-grid"><MetricTile label="用户账号" value={users.length} detail="当前系统用户" tone="info" icon={<Users size={16} />} /><MetricTile label="角色模板" value={roles.length} detail="RBAC 角色" tone="accent" icon={<ShieldCheck size={16} />} /><MetricTile label="服务权限" value={permissionCount} detail="后端强制校验" tone="success" icon={<KeyRound size={16} />} /></div>{error ? <ErrorState message={error} onRetry={() => void refresh()} /> : null}{loading ? <Panel><LoadingState label="正在加载权限配置" /></Panel> : <div className="admin-grid"><Panel className="users-panel"><PanelHeader eyebrow="RBAC USERS" title="用户与角色" description="前端只展示和发起操作，权限仍由服务端强制校验。" />{users.length === 0 ? <EmptyState icon={<Users size={19} />} title="暂无用户" description="系统中还没有可管理的用户账号。" /> : <div className="user-list">{users.map((user) => <div className="user-row" key={user.id}><div className="avatar avatar-dark">{user.displayName.slice(0, 1).toUpperCase()}</div><div className="user-copy"><strong>{user.displayName}</strong><span>{user.username} · {user.status}</span></div><div className="role-editor"><select aria-label={`为 ${user.displayName} 选择角色`} value={selectedRole[user.id] ?? ''} onChange={(event) => setSelectedRole((current) => ({ ...current, [user.id]: event.target.value }))}><option value="">选择角色</option>{roles.map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}</select><Button size="sm" tone="accent" disabled={!selectedRole[user.id] || saving === user.id} icon={<Check size={14} />} onClick={() => void saveRole(user.id)}>{saving === user.id ? '保存中…' : '保存'}</Button></div></div>)}</div>}</Panel><Panel className="roles-panel"><PanelHeader eyebrow="ROLE CATALOG" title="角色目录" description="角色定义来自服务端，不在前端复制权限规则。" /><div className="role-list">{roles.map((role) => <div className="role-card" key={role.code}><div className="role-card-icon"><ShieldCheck size={16} /></div><div><strong>{role.name}</strong><span>{role.code}</span><small>{role.description || '服务角色'}</small></div></div>)}</div></Panel></div>}</div>
}
