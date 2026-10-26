import { useEffect, useState } from 'react'
import { Database, Plus, RefreshCw } from 'lucide-react'
import {
  createEvaluationDataset,
  createKnowledgeEntity,
  listEvaluationDatasets,
  listKnowledgeEntities,
  publishKnowledgeEntity,
  type EvaluationDatasetView,
  type KnowledgeEntityView,
} from '../lib/api'

export default function OperationsPanel() {
  const [entities, setEntities] = useState<KnowledgeEntityView[]>([])
  const [datasets, setDatasets] = useState<EvaluationDatasetView[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    try {
      const [nextEntities, nextDatasets] = await Promise.all([listKnowledgeEntities(), listEvaluationDatasets()])
      setEntities(nextEntities)
      setDatasets(nextDatasets)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '运营数据加载失败')
    }
  }

  useEffect(() => { void refresh() }, [])

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between"><div><h2 className="font-semibold">知识实体</h2><p className="mt-1 text-sm text-slate-400">候选实体先入 PostgreSQL，发布后才进入运营状态。</p></div><button className="flex items-center gap-1 rounded-lg bg-cyan-400 px-3 py-2 text-sm text-slate-950" onClick={() => void createKnowledgeEntity(`售后实体-${Date.now()}`, 'policy').then(refresh)}><Plus size={15} />新增</button></div>
        <div className="mt-4 space-y-2">{entities.map((entity) => <div className="flex items-center justify-between rounded-lg border border-slate-800 p-3" key={entity.id}><div className="flex items-center gap-3"><Database size={16} className="text-cyan-300" /><div><p className="text-sm">{entity.name}</p><p className="text-xs text-slate-500">{entity.entity_type}</p></div></div>{entity.status === 'candidate' ? <button className="text-xs text-cyan-300" onClick={() => void publishKnowledgeEntity(entity.id).then(refresh)}>发布</button> : <span className="text-xs text-emerald-300">已发布</span>}</div>)}</div>
      </div>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">评测数据集</h2><p className="mt-1 text-sm text-slate-400">数据集、用例和运行记录由后端保存。</p></div><button className="flex items-center gap-1 rounded-lg bg-cyan-400 px-3 py-2 text-sm text-slate-950" onClick={() => void createEvaluationDataset(`售后评测集-${Date.now()}`).then(refresh)}><Plus size={15} />新增</button></div><div className="mt-4 space-y-2">{datasets.map((dataset) => <div className="rounded-lg border border-slate-800 p-3" key={dataset.id}><p className="text-sm">{dataset.name}</p><p className="text-xs text-slate-500">{dataset.status}</p></div>)}</div><button className="mt-4 flex items-center gap-1 text-xs text-slate-400" onClick={() => void refresh()}><RefreshCw size={14} />刷新</button></div>
      {error ? <p className="lg:col-span-2 text-sm text-rose-300">{error}</p> : null}
    </section>
  )
}
