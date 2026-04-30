import { useState, useEffect, useRef, useCallback } from 'react'
import {
  RefreshCw, Play, Square, Settings, Folder, FolderOpen, ArrowRight,
  Trash2, CheckCircle, AlertCircle, Loader2, Download, ChevronRight,
  ChevronUp, Timer, Bell, BellOff, X, Plus, Copy, Power, PowerOff, Clock,
} from 'lucide-react'

const API = '/api'

/* ─── 工具函数 ─── */
function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024, units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + units[i]
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function StatusBadge({ status }) {
  const map = {
    idle: ['bg-gray-700 text-gray-300', '空闲'],
    scanning: ['bg-blue-900/50 text-blue-300', '扫描中'],
    syncing: ['bg-brand-900/50 text-brand-300', '同步中'],
    deleting: ['bg-yellow-900/50 text-yellow-300', '清理中'],
    done: ['bg-green-900/50 text-green-300', '完成'],
    error: ['bg-red-900/50 text-red-300', '失败'],
    cancelled: ['bg-gray-700 text-gray-400', '已取消'],
  }
  const [cls, label] = map[status] || map.idle
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${cls}`}>{label}</span>
}

function ProgressBar({ percent, speed, eta }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{percent.toFixed(1)}%{eta ? ` · 剩余 ${eta}` : ''}</span>
        <span>{speed}</span>
      </div>
      <div className="w-full bg-surface-3 rounded-full h-2">
        <div className="bg-brand-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
    </div>
  )
}

/* ─── PathPicker 弹窗 ─── */
function PathPicker({ open, onClose, onSelect, title = '选择目录' }) {
  const [currentPath, setCurrentPath] = useState('/')
  const [inputPath, setInputPath] = useState('/')
  const [dirs, setDirs] = useState([])
  const [parentPath, setParentPath] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const browse = useCallback(async (path) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/sync/browse?path=${encodeURIComponent(path)}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed')
      setCurrentPath(data.path)
      setInputPath(data.path)
      setDirs(data.dirs || [])
      setParentPath(data.parent)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) browse('/')
  }, [open, browse])

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && inputPath.trim()) {
      browse(inputPath.trim())
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-surface-1 rounded-xl border border-surface-3 w-full max-w-lg mx-3 sm:mx-4 max-h-[70vh] flex flex-col"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-3">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-3 rounded"><X className="w-4 h-4" /></button>
        </div>

        <div className="px-5 py-2 bg-surface-2 flex items-center gap-2">
          <Folder className="w-3.5 h-3.5 shrink-0 text-gray-400" />
          <input type="text" value={inputPath}
            onChange={e => setInputPath(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="输入路径后按回车跳转"
            className="flex-1 bg-transparent text-xs font-mono text-gray-300 placeholder-gray-600 outline-none border-none" />
          <button onClick={() => inputPath.trim() && browse(inputPath.trim())}
            className="px-2 py-0.5 bg-surface-3 hover:bg-surface-1 rounded text-xs text-gray-400 transition shrink-0">跳转</button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-[200px] max-h-[400px]">
          {loading && <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-gray-500" /></div>}
          {error && <div className="px-5 py-3 text-xs text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {error}</div>}
          {!loading && !error && (
            <div className="divide-y divide-surface-3">
              {parentPath != null && (
                <button onClick={() => browse(parentPath)}
                  className="w-full px-5 py-2.5 text-left hover:bg-surface-2 transition flex items-center gap-3 text-sm">
                  <ChevronUp className="w-4 h-4 text-gray-500" /><span className="text-gray-400">..</span>
                </button>
              )}
              {dirs.map(d => (
                <button key={d.path} onClick={() => browse(d.path)}
                  className="w-full px-5 py-2.5 text-left hover:bg-surface-2 transition flex items-center gap-3 text-sm group">
                  <FolderOpen className="w-4 h-4 text-brand-400 shrink-0" />
                  <span className="flex-1 truncate">{d.name}</span>
                  <ChevronRight className="w-4 h-4 text-gray-600 opacity-0 group-hover:opacity-100 transition" />
                </button>
              ))}
              {!dirs.length && parentPath != null && (
                <div className="px-5 py-6 text-center text-xs text-gray-600">空目录</div>
              )}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-surface-3 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <input type="text" value={inputPath}
              onChange={e => setInputPath(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { onSelect(inputPath.trim() || currentPath); onClose() } }}
              placeholder="手动输入路径"
              className="flex-1 bg-surface-2 border border-surface-3 rounded-lg px-3 py-1.5 text-xs font-mono text-gray-300 placeholder-gray-600 outline-none focus:border-brand-500 transition" />
            <button onClick={onClose}
              className="px-3 py-1.5 bg-surface-2 hover:bg-surface-3 rounded-lg text-xs transition shrink-0">取消</button>
            <button onClick={() => { onSelect(inputPath.trim() || currentPath); onClose() }}
              className="px-3 py-1.5 bg-brand-600 hover:bg-brand-700 rounded-lg text-xs font-medium transition shrink-0">确定</button>
          </div>
          <div className="text-[10px] text-gray-600">点击目录浏览，或直接输入路径按回车确认</div>
        </div>
      </div>
    </div>
  )
}

/* ─── 路径输入 + 浏览按钮 ─── */
function PathInput({ label, placeholder, value, onChange, pickerTitle }) {
  const [pickerOpen, setPickerOpen] = useState(false)
  return (
    <div>
      {label && <label className="block text-xs text-gray-500 mb-1">{label}</label>}
      <div className="flex gap-2">
        <input
          className="flex-1 bg-surface-2 rounded-lg px-3 py-2 text-sm border border-surface-3 focus:border-brand-500 outline-none"
          placeholder={placeholder} value={value}
          onChange={e => onChange(e.target.value)} />
        <button onClick={() => setPickerOpen(true)}
          className="px-3 py-2 bg-surface-2 hover:bg-surface-3 border border-surface-3 rounded-lg transition"
          title="浏览目录">
          <FolderOpen className="w-4 h-4 text-brand-400" />
        </button>
      </div>
      <PathPicker open={pickerOpen} onClose={() => setPickerOpen(false)}
        onSelect={onChange} title={pickerTitle || label} />
    </div>
  )
}

/* ─── 单个同步任务编辑卡片 ─── */
function SyncTaskCard({ task, index, onChange, onRemove, onDuplicate }) {
  return (
    <div className="bg-surface-2 rounded-lg p-4 border border-surface-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-600 font-mono">#{index + 1}</span>
          <input
            type="text" value={task.name || ''}
            onChange={e => onChange({ ...task, name: e.target.value })}
            placeholder="任务名称"
            className="bg-transparent border-b border-surface-3 focus:border-brand-500 outline-none text-sm font-medium px-1 py-0.5 w-24 sm:w-40" />
          <button onClick={() => onChange({ ...task, enabled: !task.enabled })}
            className={`p-1 rounded transition ${task.enabled !== false ? 'text-green-400' : 'text-gray-600'}`}
            title={task.enabled !== false ? '已启用' : '已禁用'}>
            {task.enabled !== false ? <Power className="w-3.5 h-3.5" /> : <PowerOff className="w-3.5 h-3.5" />}
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onDuplicate} className="p-1 hover:bg-surface-3 rounded transition" title="复制">
            <Copy className="w-3.5 h-3.5 text-gray-500" />
          </button>
          <button onClick={onRemove} className="p-1 hover:bg-red-900/30 rounded transition" title="删除">
            <Trash2 className="w-3.5 h-3.5 text-red-400" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PathInput placeholder="/mnt/alist/夸克"
          value={task.source || ''}
          onChange={v => onChange({ ...task, source: v })}
          pickerTitle="选择源目录" />
        <PathInput placeholder="/mnt/ssd/cache"
          value={task.dest || ''}
          onChange={v => onChange({ ...task, dest: v })}
          pickerTitle="选择目标目录" />
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center text-xs text-gray-400 gap-4">
          <Folder className="w-3.5 h-3.5 text-gray-600 shrink-0" />
          <span className="truncate max-w-[80px] sm:max-w-[140px]">{task.source || '...'}</span>
          <ArrowRight className="w-3 h-3 text-gray-600 shrink-0" />
          <span className="truncate max-w-[80px] sm:max-w-[140px]">{task.dest || '...'}</span>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
        <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
          <input type="checkbox" checked={task.delete_after_sync || false}
            onChange={e => onChange({ ...task, delete_after_sync: e.target.checked })}
            className="rounded" />
          <Trash2 className="w-3 h-3" /> 同步后删除源文件
        </label>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Clock className="w-3 h-3" />
          <span>独立间隔:</span>
          <select value={task.interval_minutes || ''}
            onChange={e => onChange({ ...task, interval_minutes: e.target.value ? Number(e.target.value) : undefined })}
            className="bg-surface-2 border border-surface-3 rounded px-2 py-0.5 text-xs outline-none focus:border-brand-500">
            <option value="">跟随全局</option>
            <option value={5}>5 分钟</option>
            <option value={15}>15 分钟</option>
            <option value={30}>30 分钟</option>
            <option value={60}>1 小时</option>
            <option value={120}>2 小时</option>
            <option value={360}>6 小时</option>
            <option value={720}>12 小时</option>
            <option value={1440}>每天</option>
          </select>
        </div>
      </div>
    </div>
  )
}


/* ─── 主页面 ─── */
export default function SyncPage() {
  const [syncConfig, setSyncConfig] = useState(null)
  const [taskProgress, setTaskProgress] = useState({})
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [editMode, setEditMode] = useState(false)

  // 编辑表单
  const [formTasks, setFormTasks] = useState([])
  const [formGlobal, setFormGlobal] = useState({
    schedule_enabled: false, schedule_interval_minutes: 60, bot_notify: false,
  })

  const eventSourcesRef = useRef({})

  const fetchAll = useCallback(async () => {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch(`${API}/sync/config`),
        fetch(`${API}/sync/status`),
      ])
      const cfgData = await cfgRes.json()
      const statusData = await statusRes.json()
      setSyncConfig(cfgData)
      setTaskProgress(statusData.tasks || {})
      setFormTasks(cfgData.tasks || [])
      setFormGlobal({
        schedule_enabled: cfgData.schedule_enabled || false,
        schedule_interval_minutes: cfgData.schedule_interval_minutes || 60,
        bot_notify: cfgData.bot_notify || false,
      })
    } catch (e) {
      console.error('Failed to load sync data:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // 定时刷新活跃任务
  useEffect(() => {
    const hasActive = Object.values(taskProgress).some(t =>
      ['scanning', 'syncing', 'deleting'].includes(t.status)
    )
    if (!hasActive) return
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API}/sync/status`)
        const data = await res.json()
        setTaskProgress(data.tasks || {})
        // 全部完成时解除 syncing
        const stillActive = Object.values(data.tasks || {}).some(t =>
          ['scanning', 'syncing', 'deleting'].includes(t.status)
        )
        if (!stillActive) setSyncing(false)
      } catch {}
    }, 1000)
    return () => clearInterval(timer)
  }, [taskProgress])

  // 清理 SSE
  useEffect(() => () => {
    Object.values(eventSourcesRef.current).forEach(es => es.close())
  }, [])

  // 连接 SSE
  const connectSSE = useCallback((taskName) => {
    if (eventSourcesRef.current[taskName]) eventSourcesRef.current[taskName].close()
    const es = new EventSource(`${API}/sync/progress/${encodeURIComponent(taskName)}`)
    eventSourcesRef.current[taskName] = es
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setTaskProgress(prev => ({ ...prev, [taskName]: data }))
        if (['done', 'error', 'cancelled'].includes(data.status)) {
          es.close()
          delete eventSourcesRef.current[taskName]
        }
      } catch {}
    }
    es.onerror = () => { es.close(); delete eventSourcesRef.current[taskName] }
  }, [])

  // 启动全部同步
  const handleStartAll = async () => {
    const tasks = syncConfig?.tasks || []
    const enabled = tasks.filter(t => t.enabled !== false && t.source && t.dest)
    if (!enabled.length) { alert('请先配置同步任务'); return }

    try {
      setSyncing(true)
      const res = await fetch(`${API}/sync/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_all: true,
          bot_notify: formGlobal.bot_notify || syncConfig?.bot_notify || false,
        }),
      })
      const data = await res.json()
      if (!res.ok) { alert(data.detail || '启动失败'); setSyncing(false); return }
      // 为每个启动的任务连 SSE
      for (const tname of (data.tasks || [])) {
        connectSSE(tname)
      }
    } catch (e) {
      alert('启动失败: ' + e.message); setSyncing(false)
    }
  }

  // 启动单个任务
  const handleStartOne = async (taskName) => {
    try {
      setSyncing(true)
      const res = await fetch(`${API}/sync/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_name: taskName,
          bot_notify: formGlobal.bot_notify || syncConfig?.bot_notify || false,
        }),
      })
      const data = await res.json()
      if (!res.ok) { alert(data.detail || '启动失败'); setSyncing(false); return }
      for (const tname of (data.tasks || [])) {
        connectSSE(tname)
      }
    } catch (e) {
      alert('启动失败: ' + e.message); setSyncing(false)
    }
  }

  const handleCancel = async (taskName) => {
    try { await fetch(`${API}/sync/cancel/${encodeURIComponent(taskName)}`, { method: 'POST' }) } catch {}
  }

  // 保存配置
  const handleSaveConfig = async () => {
    try {
      const payload = { tasks: formTasks, ...formGlobal }
      const res = await fetch(`${API}/sync/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const data = await res.json()
        setSyncConfig(data.sync)
        setEditMode(false)
      }
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  // 添加新任务
  const addTask = () => {
    setFormTasks(prev => [...prev, {
      name: '同步任务' + (prev.length + 1),
      source: '', dest: '',
      delete_after_sync: false, enabled: true,
    }])
  }

  const updateTask = (idx, task) => {
    setFormTasks(prev => prev.map((t, i) => i === idx ? task : t))
  }

  const removeTask = (idx) => {
    if (formTasks.length <= 1) { alert('至少保留一个同步任务'); return }
    setFormTasks(prev => prev.filter((_, i) => i !== idx))
  }

  const duplicateTask = (idx) => {
    const t = { ...formTasks[idx], name: formTasks[idx].name + ' (副本)' }
    setFormTasks(prev => [...prev.slice(0, idx + 1), t, ...prev.slice(idx + 1)])
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
  }

  const configTasks = syncConfig?.tasks || []
  const enabledTasks = configTasks.filter(t => t.enabled !== false && t.source && t.dest)
  const hasConfig = enabledTasks.length > 0

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">文件同步</h1>
          <p className="text-sm text-gray-500 mt-1">多路径并行同步 · WebDAV / SSD / HDD</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchAll} className="p-2 rounded-lg bg-surface-2 hover:bg-surface-3 transition" title="刷新">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => setEditMode(!editMode)}
            className={`p-2 rounded-lg transition ${editMode ? 'bg-brand-600' : 'bg-surface-2 hover:bg-surface-3'}`} title="配置">
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 配置编辑 */}
      {editMode && (
        <div className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-300">同步任务配置</h2>
            <button onClick={addTask}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 hover:bg-surface-3 border border-surface-3 rounded-lg text-xs transition">
              <Plus className="w-3.5 h-3.5" /> 添加任务
            </button>
          </div>

          <div className="space-y-3">
            {formTasks.map((task, idx) => (
              <SyncTaskCard key={idx} task={task} index={idx}
                onChange={t => updateTask(idx, t)}
                onRemove={() => removeTask(idx)}
                onDuplicate={() => duplicateTask(idx)} />
            ))}
            {formTasks.length === 0 && (
              <div className="text-center py-8 text-sm text-gray-600">
                暂无同步任务，点击上方「添加任务」创建
              </div>
            )}
          </div>

          {/* 全局选项 */}
          <div className="border-t border-surface-3 pt-4 space-y-3">
            <h3 className="text-xs text-gray-500 font-medium">全局选项</h3>
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input type="checkbox" checked={formGlobal.bot_notify}
                  onChange={e => setFormGlobal(f => ({ ...f, bot_notify: e.target.checked }))} className="rounded" />
                {formGlobal.bot_notify ? <Bell className="w-3.5 h-3.5 text-brand-400" /> : <BellOff className="w-3.5 h-3.5" />}
                飞书 Bot 通知
              </label>
            </div>

            {/* 定时同步 */}
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input type="checkbox" checked={formGlobal.schedule_enabled}
                onChange={e => setFormGlobal(f => ({ ...f, schedule_enabled: e.target.checked }))} className="rounded" />
              <Timer className="w-4 h-4 text-brand-400" />
              <span className="font-medium">启用定时同步</span>
            </label>
            {formGlobal.schedule_enabled && (
              <div className="ml-6 flex items-center gap-3">
                <label className="text-xs text-gray-500">执行间隔:</label>
                <select value={formGlobal.schedule_interval_minutes}
                  onChange={e => setFormGlobal(f => ({ ...f, schedule_interval_minutes: Number(e.target.value) }))}
                  className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-brand-500">
                  <option value={15}>每 15 分钟</option>
                  <option value={30}>每 30 分钟</option>
                  <option value={60}>每 1 小时</option>
                  <option value={120}>每 2 小时</option>
                  <option value={360}>每 6 小时</option>
                  <option value={720}>每 12 小时</option>
                  <option value={1440}>每天</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-2">
            <button onClick={handleSaveConfig}
              className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 rounded-lg text-sm transition">保存</button>
            <button onClick={() => { setEditMode(false); setFormTasks(configTasks); }}
              className="px-4 py-1.5 bg-surface-2 hover:bg-surface-3 rounded-lg text-sm transition">取消</button>
          </div>
        </div>
      )}

      {/* 当前配置概览 */}
      {!editMode && hasConfig && (
        <div className="bg-surface-1 rounded-xl p-4 border border-surface-3 space-y-2">
          {enabledTasks.map((t, i) => (
            <div key={i} className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm flex-wrap">
              <span className="text-xs text-gray-600 font-mono w-5">#{i + 1}</span>
              <span className="font-medium text-gray-300 min-w-[80px]">{t.name}</span>
              <Folder className="w-3.5 h-3.5 text-brand-400 shrink-0" />
              <span className="text-gray-400 truncate max-w-[100px] sm:max-w-[200px]">{t.source}</span>
              <ArrowRight className="w-3.5 h-3.5 text-gray-600 shrink-0" />
              <span className="text-gray-400 truncate max-w-[100px] sm:max-w-[200px]">{t.dest}</span>
              {t.delete_after_sync && (
                <span className="text-[10px] text-yellow-500 flex items-center gap-0.5"><Trash2 className="w-3 h-3" />删除源</span>
              )}
              {t.interval_minutes > 0 && (
                <span className="text-[10px] text-cyan-400 flex items-center gap-0.5"><Clock className="w-3 h-3" />{t.interval_minutes}m</span>
              )}
              {/* 单个任务启动按钮 */}
              <button onClick={() => handleStartOne(t.name)}
                disabled={syncing}
                className="ml-auto p-1 rounded hover:bg-surface-3 transition disabled:opacity-50"
                title={`启动 ${t.name}`}>
                <Play className="w-3.5 h-3.5 text-brand-400" />
              </button>
            </div>
          ))}
          <div className="flex items-center gap-3 text-xs text-gray-600 pt-1 border-t border-surface-3 mt-2">
            {syncConfig?.bot_notify && <span className="text-brand-400 flex items-center gap-1"><Bell className="w-3 h-3" /> 通知</span>}
            {syncConfig?.schedule_enabled && (
              <span className="text-green-400 flex items-center gap-1">
                <Timer className="w-3 h-3" /> 每 {syncConfig.schedule_interval_minutes || 60}m
              </span>
            )}
            <span>{enabledTasks.length} 个活跃任务</span>
          </div>
        </div>
      )}

      {/* 全部同步按钮 */}
      <div className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-4">
        <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <Download className="w-4 h-4" /> 手动同步
        </h2>
        <div className="flex gap-2 flex-wrap">
          <button onClick={handleStartAll} disabled={syncing || !hasConfig}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 rounded-lg text-sm font-medium transition flex items-center gap-2">
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {syncing ? '同步中...' : `全部同步 (${enabledTasks.length} 任务)`}
          </button>
          {!hasConfig && (
            <span className="self-center text-xs text-gray-500">请先点击右上角 ⚙️ 配置同步任务</span>
          )}
        </div>
      </div>

      {/* 任务进度列表 */}
      {Object.entries(taskProgress).length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-300">运行进度</h2>
          {Object.entries(taskProgress).map(([name, task]) => (
            <div key={name} className="bg-surface-1 rounded-xl p-5 border border-surface-3 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-sm">{name}</span>
                  <StatusBadge status={task.status} />
                </div>
                {['scanning', 'syncing', 'deleting'].includes(task.status) && (
                  <button onClick={() => handleCancel(name)}
                    className="p-1.5 rounded-lg bg-red-900/30 hover:bg-red-900/50 transition" title="取消">
                    <Square className="w-3.5 h-3.5 text-red-400" />
                  </button>
                )}
              </div>
              {task.total_bytes > 0 && (
                <ProgressBar percent={task.percent || 0} speed={task.speed_human || '0 B/s'} eta={task.eta_human} />
              )}
              <div className="grid grid-cols-2 gap-2 sm:gap-3 text-xs">
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <div className="text-gray-500">已拷贝</div>
                  <div className="font-medium mt-0.5">{task.copied_files || 0} 文件 · {formatSize(task.copied_bytes)}</div>
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
                  <div className="font-medium mt-0.5">{task.total_files || 0} 文件 · {formatSize(task.total_bytes)}</div>
                </div>
              </div>
              {task.current_file && task.current_file.status === 'copying' && (
                <div className="bg-surface-2 rounded-lg p-3 text-xs">
                  <div className="flex items-center justify-between text-gray-400 mb-1">
                    <span className="truncate mr-2">▸ {task.current_file.filename}</span>
                    <span className="shrink-0">{task.current_file.eta_human ? `${task.current_file.eta_human} · ` : ''}{task.current_file.speed_human}</span>
                  </div>
                  <div className="w-full bg-surface-3 rounded-full h-1.5">
                    <div className="bg-brand-400 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${task.current_file.percent}%` }} />
                  </div>
                </div>
              )}
              {task.errors && task.errors.length > 0 && (
                <div className="bg-red-900/20 rounded-lg p-3 text-xs space-y-1">
                  {task.errors.slice(0, 5).map((err, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-red-400">
                      <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{err}</span>
                    </div>
                  ))}
                  {task.errors.length > 5 && (
                    <div className="text-gray-600 pl-5">...还有 {task.errors.length - 5} 个错误</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
