import { useState, useEffect, useCallback } from 'react'
import {
  Clock, Play, Pause, Plus, Trash2, Settings, Loader2,
  Film, Tv, Zap, CheckCircle2, XCircle, AlertCircle,
  RotateCcw, ChevronDown, ChevronRight, Bot, Bell,
  Search, Library, Filter, Shuffle, Power, Calendar,
} from 'lucide-react'
import { schedulerApi, discoveryApi } from '../api/client'
import { PageHeader, ErrorBanner } from '../components/UI'

/* ════════════════════════════════════════════════
   任务编辑器 (弹窗)
   ════════════════════════════════════════════════ */
function TaskEditor({ task, onSave, onClose, genres }) {
  const [form, setForm] = useState({
    name: '',
    enabled: true,
    interval_minutes: 360,
    source: 'tmdb',
    media_type: 'movie',
    count: 3,
    filters: {},
    save_base_path: '/媒体',
    check_media_lib: true,
    bot_notify: true,
    notify_open_id: '',
    ...task,
  })

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))
  const setFilter = (key, val) => setForm(f => ({
    ...f,
    filters: { ...f.filters, [key]: val || undefined },
  }))

  const handleSave = () => {
    if (!form.name.trim()) return
    // 清理空 filter
    const filters = {}
    for (const [k, v] of Object.entries(form.filters || {})) {
      if (v !== undefined && v !== '' && v !== null) filters[k] = v
    }
    onSave({ ...form, filters })
  }

  const intervalOptions = [
    { label: '1 小时', value: 60 },
    { label: '3 小时', value: 180 },
    { label: '6 小时', value: 360 },
    { label: '12 小时', value: 720 },
    { label: '24 小时', value: 1440 },
  ]

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
         onClick={onClose}>
      <div className="card p-4 sm:p-6 w-full max-w-xl mx-3 sm:mx-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white mb-4">
          {task ? '编辑任务' : '新建定时任务'}
        </h3>

        <div className="space-y-4">
          {/* 任务名称 */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">任务名称</label>
            <input
              type="text"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder="如: 每日随机电影"
              className="input text-sm w-full"
            />
          </div>

          {/* 执行间隔 + 类型 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">执行间隔</label>
              <select
                value={form.interval_minutes}
                onChange={e => set('interval_minutes', Number(e.target.value))}
                className="input text-sm w-full"
              >
                {intervalOptions.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">影视类型</label>
              <select
                value={form.media_type}
                onChange={e => set('media_type', e.target.value)}
                className="input text-sm w-full"
              >
                <option value="movie">电影</option>
                <option value="tv">剧集</option>
              </select>
            </div>
          </div>

          {/* 数据源 */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">数据源</label>
            <select
              value={form.source || 'tmdb'}
              onChange={e => set('source', e.target.value)}
              className="input text-sm w-full"
            >
              <option value="tmdb">TMDB</option>
              <option value="douban">豆瓣</option>
            </select>
          </div>

          {/* 数量 + 保存路径 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">每次数量</label>
              <input
                type="number"
                value={form.count}
                onChange={e => set('count', Math.max(1, Math.min(20, Number(e.target.value))))}
                min={1}
                max={20}
                className="input text-sm w-full"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">保存根路径</label>
              <input
                type="text"
                value={form.save_base_path}
                onChange={e => set('save_base_path', e.target.value)}
                className="input text-sm w-full font-mono"
              />
            </div>
          </div>

          {/* 筛选条件 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 flex items-center gap-1.5">
              <Filter size={12} /> 筛选条件
            </label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-gray-600 mb-1 block">最低评分</label>
                <input
                  type="number"
                  value={form.filters.min_rating || ''}
                  onChange={e => setFilter('min_rating', e.target.value ? Number(e.target.value) : undefined)}
                  placeholder="如 7.0"
                  step={0.5}
                  min={0}
                  max={10}
                  className="input text-xs w-full"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-600 mb-1 block">类型</label>
                <select
                  value={form.filters.genre || ''}
                  onChange={e => setFilter('genre', e.target.value)}
                  className="input text-xs w-full"
                >
                  <option value="">全部</option>
                  {(genres || []).map(g => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-gray-600 mb-1 block">发行年份</label>
                <input
                  type="number"
                  value={form.filters.year || ''}
                  onChange={e => setFilter('year', e.target.value ? Number(e.target.value) : undefined)}
                  placeholder="如 2024"
                  className="input text-xs w-full"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-600 mb-1 block">豆瓣标签</label>
                <input
                  type="text"
                  value={form.filters.tag || ''}
                  onChange={e => setFilter('tag', e.target.value)}
                  placeholder="如 热门/科幻/华语"
                  className="input text-xs w-full"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-600 mb-1 block">国家/地区</label>
                <select
                  value={form.filters.country || ''}
                  onChange={e => setFilter('country', e.target.value)}
                  className="input text-xs w-full"
                >
                  <option value="">全部</option>
                  <option value="US">美国</option>
                  <option value="CN">中国</option>
                  <option value="JP">日本</option>
                  <option value="KR">韩国</option>
                  <option value="GB">英国</option>
                  <option value="FR">法国</option>
                  <option value="DE">德国</option>
                  <option value="IN">印度</option>
                  <option value="HK">中国香港</option>
                  <option value="TW">中国台湾</option>
                </select>
              </div>
            </div>
          </div>

          {/* 开关选项 */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.check_media_lib}
                onChange={e => set('check_media_lib', e.target.checked)}
                className="rounded"
              />
              <Library size={14} className="text-gray-500" />
              媒体库查重 (已有则跳过)
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.bot_notify}
                onChange={e => set('bot_notify', e.target.checked)}
                className="rounded"
              />
              <Bell size={14} className="text-gray-500" />
              飞书机器人通知
            </label>
          </div>

          {/* 通知人 */}
          {form.bot_notify && (
            <div>
              <label className="text-[10px] text-gray-600 mb-1 block">通知人 Open ID (可选，空则使用全局配置)</label>
              <input
                type="text"
                value={form.notify_open_id}
                onChange={e => set('notify_open_id', e.target.value)}
                placeholder="ou_xxxxxxxx (飞书用户 Open ID)"
                className="input text-xs w-full font-mono"
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="btn-ghost text-sm">取消</button>
          <button
            onClick={handleSave}
            disabled={!form.name.trim()}
            className="btn-primary text-sm"
          >
            {task ? '保存修改' : '创建任务'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════
   任务卡片
   ════════════════════════════════════════════════ */
function TaskCard({ task, index, status, onToggle, onTrigger, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [triggering, setTriggering] = useState(false)

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      await onTrigger(index)
    } finally {
      setTimeout(() => setTriggering(false), 2000)
    }
  }

  const lastResult = status?.last_result
  const isRunning = status?.running

  return (
    <div className={`card overflow-hidden transition-colors
      ${!task.enabled ? 'opacity-50' : ''}`}>
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-3">
        {/* 状态图标 */}
        <button
          onClick={() => onToggle(index)}
          className={`flex-shrink-0 p-1.5 rounded-lg transition-colors
            ${task.enabled
              ? 'bg-green-500/10 text-green-400 hover:bg-green-500/20'
              : 'bg-surface-2 text-gray-600 hover:text-gray-400'
            }`}
          title={task.enabled ? '点击禁用' : '点击启用'}
        >
          <Power size={16} />
        </button>

        {/* 名称 + 基本信息 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate">{task.name}</span>
            {isRunning && (
              <span className="flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                <Loader2 size={10} className="animate-spin" /> 执行中
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 sm:gap-3 mt-0.5 text-[10px] text-gray-500 flex-wrap">
            {task.source && task.source !== 'tmdb' && (
              <span className="px-1 py-0.5 rounded bg-green-500/10 text-green-400">
                {task.source === 'douban' ? '豆瓣' : task.source}
              </span>
            )}
            <span className="flex items-center gap-1">
              {task.media_type === 'tv' ? <Tv size={10} /> : <Film size={10} />}
              {task.media_type === 'tv' ? '剧集' : '电影'}
            </span>
            <span className="flex items-center gap-1">
              <Shuffle size={10} /> {task.count} 部/次
            </span>
            <span className="flex items-center gap-1">
              <Clock size={10} /> 每 {task.interval_minutes >= 60
                ? `${task.interval_minutes / 60}h`
                : `${task.interval_minutes}m`}
            </span>
            {task.check_media_lib && (
              <span className="flex items-center gap-1">
                <Library size={10} /> 查重
              </span>
            )}
            {task.bot_notify && (
              <span className="flex items-center gap-1">
                <Bell size={10} /> 通知
              </span>
            )}
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={handleTrigger}
            disabled={triggering || isRunning || !task.enabled}
            className="p-1.5 rounded-lg text-gray-500 hover:text-brand-400 hover:bg-surface-2
                       disabled:opacity-30 transition-colors"
            title="立即执行"
          >
            {triggering ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
          </button>
          <button
            onClick={() => onEdit(index)}
            className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-surface-2 transition-colors"
            title="编辑"
          >
            <Settings size={15} />
          </button>
          <button
            onClick={() => onDelete(index)}
            className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-surface-2 transition-colors"
            title="删除"
          >
            <Trash2 size={15} />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg text-gray-600 hover:text-gray-400 transition-colors"
          >
            {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          </button>
        </div>
      </div>

      {/* 调度时间 */}
      {task.enabled && status && (
        <div className="px-4 pb-2 flex items-center gap-4 text-[10px] text-gray-500">
          {status.last_run && (
            <span className="flex items-center gap-1">
              <Clock size={10} className="text-gray-600" />
              上次: {new Date(status.last_run).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })}
            </span>
          )}
          {status.next_run && (
            <span className="flex items-center gap-1 text-brand-400">
              <Calendar size={10} />
              下次: {new Date(status.next_run).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })}
            </span>
          )}
        </div>
      )}

      {/* 筛选标签 */}
      {Object.keys(task.filters || {}).length > 0 && (
        <div className="px-4 pb-2 flex items-center gap-1.5 flex-wrap">
          {task.filters.min_rating && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">
              ★ ≥ {task.filters.min_rating}
            </span>
          )}
          {task.filters.genre && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
              {task.filters.genre}
            </span>
          )}
          {task.filters.year && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
              {task.filters.year}
            </span>
          )}
          {task.filters.tag && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
              标签: {task.filters.tag}
            </span>
          )}
          {task.filters.country && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
              {task.filters.country}
            </span>
          )}
        </div>
      )}

      {/* 展开: 最近执行结果 */}
      {expanded && lastResult && (
        <div className="px-4 py-3 border-t border-white/5 bg-surface-1/50">
          <div className="text-[10px] text-gray-600 mb-2">
            最近执行: {lastResult.timestamp ? new Date(lastResult.timestamp).toLocaleString() : '-'}
          </div>

          {lastResult.error ? (
            <div className="text-xs text-red-400 flex items-center gap-1">
              <XCircle size={12} /> {lastResult.error}
            </div>
          ) : (
            <div className="space-y-1">
              <div className="flex items-center gap-3 text-xs text-gray-400">
                {lastResult.saved?.length > 0 && (
                  <span className="text-green-400">✅ 转存 {lastResult.saved.length} 部</span>
                )}
                {lastResult.failed?.length > 0 && (
                  <span className="text-red-400">❌ 失败 {lastResult.failed.length} 部</span>
                )}
                {lastResult.skipped_existing > 0 && (
                  <span className="text-gray-500">⏭️ 已有 {lastResult.skipped_existing} 部</span>
                )}
              </div>

              {/* 成功列表 */}
              {lastResult.saved?.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-green-400/80 pl-2">
                  <CheckCircle2 size={11} />
                  <span>{s.title}{s.year ? ` (${s.year})` : ''}</span>
                  <span className="text-gray-600">→ {s.save_path}</span>
                </div>
              ))}

              {/* 失败列表 */}
              {lastResult.failed?.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-red-400/80 pl-2">
                  <XCircle size={11} />
                  <span>{f.title}{f.year ? ` (${f.year})` : ''}</span>
                  <span className="text-gray-600">- {f.error}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {expanded && !lastResult && (
        <div className="px-4 py-3 border-t border-white/5 text-xs text-gray-600">
          尚未执行过
        </div>
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════
   主页面
   ════════════════════════════════════════════════ */
export default function SchedulerPage() {
  const [tasks, setTasks] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showEditor, setShowEditor] = useState(false)
  const [editingIndex, setEditingIndex] = useState(null)
  const [genres, setGenres] = useState([])

  const fetchAll = useCallback(async () => {
    try {
      const [tasksData, statusData] = await Promise.all([
        schedulerApi.tasks(),
        schedulerApi.status(),
      ])
      setTasks(tasksData.tasks || [])
      setStatus(statusData)
      setLoading(false)
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    // 加载类型列表
    discoveryApi.genres('movie').then(g => setGenres(g)).catch(() => {})
  }, [fetchAll])

  // 定时刷新状态 (有任务运行时)
  useEffect(() => {
    const hasRunning = status?.tasks?.some(t => t.running)
    if (!hasRunning) return
    const timer = setInterval(fetchAll, 5000)
    return () => clearInterval(timer)
  }, [status, fetchAll])

  const handleCreate = async (task) => {
    try {
      await schedulerApi.create(task)
      setShowEditor(false)
      fetchAll()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleUpdate = async (task) => {
    try {
      await schedulerApi.update(editingIndex, task)
      setShowEditor(false)
      setEditingIndex(null)
      fetchAll()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleToggle = async (index) => {
    try {
      await schedulerApi.toggle(index)
      fetchAll()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleTrigger = async (index) => {
    try {
      await schedulerApi.trigger(index)
      // 延迟刷新 (等任务开始)
      setTimeout(fetchAll, 1000)
    } catch (e) {
      setError(e.message)
    }
  }

  const handleDelete = async (index) => {
    if (!confirm('确定删除此任务？')) return
    try {
      await schedulerApi.remove(index)
      fetchAll()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleEdit = (index) => {
    setEditingIndex(index)
    setShowEditor(true)
  }

  const handleSchedulerToggle = async () => {
    try {
      if (status?.running) {
        await schedulerApi.stop()
      } else {
        await schedulerApi.start()
      }
      fetchAll()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader title="定时任务" description="自动发现 + 搜索 + 转存" />
        <div className="flex items-center justify-center py-20 text-gray-500">
          <Loader2 size={20} className="animate-spin mr-2" /> 加载中...
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title="定时任务" description="自动从 TMDB/豆瓣 发现影视 → 搜索网盘 → 转存" />

      {error && <ErrorBanner message={error} />}

      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={handleSchedulerToggle}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors
              ${status?.running
                ? 'bg-green-500/10 text-green-400 hover:bg-green-500/20'
                : 'bg-surface-2 text-gray-400 hover:text-gray-200'
              }`}
          >
            {status?.running
              ? <><Pause size={15} /> 调度器运行中</>
              : <><Play size={15} /> 启动调度器</>
            }
          </button>
          <span className="text-xs text-gray-600">
            {tasks.length} 个任务 · {tasks.filter(t => t.enabled).length} 个启用
          </span>
        </div>

        <button
          onClick={() => { setEditingIndex(null); setShowEditor(true) }}
          className="btn-primary text-sm flex items-center gap-1.5"
        >
          <Plus size={15} /> 新建任务
        </button>
      </div>

      {/* 任务列表 */}
      {tasks.length > 0 ? (
        <div className="space-y-2">
          {tasks.map((task, index) => {
            const taskStatus = status?.tasks?.find(t => t.name === task.name)
            return (
              <TaskCard
                key={index}
                task={task}
                index={index}
                status={taskStatus}
                onToggle={handleToggle}
                onTrigger={handleTrigger}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            )
          })}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <Clock size={40} className="mx-auto mb-3 text-gray-700" />
          <p className="text-gray-400 mb-1">还没有定时任务</p>
          <p className="text-xs text-gray-600 mb-4">
            创建一个定时任务，自动从 TMDB/豆瓣 随机发现影视并搜索转存到网盘
          </p>
          <button
            onClick={() => { setEditingIndex(null); setShowEditor(true) }}
            className="btn-primary text-sm"
          >
            <Plus size={14} className="inline mr-1" /> 创建第一个任务
          </button>
        </div>
      )}

      {/* 编辑器弹窗 */}
      {showEditor && (
        <TaskEditor
          task={editingIndex !== null ? tasks[editingIndex] : null}
          genres={genres}
          onSave={editingIndex !== null ? handleUpdate : handleCreate}
          onClose={() => { setShowEditor(false); setEditingIndex(null) }}
        />
      )}
    </>
  )
}
