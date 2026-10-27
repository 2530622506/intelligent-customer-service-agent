import { useEffect, useState } from 'react'
import { ShieldCheck, Users } from 'lucide-react'
import {
  assignUserRoles,
  listAdminPermissions,
  listAdminRoles,
  listAdminUsers,
  type AdminRoleView,
  type AdminUserView,
} from '../lib/api'

export default function AdminPanel() {
  const [users, setUsers] = useState<AdminUserView[]>([])
  const [roles, setRoles] = useState<AdminRoleView[]>([])
  const [permissionCount, setPermissionCount] = useState(0)
  const [selectedRole, setSelectedRole] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    try {
      const [nextUsers, nextRoles, permissions] = await Promise.all([
        listAdminUsers(),
        listAdminRoles(),
        listAdminPermissions(),
      ])
      setUsers(nextUsers)
      setRoles(nextRoles)
      setPermissionCount(permissions.length)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '管理员配置加载失败')
    }
  }

  useEffect(() => { void refresh() }, [])

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center gap-3"><ShieldCheck size={18} className="text-cyan-300" /><div><h2 className="font-semibold">系统配置</h2><p className="mt-1 text-sm text-slate-400">RBAC 配置由服务端强制校验，前端只展示可操作范围。</p></div></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold">用户与角色</h3><span className="text-xs text-slate-500">{users.length} 个用户 · {roles.length} 个角色</span></div><div className="space-y-2">{users.map((user) => <div className="flex items-center justify-between rounded-lg border border-slate-800 p-3" key={user.id}><div className="flex items-center gap-3"><Users size={15} className="text-slate-500" /><div><p className="text-sm">{user.displayName}</p><p className="text-xs text-slate-500">{user.username} · {user.status}</p></div></div><div className="flex gap-2"><select className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs" value={selectedRole[user.id] ?? ''} onChange={(event) => setSelectedRole((current) => ({ ...current, [user.id]: event.target.value }))}><option value="">选择角色</option>{roles.map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}</select><button className="rounded-lg border border-slate-700 px-2 py-1.5 text-xs text-cyan-300" onClick={() => { const role = selectedRole[user.id]; if (role) void assignUserRoles(user.id, [role]).then(refresh).catch((reason) => setError(reason instanceof Error ? reason.message : '角色分配失败')) }}>保存</button></div></div>)}</div></div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4"><h3 className="text-sm font-semibold">权限概览</h3><p className="mt-3 text-3xl font-semibold text-cyan-300">{permissionCount}</p><p className="mt-1 text-xs text-slate-500">已注册服务端权限</p><button className="mt-5 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300" onClick={() => void refresh()}>刷新配置</button></div>
      </div>
      {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
    </section>
  )
}
