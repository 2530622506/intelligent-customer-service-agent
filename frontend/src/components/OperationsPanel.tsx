import { useEffect, useState } from 'react'
import { Database, FileUp, GitBranch, Play, Plus, RefreshCw } from 'lucide-react'
import {
  createEvaluationDataset,
  createEvaluationRun,
  createKnowledgeEntity,
  executeEvaluationRun,
  listEvaluationDatasets,
  listEvaluationScores,
  listKnowledgeEntities,
  listKnowledgeRelations,
  publishKnowledgeEntity,
  uploadKnowledgeDocument,
  type EvaluationDatasetView,
  type KnowledgeEntityView,
  type KnowledgeRelationView,
} from '../lib/api'

export default function OperationsPanel() {
  const [entities, setEntities] = useState<KnowledgeEntityView[]>([])
  const [datasets, setDatasets] = useState<EvaluationDatasetView[]>([])
  const [relations, setRelations] = useState<KnowledgeRelationView[]>([])
  const [scores, setScores] = useState<Array<{ metric: string; value: number; comment: string | null }>>([])
  const [error, setError] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)

  async function refresh() {
    try {
      const [nextEntities, nextDatasets, nextRelations] = await Promise.all([listKnowledgeEntities(), listEvaluationDatasets(), listKnowledgeRelations()])
      setEntities(nextEntities)
      setDatasets(nextDatasets)
      setRelations(nextRelations)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '运营数据加载失败')
    }
  }

  useEffect(() => { void refresh() }, [])

  async function runDataset(datasetId: string) {
    const run = await createEvaluationRun(datasetId)
    const completed = await executeEvaluationRun(run.id)
    setScores(await listEvaluationScores(completed.id))
  }

  async function uploadDocument(file: File) {
    try {
      const result = await uploadKnowledgeDocument(file)
      setUploadStatus(`任务 ${result.taskId.slice(0, 8)} 已提交：${result.status}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '文档上传失败')
    }
  }

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2"><div className="flex items-center gap-3"><FileUp size={18} className="text-cyan-300" /><div><h2 className="font-semibold">知识文档</h2><p className="mt-1 text-sm text-slate-400">原始文件进入 RustFS，解析任务由 MinerU Cloud Worker 处理。</p></div></div><label className="mt-4 flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-400 hover:border-cyan-400"><input className="sr-only" type="file" accept=".md,.txt,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.html" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadDocument(file) }} />选择文档上传</label>{uploadStatus ? <p className="mt-3 text-xs text-emerald-300">{uploadStatus}</p> : null}</div>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between"><div><h2 className="font-semibold">知识实体</h2><p className="mt-1 text-sm text-slate-400">候选实体先入 PostgreSQL，发布后才进入运营状态。</p></div><button className="flex items-center gap-1 rounded-lg bg-cyan-400 px-3 py-2 text-sm text-slate-950" onClick={() => void createKnowledgeEntity(`售后实体-${Date.now()}`, 'policy').then(refresh)}><Plus size={15} />新增</button></div>
        <div className="mt-4 space-y-2">{entities.map((entity) => <div className="flex items-center justify-between rounded-lg border border-slate-800 p-3" key={entity.id}><div className="flex items-center gap-3"><Database size={16} className="text-cyan-300" /><div><p className="text-sm">{entity.name}</p><p className="text-xs text-slate-500">{entity.entity_type}</p></div></div>{entity.status === 'candidate' ? <button className="text-xs text-cyan-300" onClick={() => void publishKnowledgeEntity(entity.id).then(refresh)}>发布</button> : <span className="text-xs text-emerald-300">已发布</span>}</div>)}</div>
      </div>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">评测数据集</h2><p className="mt-1 text-sm text-slate-400">数据集、用例和运行记录由后端保存。</p></div><button className="flex items-center gap-1 rounded-lg bg-cyan-400 px-3 py-2 text-sm text-slate-950" onClick={() => void createEvaluationDataset(`售后评测集-${Date.now()}`).then(refresh)}><Plus size={15} />新增</button></div><div className="mt-4 space-y-2">{datasets.map((dataset) => <div className="rounded-lg border border-slate-800 p-3" key={dataset.id}><p className="text-sm">{dataset.name}</p><p className="text-xs text-slate-500">{dataset.status}</p></div>)}</div><button className="mt-4 flex items-center gap-1 text-xs text-slate-400" onClick={() => void refresh()}><RefreshCw size={14} />刷新</button></div>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2"><div className="flex items-center justify-between"><div><h2 className="font-semibold">关系投影</h2><p className="mt-1 text-sm text-slate-400">关系状态由 PostgreSQL 治理，发布后投影到 Neo4j。</p></div><GitBranch size={18} className="text-cyan-300" /></div><div className="mt-4 grid gap-2 md:grid-cols-2">{relations.map((relation) => <div className="rounded-lg border border-slate-800 p-3" key={relation.id}><p className="text-sm">{relation.relation_type}</p><p className="text-xs text-slate-500">{relation.source_entity_id.slice(0, 8)} → {relation.target_entity_id.slice(0, 8)} · {relation.status}</p></div>)}</div></div>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2"><h2 className="font-semibold">评测评分</h2><div className="mt-4 flex flex-wrap gap-3">{datasets.map((dataset) => <button key={dataset.id} className="flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300" onClick={() => void runDataset(dataset.id)}><Play size={14} />运行 {dataset.name}</button>)}</div>{scores.length ? <div className="mt-4 grid gap-2 md:grid-cols-3">{scores.map((score, index) => <div className="rounded-lg border border-slate-800 p-3" key={`${score.metric}-${index}`}><p className="text-xs text-slate-400">{score.metric}</p><p className="mt-1 text-xl font-semibold text-emerald-300">{score.value.toFixed(2)}</p></div>)}</div> : <p className="mt-4 text-sm text-slate-500">运行评测后显示评分。</p>}</div>
      {error ? <p className="lg:col-span-2 text-sm text-rose-300">{error}</p> : null}
    </section>
  )
}
