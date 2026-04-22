import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Cloud, FolderOpen, FolderPlus, Trash2, Download, Link2, RefreshCw,
  ChevronRight, ArrowLeft, Loader2, Settings, X, Check, Copy,
  Magnet, FileText, Plus, AlertCircle, CheckCircle, HardDrive, Server,
  FolderSync, StopCircle, Play, Clock
} from 'lucide-react'

const API = '/api'

function fmtSize(b) {
  if (!b) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let s = b
  while (s >= 1024 && i < u.length - 1) { s /= 1024; i++ }
  return `${s.toFixed(i > 0 ? 2 : 0)} ${u[i]}`
}

function StatusBadge({ status }) {
  const map = {
    0: ['等待中', 'bg-gray-500/20 text-gray-400'],
    1: ['下载中', 'bg-blue-500/20 text-blue-400 animate-pulse'],
    2: ['已完成', 'bg-green-500/20 text-green-400'],
    3: ['失败', 'bg-red-500/20 text-red-400'],
  }
  const [label, cls] = map[status] || ['未知', 'bg-gray-500/20 text-gray-400']
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>{label}</span>
}

function SyncStatusBadge({ status }) {
  const map = {
    pending: ['扫描中', 'bg-yellow-500/20 text-yellow-400 animate-pulse'],
    running: ['同步中', 'bg-blue-500/20 text-blue-400 animate-pulse'],
    done: ['完成', 'bg-green-500/20 text-green-400'],
    failed: ['失败', 'bg-red-500/20 text-red-400'],
    cancelled: ['已取消', 'bg-gray-500/20 text-gray-400'],
  }
  const [label, cls] = map[status] || ['未知', 'bg-gray-500/20 text-gray-400']
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>{label}</span>
}

// ── 配置弹窗 ──
function ConfigModal({ config, onClose, onSave }) {
  const [token, setToken] = useState('')
  const [downloadDir, setDownloadDir] = useState(config?.download_dir || '/downloads/guangya')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const body = {}
      if (token.trim()) body.refresh_token = token.trim()
      if (downloadDir.trim()) body.download_dir = downloadDir.trim()
      const resp = await fetch(`${API}/guangya/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error('保存失败')
      onSave()
    } catch (e) { alert(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold">光鸭云盘配置</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <div className="text-xs text-gray-400 mb-1">当前状态</div>
            <div className="text-sm">
              {config?.has_refresh_token
                ? <span className="text-green-400">✓ 已配置 ({config.refresh_token_preview})</span>
                : <span className="text-red-400">✗ 未配置</span>}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">Refresh Token</div>
            <input
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              placeholder="粘贴 refresh_token (留空不修改)..."
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
            />
            <div className="text-[10px] text-gray-600 mt-1">
              F12 控制台执行: JSON.parse(localStorage.getItem("credentials_aMe-8VSlkrbQXpUR")||"{'{}'}").refresh_token
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">服务器下载目录</div>
            <input
              value={downloadDir}
              onChange={e => setDownloadDir(e.target.value)}
              placeholder="/downloads/guangya"
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
            />
            <div className="text-[10px] text-gray-600 mt-1">
              Sync / 下载到服务器时的默认保存路径
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button onClick={handleSave} disabled={saving || (!token.trim() && !downloadDir.trim())}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2">
            {saving && <Loader2 size={14} className="animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 云添加弹窗 ──
function CloudAddModal({ onClose, onCreated }) {
  const [url, setUrl] = useState('')
  const [parentId, setParentId] = useState('')
  const [resolving, setResolving] = useState(false)
  const [resolved, setResolved] = useState(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const isMagnet = url.trim().startsWith('magnet:')

  const doResolve = async () => {
    setResolving(true); setError(''); setResolved(null)
    try {
      const endpoint = isMagnet ? `${API}/guangya/cloud/resolve-magnet` : `${API}/guangya/cloud/resolve-torrent-url`
      const resp = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })
      if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || '解析失败') }
      setResolved(await resp.json())
    } catch (e) { setError(e.message) }
    finally { setResolving(false) }
  }

  const doCreate = async () => {
    setCreating(true); setError('')
    try {
      const magnetUrl = isMagnet ? url.trim() : (resolved?.url || `magnet:?xt=urn:btih:${resolved?.btResInfo?.infoHash}`)
      const btInfo = resolved?.btResInfo || {}
      const subfiles = btInfo.subfiles || []
      const body = {
        url: magnetUrl,
        parent_id: parentId,
        file_indexes: subfiles.length > 0 ? subfiles.map((_, i) => i) : undefined,
      }
      const resp = await fetch(`${API}/guangya/cloud/create`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || '创建失败') }
      onCreated()
    } catch (e) { setError(e.message) }
    finally { setCreating(false) }
  }

  const btInfo = resolved?.btResInfo || {}
  const subfiles = btInfo.subfiles || []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-lg max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2"><Plus size={18} className="text-brand-400" />云添加</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <label className="block">
            <span className="text-xs text-gray-400 mb-1 block">磁力链接 / 种子 URL</span>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="magnet:?xt=... 或 https://...xxx.torrent"
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500" />
          </label>
          {!resolved && (
            <button onClick={doResolve} disabled={resolving || !url.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm disabled:opacity-50">
              {resolving ? <Loader2 size={14} className="animate-spin" /> : <Magnet size={14} />}
              解析
            </button>
          )}
          {error && <div className="flex items-center gap-2 text-red-400 text-sm p-3 bg-red-500/10 rounded-lg"><AlertCircle size={16} />{error}</div>}
          {resolved && (
            <div className="bg-surface-2 border border-surface-3 rounded-lg p-3 space-y-2">
              <div className="font-medium text-sm">{btInfo.fileName || '未知'}</div>
              <div className="text-xs text-gray-400">大小: {fmtSize(btInfo.fileSize)} · {subfiles.length} 个文件</div>
              {subfiles.length > 0 && subfiles.length <= 20 && (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {subfiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-xs text-gray-400">
                      <span className="truncate flex-1">{f.fileName}</span>
                      <span className="flex-shrink-0 ml-2">{fmtSize(f.fileSize)}</span>
                    </div>
                  ))}
                </div>
              )}
              <button onClick={doCreate} disabled={creating}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm disabled:opacity-50 mt-2">
                {creating ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                创建任务
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sync 进度卡片 ──
function SyncTaskCard({ task, onCancel, onRemove }) {
  const pct = task.progress || 0
  const isActive = task.status === 'running' || task.status === 'pending'
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [task.log])

  return (
    <div className="bg-surface-2 border border-surface-3 rounded-lg p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <FolderSync size={16} className={`flex-shrink-0 ${isActive ? 'text-blue-400 animate-pulse' : 'text-gray-400'}`} />
          <span className="text-sm font-medium truncate">{task.file_name || task.file_id}</span>
          <SyncStatusBadge status={task.status} />
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {isActive && (
            <button onClick={() => onCancel(task.task_id)}
              className="p-1.5 rounded hover:bg-red-500/10 text-red-400/60 hover:text-red-400" title="取消">
              <StopCircle size={14} />
            </button>
          )}
          {!isActive && (
            <button onClick={() => onRemove(task.task_id)}
              className="p-1.5 rounded hover:bg-surface-3 text-gray-500 hover:text-gray-300" title="删除记录">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between text-[10px] text-gray-500 mb-1">
          <span>{task.done_bytes_fmt} / {task.total_bytes_fmt}</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div className="w-full h-1.5 bg-surface-3 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              task.status === 'done' ? 'bg-green-500' :
              task.status === 'failed' ? 'bg-red-500' :
              task.status === 'cancelled' ? 'bg-gray-500' : 'bg-blue-500'
            }`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
        <div>
          <span className="text-gray-500">文件:</span>{' '}
          <span className="text-gray-300">{task.done_files}/{task.total_files}</span>
        </div>
        <div>
          <span className="text-gray-500">目录:</span>{' '}
          <span className="text-gray-300">{task.done_dirs}/{task.total_dirs}</span>
        </div>
        <div>
          <span className="text-gray-500">跳过:</span>{' '}
          <span className="text-gray-300">{task.skipped_files}</span>
          {task.failed_files > 0 && <span className="text-red-400 ml-1">失败:{task.failed_files}</span>}
        </div>
        <div>
          <span className="text-gray-500">速度:</span>{' '}
          <span className="text-gray-300">{task.speed_fmt || '-'}</span>
        </div>
      </div>

      {/* Current file */}
      {isActive && task.current_file && (
        <div className="text-[10px] text-gray-500 truncate">
          ↳ {task.current_file}
        </div>
      )}

      {/* Log (collapsible) */}
      {task.log && task.log.length > 0 && (
        <details className="text-[10px]">
          <summary className="text-gray-500 cursor-pointer hover:text-gray-300">日志 ({task.log.length})</summary>
          <div ref={logRef} className="mt-1 max-h-32 overflow-y-auto bg-black/30 rounded p-2 font-mono text-gray-400 space-y-0.5">
            {task.log.map((line, i) => <div key={i}>{line}</div>)}
          </div>
        </details>
      )}

      {/* Error */}
      {task.error && (
        <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{task.error}</div>
      )}

      {/* Elapsed */}
      {task.elapsed > 0 && !isActive && (
        <div className="text-[10px] text-gray-500 flex items-center gap-1">
          <Clock size={10} /> 耗时 {task.elapsed.toFixed(1)}s
        </div>
      )}
    </div>
  )
}

// ── 主页面 ──
export default function GuangyaPage() {
  const [tab, setTab] = useState('files') // files | tasks | sync
  const [config, setConfig] = useState(null)
  const [space, setSpace] = useState(null)
  const [showConfig, setShowConfig] = useState(false)
  const [showCloudAdd, setShowCloudAdd] = useState(false)

  // 文件浏览
  const [path, setPath] = useState([]) // [{id, name}]
  const [files, setFiles] = useState([])
  const [filesLoading, setFilesLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())

  // 云添加任务
  const [tasks, setTasks] = useState([])
  const [tasksLoading, setTasksLoading] = useState(true)

  // Sync 任务
  const [syncTasks, setSyncTasks] = useState([])
  const [syncLoading, setSyncLoading] = useState(false)

  // 服务器下载状态
  const [downloading, setDownloading] = useState(new Set())

  const parentId = path.length > 0 ? path[path.length - 1].id : ''

  const fetchConfig = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/guangya/config`)
      setConfig(await resp.json())
    } catch { /* ignore */ }
  }, [])

  const fetchSpace = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/guangya/space`)
      if (resp.ok) setSpace(await resp.json())
    } catch { /* ignore */ }
  }, [])

  const fetchFiles = useCallback(async () => {
    setFilesLoading(true)
    try {
      const resp = await fetch(`${API}/guangya/drive/ls?parent_id=${encodeURIComponent(parentId)}`)
      if (resp.ok) {
        const data = await resp.json()
        setFiles(data.items || [])
      }
    } catch { /* ignore */ }
    finally { setFilesLoading(false) }
  }, [parentId])

  const fetchTasks = useCallback(async () => {
    setTasksLoading(true)
    try {
      const resp = await fetch(`${API}/guangya/cloud/tasks`)
      if (resp.ok) {
        const data = await resp.json()
        setTasks(data.tasks?.list || data.tasks || [])
      }
    } catch { /* ignore */ }
    finally { setTasksLoading(false) }
  }, [])

  const fetchSyncTasks = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/guangya/sync/list`)
      if (resp.ok) {
        const data = await resp.json()
        setSyncTasks(data.tasks || [])
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { fetchConfig(); fetchSpace() }, [])
  useEffect(() => { if (tab === 'files') fetchFiles() }, [tab, fetchFiles])
  useEffect(() => {
    if (tab === 'tasks') {
      fetchTasks()
      const timer = setInterval(fetchTasks, 5000)
      return () => clearInterval(timer)
    }
  }, [tab, fetchTasks])
  useEffect(() => {
    if (tab === 'sync') {
      fetchSyncTasks()
      const hasActive = syncTasks.some(t => t.status === 'running' || t.status === 'pending')
      const interval = hasActive ? 1000 : 5000
      const timer = setInterval(fetchSyncTasks, interval)
      return () => clearInterval(timer)
    }
  }, [tab, fetchSyncTasks, syncTasks])

  const navigateTo = (fileId, fileName) => {
    setPath(p => [...p, { id: fileId, name: fileName }])
    setSelected(new Set())
  }
  const navigateBack = () => { setPath(p => p.slice(0, -1)); setSelected(new Set()) }
  const navigateToBreadcrumb = (idx) => { setPath(p => p.slice(0, idx + 1)); setSelected(new Set()) }

  const handleDelete = async () => {
    if (selected.size === 0) return
    if (!confirm(`确认删除 ${selected.size} 个文件/文件夹?`)) return
    try {
      await fetch(`${API}/guangya/drive/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_ids: [...selected] }),
      })
      setSelected(new Set())
      fetchFiles()
    } catch (e) { alert(e.message) }
  }

  const handleMkdir = async () => {
    const name = prompt('新建文件夹名称:')
    if (!name?.trim()) return
    try {
      await fetch(`${API}/guangya/drive/mkdir`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir_name: name.trim(), parent_id: parentId }),
      })
      fetchFiles()
    } catch (e) { alert(e.message) }
  }

  const handleDownload = async (fileId) => {
    try {
      const resp = await fetch(`${API}/guangya/drive/download?file_id=${fileId}`)
      if (!resp.ok) throw new Error('获取下载链接失败')
      const data = await resp.json()
      if (data.signedURL) window.open(data.signedURL, '_blank')
      else alert('无下载链接')
    } catch (e) { alert(e.message) }
  }

  const handleDownloadToServer = async (fileId, fileName) => {
    setDownloading(prev => new Set(prev).add(fileId))
    try {
      const resp = await fetch(`${API}/guangya/drive/download-to-server`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId }),
      })
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}))
        throw new Error(e.detail || '下载失败')
      }
      const data = await resp.json()
      alert(`✅ 下载完成\n文件: ${data.fileName}\n路径: ${data.path}\n大小: ${data.size_fmt}`)
    } catch (e) {
      alert(`❌ ${e.message}`)
    } finally {
      setDownloading(prev => {
        const s = new Set(prev)
        s.delete(fileId)
        return s
      })
    }
  }

  const handleSync = async (fileId, fileName) => {
    try {
      const resp = await fetch(`${API}/guangya/sync/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId }),
      })
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}))
        throw new Error(e.detail || '创建 Sync 任务失败')
      }
      setTab('sync')
      fetchSyncTasks()
    } catch (e) {
      alert(`❌ ${e.message}`)
    }
  }

  const handleSyncCancel = async (taskId) => {
    try {
      await fetch(`${API}/guangya/sync/cancel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId }),
      })
      fetchSyncTasks()
    } catch (e) { alert(e.message) }
  }

  const handleSyncRemove = async (taskId) => {
    try {
      await fetch(`${API}/guangya/sync/remove`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId }),
      })
      fetchSyncTasks()
    } catch (e) { alert(e.message) }
  }

  const handleDeleteTasks = async (taskIds) => {
    if (!confirm(`确认删除 ${taskIds.length} 个任务?`)) return
    try {
      await fetch(`${API}/guangya/cloud/tasks/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_ids: taskIds }),
      })
      fetchTasks()
    } catch (e) { alert(e.message) }
  }

  const notConfigured = config && !config.has_refresh_token

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-3">
            <Cloud className="text-cyan-400" size={24} />
            光鸭云盘
          </h1>
          <p className="text-sm text-gray-500 mt-1">guangyapan.com · 文件管理 & 云添加 & Sync</p>
        </div>
        <div className="flex items-center gap-2">
          {space && (
            <div className="text-xs text-gray-500 mr-2">
              <HardDrive size={12} className="inline mr-1" />
              {space.used_fmt} / {space.total_fmt}
            </div>
          )}
          <button onClick={() => setShowCloudAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium">
            <Plus size={16} />云添加
          </button>
          <button onClick={() => setShowConfig(true)}
            className="p-2 rounded-lg hover:bg-surface-2" title="配置">
            <Settings size={16} />
          </button>
        </div>
      </div>

      {notConfigured && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="text-yellow-400 flex-shrink-0" size={20} />
          <div>
            <div className="text-sm font-medium text-yellow-400">未配置光鸭云盘</div>
            <div className="text-xs text-gray-400 mt-0.5">点击右上角设置图标配置 Refresh Token</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-2 rounded-lg p-1 w-fit">
        {[
          ['files', '文件管理', FolderOpen],
          ['sync', 'Sync 任务', FolderSync],
          ['tasks', '云添加任务', Cloud],
        ].map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition ${tab === key ? 'bg-surface-1 text-white shadow' : 'text-gray-400 hover:text-white'}`}>
            <Icon size={16} />{label}
            {key === 'sync' && syncTasks.some(t => t.status === 'running' || t.status === 'pending') && (
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            )}
          </button>
        ))}
      </div>

      {/* Files Tab */}
      {tab === 'files' && (
        <div className="bg-surface-1 border border-surface-3 rounded-xl">
          {/* Toolbar */}
          <div className="flex items-center gap-2 p-3 border-b border-surface-3">
            <div className="flex items-center gap-1 text-sm flex-1 min-w-0 overflow-x-auto">
              <button onClick={() => { setPath([]); setSelected(new Set()) }}
                className="text-gray-400 hover:text-white flex-shrink-0">根目录</button>
              {path.map((p, i) => (
                <span key={i} className="flex items-center gap-1 flex-shrink-0">
                  <ChevronRight size={14} className="text-gray-600" />
                  <button onClick={() => navigateToBreadcrumb(i)} className="text-gray-400 hover:text-white truncate max-w-[120px]">{p.name}</button>
                </span>
              ))}
            </div>
            <button onClick={handleMkdir} className="p-2 rounded-lg hover:bg-surface-2" title="新建文件夹"><FolderPlus size={16} /></button>
            {selected.size > 0 && (
              <button onClick={handleDelete} className="p-2 rounded-lg hover:bg-red-500/10 text-red-400" title="删除选中">
                <Trash2 size={16} />
              </button>
            )}
            <button onClick={fetchFiles} className="p-2 rounded-lg hover:bg-surface-2"><RefreshCw size={16} className={filesLoading ? 'animate-spin' : ''} /></button>
          </div>

          {/* File List */}
          <div className="divide-y divide-surface-3">
            {path.length > 0 && (
              <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2/50 cursor-pointer" onClick={navigateBack}>
                <ArrowLeft size={16} className="text-gray-500" />
                <span className="text-sm text-gray-400">..</span>
              </div>
            )}
            {filesLoading && files.length === 0 ? (
              <div className="p-8 text-center"><Loader2 size={24} className="animate-spin mx-auto text-brand-400" /></div>
            ) : files.length === 0 ? (
              <div className="p-8 text-center text-gray-500 text-sm">空目录</div>
            ) : files.map(f => (
              <div key={f.fileId}
                className={`flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2/50 transition ${selected.has(f.fileId) ? 'bg-brand-600/10' : ''}`}>
                <input type="checkbox" checked={selected.has(f.fileId)}
                  onChange={e => {
                    const s = new Set(selected)
                    e.target.checked ? s.add(f.fileId) : s.delete(f.fileId)
                    setSelected(s)
                  }}
                  className="rounded border-surface-3" />
                <div className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer"
                  onClick={() => f.is_dir ? navigateTo(f.fileId, f.fileName) : null}>
                  {f.is_dir
                    ? <FolderOpen size={18} className="text-yellow-400 flex-shrink-0" />
                    : <FileText size={18} className="text-gray-400 flex-shrink-0" />}
                  <span className="text-sm truncate flex-1">{f.fileName}</span>
                  <span className="text-xs text-gray-500 flex-shrink-0">{f.size_fmt}</span>
                </div>
                <div className="flex items-center gap-1">
                  {/* Sync 按钮 — 目录和文件都支持 */}
                  <button onClick={() => handleSync(f.fileId, f.fileName)}
                    className="p-1.5 rounded hover:bg-blue-500/10 group" title="Sync 到服务器">
                    <FolderSync size={14} className="text-blue-400/60 group-hover:text-blue-400" />
                  </button>
                  {!f.is_dir && (
                    <>
                      <button onClick={() => handleDownloadToServer(f.fileId, f.fileName)}
                        disabled={downloading.has(f.fileId)}
                        className="p-1.5 rounded hover:bg-green-500/10 group" title="下载到服务器">
                        {downloading.has(f.fileId)
                          ? <Loader2 size={14} className="text-green-400 animate-spin" />
                          : <Server size={14} className="text-green-400/60 group-hover:text-green-400" />}
                      </button>
                      <button onClick={() => handleDownload(f.fileId)}
                        className="p-1.5 rounded hover:bg-surface-3" title="浏览器下载">
                        <Download size={14} className="text-gray-400" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sync Tab */}
      {tab === 'sync' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-300">Sync 任务 ({syncTasks.length})</span>
            <button onClick={fetchSyncTasks} className="p-2 rounded-lg hover:bg-surface-2">
              <RefreshCw size={16} className={syncLoading ? 'animate-spin' : ''} />
            </button>
          </div>
          {syncTasks.length === 0 ? (
            <div className="bg-surface-1 border border-surface-3 rounded-xl p-8 text-center text-gray-500 text-sm">
              暂无 Sync 任务 — 在文件管理中点击 <FolderSync size={14} className="inline text-blue-400" /> 按钮开始
            </div>
          ) : syncTasks.map(t => (
            <SyncTaskCard key={t.task_id} task={t} onCancel={handleSyncCancel} onRemove={handleSyncRemove} />
          ))}
        </div>
      )}

      {/* Tasks Tab */}
      {tab === 'tasks' && (
        <div className="bg-surface-1 border border-surface-3 rounded-xl">
          <div className="flex items-center justify-between p-3 border-b border-surface-3">
            <span className="text-sm font-semibold">云添加任务 ({tasks.length})</span>
            <button onClick={fetchTasks} className="p-2 rounded-lg hover:bg-surface-2">
              <RefreshCw size={16} className={tasksLoading ? 'animate-spin' : ''} />
            </button>
          </div>
          <div className="divide-y divide-surface-3">
            {tasksLoading && tasks.length === 0 ? (
              <div className="p-8 text-center"><Loader2 size={24} className="animate-spin mx-auto text-brand-400" /></div>
            ) : tasks.length === 0 ? (
              <div className="p-8 text-center text-gray-500 text-sm">暂无任务</div>
            ) : tasks.map(t => (
              <div key={t.taskId} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2/50">
                <Magnet size={16} className="text-purple-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{t.fileName}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <StatusBadge status={t.status} />
                    <span className="text-xs text-gray-500">{fmtSize(t.totalSize)}</span>
                    {t.progress != null && t.status === 1 && (
                      <span className="text-xs text-blue-400">{t.progress}%</span>
                    )}
                  </div>
                </div>
                <button onClick={() => handleDeleteTasks([t.taskId])}
                  className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {showConfig && <ConfigModal config={config} onClose={() => setShowConfig(false)} onSave={() => { setShowConfig(false); fetchConfig(); fetchSpace() }} />}
      {showCloudAdd && <CloudAddModal onClose={() => setShowCloudAdd(false)} onCreated={() => { setShowCloudAdd(false); setTab('tasks'); fetchTasks() }} />}
    </div>
  )
}
