import { useState, useEffect, useRef, useCallback } from 'react'
import { RefreshCw, Play, Square, Settings, Folder, ArrowRight, Trash2, CheckCircle, AlertCircle, Loader2, Download } from 'lucide-react'

const API = '/api'

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  if (seconds < 60) return Math.round(seconds) + 's'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m < 60) return `${m}m ${s}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

function StatusBadge({ status }) {
  const map = {
    idle:       { color: 'bg-gray-600', text: '空闲' },
    scanning:   { color: 'bg-blue-600 animate-pulse', text: '扫描中' },
    syncing:    { color: 'bg-brand-600 animate-pulse', text: '同步中' },
    deleting:   { color: 'bg-yellow-600 animate-pulse', text: '清理中' },
    done:       { color: 'bg-green-600', text: '完成' },
    error:      { color: 'bg-red-600', text: '错误' },
    cancelled:  { color: 'bg-gray-500', text: '已取消' },
  }
  const s = map[status] || { color: 'bg-gray-600', text: status }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${s.color}`}>{s.text}</span>
  )
}

function ProgressBar({ percent, speed, className = '' }) {
  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex justify-between text-xs text-gray-400">
        <span>{percent.toFixed(1)}%</span>
        <span>{speed}</span>
      </div>
      <div className="w-full bg-surface-3 rounded-full h-2">
        <div
          className="bg-brand-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </div>
    </div>
  )
}

export default function SyncPage() {
  const [config, setConfig] = useState(null)
  const [tasks, setTasks] = useState({})
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [form, setForm] = useState({ webdav_mount: '', local_dest: '', delete_after_sync: false })
  const [manualSource, setManualSource] = useState('')
  const [manualDest, setManualDest] = useState('')
  const eventSourceRef = useRef(null)

  // 加载配置和状态
  const fetchAll = useCallback(async () => {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch(`${API}/sync/config`),
        fetch(`${API}/sync/status`),
      ])
      const cfgData = await cfgRes.json()
      const statusData = await statusRes.json()
      setConfig(cfgData)
      setTasks(statusData.tasks || {})
      setForm({
        webdav_mount: cfgData.webdav_mount || '',
        local_dest: cfgData.local_dest || '',
        delete_after_sync: cfgData.delete_after_sync || false,
      })
    } catch (e) {
      console.error('Failed to load sync data:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // 定时刷新状态 (当有活跃任务时)
  useEffect(() => {
    const hasActive = Object.values(tasks).some(t =>
      ['scanning', 'syncing', 'deleting'].includes(t.status)
    )
    if (!hasActive) return

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API}/sync/status`)
        const data = await res.json()
        setTasks(data.tasks || {})
      } catch {}
    }, 1000)

    return () => clearInterval(timer)
  }, [tasks])

  // SSE 实时进度
  const connectSSE = useCallback((taskName) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`${API}/sync/progress/${encodeURIComponent(taskName)}`)
    eventSourceRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setTasks(prev => ({ ...prev, [taskName]: data }))
        if (['done', 'error', 'cancelled'].includes(data.status)) {
          es.close()
          eventSourceRef.current = null
          setSyncing(false)
        }
      } catch {}
    }
    es.onerror = () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close()
    }
  }, [])

  // 启动同步
  const handleStart = async () => {
    const body = {}
    if (manualSource && manualDest) {
      body.source_dir = manualSource
      body.dest_dir = manualDest
      body.task_name = 'manual'
    } else if (config?.webdav_mount && config?.local_dest) {
      body.task_name = 'default'
    } else {
      alert('请先配置同步路径，或手动指定源/目标目录')
      return
    }

    try {
      setSyncing(true)
      const res = await fetch(`${API}/sync/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        alert(data.detail || '启动失败')
        setSyncing(false)
        return
      }
      // 连接 SSE
      connectSSE(data.task_name || body.task_name)
    } catch (e) {
      alert('启动失败: ' + e.message)
      setSyncing(false)
    }
  }

  // 取消同步
  const handleCancel = async (taskName) => {
    try {
      await fetch(`${API}/sync/cancel/${encodeURIComponent(taskName)}`, { method: 'POST' })
    } catch {}
  }

  // 保存配置
  const handleSaveConfig = async () => {
    try {
      const res = await fetch(`${API}/sync/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (res.ok) {
        const data = await res.json()
        setConfig(data.sync)
        setEditMode(false)
      }
    } catch (e) {
      alert('保存失败: ' + e.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }

  const hasConfig = config?.webdav_mount && config?.local_dest

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">文件同步</h1>
          <p className="text-sm text-gray-500 mt-1">WebDAV 挂载目录 → NAS 本地磁盘</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAll}
            className="p-2 rounded-lg bg-surface-2 hover:bg-surface-3 transition"
            title="刷新"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setEditMode(!editMode)}
            className={`p-2 rounded-lg transition ${editMode ? 'bg-brand-600' : 'bg-surface-2 hover:bg-surface-3'}`}
            title="配置"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 配置编辑 */}
      {editMode && (
        <div className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">全局同步配置</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">WebDAV 挂载路径</label>
              <input
                className="w-full bg-surface-2 rounded-lg px-3 py-2 text-sm border border-surface-3 focus:border-brand-500 outline-none"
                placeholder="/mnt/alist/夸克"
                value={form.webdav_mount}
                onChange={e => setForm(f => ({ ...f, webdav_mount: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">NAS 本地目标路径</label>
              <input
                className="w-full bg-surface-2 rounded-lg px-3 py-2 text-sm border border-surface-3 focus:border-brand-500 outline-none"
                placeholder="/mnt/nas/media"
                value={form.local_dest}
                onChange={e => setForm(f => ({ ...f, local_dest: e.target.value }))}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={form.delete_after_sync}
              onChange={e => setForm(f => ({ ...f, delete_after_sync: e.target.checked }))}
              className="rounded"
            />
            同步后删除源文件 (释放网盘空间)
          </label>
          <div className="flex gap-2">
            <button
              onClick={handleSaveConfig}
              className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 rounded-lg text-sm transition"
            >
              保存
            </button>
            <button
              onClick={() => setEditMode(false)}
              className="px-4 py-1.5 bg-surface-2 hover:bg-surface-3 rounded-lg text-sm transition"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 当前配置概览 */}
      {!editMode && hasConfig && (
        <div className="bg-surface-1 rounded-xl p-4 border border-surface-3">
          <div className="flex items-center gap-3 text-sm">
            <Folder className="w-4 h-4 text-brand-400 shrink-0" />
            <span className="text-gray-400 truncate">{config.webdav_mount}</span>
            <ArrowRight className="w-4 h-4 text-gray-600 shrink-0" />
            <span className="text-gray-400 truncate">{config.local_dest}</span>
            {config.delete_after_sync && (
              <span className="ml-2 text-xs text-yellow-500 flex items-center gap-1">
                <Trash2 className="w-3 h-3" /> 删除源
              </span>
            )}
          </div>
        </div>
      )}

      {/* 手动同步面板 */}
      <div className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-4">
        <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <Download className="w-4 h-4" />
          手动同步
        </h2>

        {!hasConfig && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              className="bg-surface-2 rounded-lg px-3 py-2 text-sm border border-surface-3 focus:border-brand-500 outline-none"
              placeholder="源目录 (WebDAV 挂载路径)"
              value={manualSource}
              onChange={e => setManualSource(e.target.value)}
            />
            <input
              className="bg-surface-2 rounded-lg px-3 py-2 text-sm border border-surface-3 focus:border-brand-500 outline-none"
              placeholder="目标目录 (NAS 本地路径)"
              value={manualDest}
              onChange={e => setManualDest(e.target.value)}
            />
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleStart}
            disabled={syncing}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 rounded-lg text-sm font-medium transition flex items-center gap-2"
          >
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {syncing ? '同步中...' : '开始同步'}
          </button>
        </div>
      </div>

      {/* 任务进度列表 */}
      {Object.entries(tasks).length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-300">同步任务</h2>

          {Object.entries(tasks).map(([name, task]) => (
            <div key={name} className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-3">
              {/* 头部 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-sm">{name}</span>
                  <StatusBadge status={task.status} />
                </div>
                {['scanning', 'syncing', 'deleting'].includes(task.status) && (
                  <button
                    onClick={() => handleCancel(name)}
                    className="p-1.5 rounded-lg bg-red-900/30 hover:bg-red-900/50 transition"
                    title="取消"
                  >
                    <Square className="w-3.5 h-3.5 text-red-400" />
                  </button>
                )}
              </div>

              {/* 进度条 */}
              {task.total_bytes > 0 && (
                <ProgressBar
                  percent={task.percent || 0}
                  speed={task.speed_human || '0 B/s'}
                />
              )}

              {/* 统计 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <div className="text-gray-500">已拷贝</div>
                  <div className="font-medium mt-0.5">
                    {task.copied_files || 0} 文件 · {formatSize(task.copied_bytes)}
                  </div>
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <div className="text-gray-500">已跳过</div>
                  <div className="font-medium mt-0.5">{task.skipped_files || 0} 文件</div>
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <div className="text-gray-500">耗时</div>
                  <div className="font-medium mt-0.5">{formatDuration(task.elapsed)}</div>
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <div className="text-gray-500">总计</div>
                  <div className="font-medium mt-0.5">
                    {task.total_files || 0} 文件 · {formatSize(task.total_bytes)}
                  </div>
                </div>
              </div>

              {/* 当前文件 */}
              {task.current_file && task.current_file.status === 'copying' && (
                <div className="bg-surface-2 rounded-lg p-3 text-xs">
                  <div className="flex items-center justify-between text-gray-400 mb-1">
                    <span className="truncate mr-2">▸ {task.current_file.filename}</span>
                    <span className="shrink-0">{task.current_file.speed_human}</span>
                  </div>
                  <div className="w-full bg-surface-3 rounded-full h-1.5">
                    <div
                      className="bg-brand-400 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${task.current_file.percent}%` }}
                    />
                  </div>
                </div>
              )}

              {/* 错误 */}
              {task.errors && task.errors.length > 0 && (
                <div className="bg-red-900/20 rounded-lg p-3 text-xs space-y-1">
                  {task.errors.map((err, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-red-400">
                      <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{err}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 完成状态 */}
              {task.status === 'done' && (
                <div className="flex items-center gap-2 text-green-400 text-xs">
                  <CheckCircle className="w-4 h-4" />
                  同步完成 — 拷贝 {task.copied_files} · 跳过 {task.skipped_files}
                  {task.deleted_files > 0 && ` · 删除源 ${task.deleted_files}`}
                  {' '}· 平均 {task.speed_human}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
