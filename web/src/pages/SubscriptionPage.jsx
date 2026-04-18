import { useState, useEffect, useCallback } from 'react'
import { Tv, Plus, Play, Pause, RefreshCw, Trash2, ChevronDown, ChevronUp, RotateCcw, Edit3, X, Check, Loader2 } from 'lucide-react'

const API = '/api'

function timeAgo(ts) {
  if (!ts) return '从未'
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

function ProgressBar({ current, total, className = '' }) {
  const pct = total ? Math.min(Math.round((current / total) * 100), 100) : 0
  return (
    <div className={`h-2 bg-surface-3 rounded-full overflow-hidden ${className}`}>
      <div
        className="h-full bg-brand-500 rounded-full transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function StatusBadge({ enabled, finished, running }) {
  if (running) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/20 text-blue-400 animate-pulse">检查中</span>
  if (finished) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/20 text-green-400">已完结</span>
  if (!enabled) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-500/20 text-gray-400">已暂停</span>
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-500/20 text-brand-400">追更中</span>
}

// ── 新增 / 编辑 弹窗 ──

function SubModal({ sub, onClose, onSave }) {
  const isEdit = !!sub
  const [form, setForm] = useState({
    name: '', keyword: '', season: 1, next_episode: 1,
    max_episode: '', quality: '4K|2160p|1080p',
    save_path: '/追剧', interval_minutes: 240,
    bot_notify: true, enabled: true,
    ...(sub || {}),
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        ...form,
        max_episode: form.max_episode ? Number(form.max_episode) : null,
        season: Number(form.season),
        next_episode: Number(form.next_episode),
        interval_minutes: Number(form.interval_minutes),
      }
      const url = isEdit ? `${API}/subscriptions/${encodeURIComponent(sub.name)}` : `${API}/subscriptions`
      const method = isEdit ? 'PUT' : 'POST'
      const resp = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '操作失败')
      }
      onSave()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const F = (label, key, type = 'text', placeholder = '') => (
    <label className="block">
      <span className="text-xs text-gray-400 mb-1 block">{label}</span>
      <input
        type={type}
        value={form[key] ?? ''}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
      />
    </label>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold">{isEdit ? '编辑订阅' : '新增订阅'}</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        <div className="p-4 space-y-3">
          {F('剧名 *', 'name', 'text', '如: 三体')}
          {F('搜索关键词', 'keyword', 'text', '留空则使用剧名')}

          <div className="grid grid-cols-3 gap-3">
            {F('季号', 'season', 'number')}
            {F('从第几集', 'next_episode', 'number')}
            {F('总集数', 'max_episode', 'number', '可留空')}
          </div>

          {F('画质偏好', 'quality', 'text', '正则, 如 4K|2160p|1080p')}
          {F('存储路径', 'save_path', 'text', '/追剧/三体/S01')}

          <div className="grid grid-cols-2 gap-3">
            {F('检查间隔(分钟)', 'interval_minutes', 'number')}
            <label className="flex items-center gap-2 pt-5">
              <input
                type="checkbox" checked={form.bot_notify}
                onChange={e => setForm(f => ({ ...f, bot_notify: e.target.checked }))}
                className="rounded border-surface-3"
              />
              <span className="text-sm text-gray-300">飞书通知</span>
            </label>
          </div>
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button
            onClick={handleSave} disabled={saving || !form.name.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {isEdit ? '保存' : '开始追更'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 单个订阅卡片 ──

function SubCard({ sub, onRefresh }) {
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)

  const episodes = sub.episodes_found || []
  const lastEp = sub.last_episode || 0
  const maxEp = sub.max_episode
  const pctText = maxEp ? `${lastEp} / ${maxEp} 集` : `已追到 E${String(lastEp).padStart(2, '0')}`

  const action = async (url, method = 'POST', body = null) => {
    setLoading(true)
    try {
      const opts = { method, headers: { 'Content-Type': 'application/json' } }
      if (body) opts.body = JSON.stringify(body)
      const resp = await fetch(url, opts)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '操作失败')
      }
      onRefresh()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="bg-surface-1 border border-surface-3 rounded-xl p-4 hover:border-surface-4 transition">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-brand-600/20 rounded-lg flex items-center justify-center">
              <Tv size={20} className="text-brand-400" />
            </div>
            <div>
              <div className="font-semibold flex items-center gap-2">
                {sub.name}
                <StatusBadge enabled={sub.enabled} finished={sub.finished} running={sub.running} />
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                S{String(sub.season).padStart(2, '0')} · {pctText}
                {sub.quality && <span className="ml-2 text-gray-600">· {sub.quality}</span>}
              </div>
            </div>
          </div>

          <button onClick={() => setExpanded(e => !e)} className="p-1 hover:bg-surface-2 rounded">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        {/* Progress */}
        {maxEp && <ProgressBar current={lastEp} total={maxEp} className="mb-3" />}

        {/* Info */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>上次检查: {timeAgo(sub.last_check)}</span>
          <span>每 {sub.interval_minutes >= 60 ? `${sub.interval_minutes / 60}h` : `${sub.interval_minutes}m`} 检查</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-surface-3">
          {!sub.finished && sub.enabled && (
            <button
              onClick={() => action(`${API}/subscriptions/${encodeURIComponent(sub.name)}/check`)}
              disabled={loading || sub.running}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-brand-600/20 text-brand-400 hover:bg-brand-600/30 disabled:opacity-50"
            >
              {sub.running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
              立即检查
            </button>
          )}

          {!sub.finished && (
            <button
              onClick={() => action(`${API}/subscriptions/${encodeURIComponent(sub.name)}/toggle`)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
            >
              {sub.enabled ? <Pause size={12} /> : <Play size={12} />}
              {sub.enabled ? '暂停' : '恢复'}
            </button>
          )}

          {sub.finished && (
            <button
              onClick={() => action(`${API}/subscriptions/${encodeURIComponent(sub.name)}/resume`, 'POST', {})}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-green-600/20 text-green-400 hover:bg-green-600/30"
            >
              <RotateCcw size={12} />
              重新追更
            </button>
          )}

          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
          >
            <Edit3 size={12} />
            编辑
          </button>

          <div className="flex-1" />

          <button
            onClick={() => { if (confirm(`确认删除订阅「${sub.name}」?`)) action(`${API}/subscriptions/${encodeURIComponent(sub.name)}`, 'DELETE') }}
            disabled={loading}
            className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
          >
            <Trash2 size={14} />
          </button>
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-surface-3 space-y-2 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div><span className="text-gray-500">搜索词:</span> <span className="text-gray-300">{sub.keyword}</span></div>
              <div><span className="text-gray-500">存储路径:</span> <span className="text-gray-300">{sub.save_path}</span></div>
              <div><span className="text-gray-500">Miss 次数:</span> <span className="text-gray-300">{sub.miss_count}</span></div>
              <div><span className="text-gray-500">下一集:</span> <span className="text-gray-300">S{String(sub.season).padStart(2, '0')}E{String(sub.next_episode).padStart(2, '0')}</span></div>
            </div>

            {episodes.length > 0 && (
              <div>
                <span className="text-gray-500">已追集数: </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {episodes.map(ep => (
                    <span key={ep} className="px-1.5 py-0.5 rounded bg-brand-600/20 text-brand-300 text-[10px]">
                      E{String(ep).padStart(2, '0')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {sub.last_result && sub.last_result.new_episodes && sub.last_result.new_episodes.length > 0 && (
              <div>
                <span className="text-gray-500">上次新增: </span>
                {sub.last_result.new_episodes.map((ep, i) => (
                  <span key={i} className="text-green-400">
                    E{String(ep.episode).padStart(2, '0')}{i < sub.last_result.new_episodes.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </div>
            )}

            {sub.last_result && sub.last_result.error && (
              <div className="text-red-400">错误: {sub.last_result.error}</div>
            )}
          </div>
        )}
      </div>

      {editing && (
        <SubModal sub={sub} onClose={() => setEditing(false)} onSave={() => { setEditing(false); onRefresh() }} />
      )}
    </>
  )
}


// ── 主页面 ──

export default function SubscriptionPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/subscriptions`)
      const json = await resp.json()
      setData(json)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 5000)
    return () => clearInterval(timer)
  }, [fetchData])

  const subs = data?.subscriptions || []
  const activeSubs = subs.filter(s => s.enabled && !s.finished)
  const finishedSubs = subs.filter(s => s.finished)
  const pausedSubs = subs.filter(s => !s.enabled && !s.finished)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-3">
            <Tv className="text-brand-400" size={24} />
            订阅追剧
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            自动检查新集 → 搜索 → 转存 → 同步 → 通知
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={fetchData} className="p-2 rounded-lg hover:bg-surface-2 transition">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition"
          >
            <Plus size={16} />
            新增订阅
          </button>
        </div>
      </div>

      {/* Stats */}
      {subs.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-brand-400">{subs.length}</div>
            <div className="text-xs text-gray-500">总订阅</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-blue-400">{activeSubs.length}</div>
            <div className="text-xs text-gray-500">追更中</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{finishedSubs.length}</div>
            <div className="text-xs text-gray-500">已完结</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-gray-400">{pausedSubs.length}</div>
            <div className="text-xs text-gray-500">已暂停</div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && subs.length === 0 && (
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-12 text-center">
          <Tv size={48} className="mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold mb-2">还没有订阅</h3>
          <p className="text-sm text-gray-500 mb-6">
            添加你正在追的剧，系统会自动检查新集并转存到网盘
          </p>
          <button
            onClick={() => setShowAdd(true)}
            className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition"
          >
            添加第一个订阅
          </button>
        </div>
      )}

      {/* Active subs */}
      {activeSubs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">追更中 ({activeSubs.length})</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {activeSubs.map(s => <SubCard key={s.name} sub={s} onRefresh={fetchData} />)}
          </div>
        </div>
      )}

      {/* Paused */}
      {pausedSubs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">已暂停 ({pausedSubs.length})</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {pausedSubs.map(s => <SubCard key={s.name} sub={s} onRefresh={fetchData} />)}
          </div>
        </div>
      )}

      {/* Finished */}
      {finishedSubs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">已完结 ({finishedSubs.length})</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {finishedSubs.map(s => <SubCard key={s.name} sub={s} onRefresh={fetchData} />)}
          </div>
        </div>
      )}

      {/* Modal */}
      {showAdd && (
        <SubModal onClose={() => setShowAdd(false)} onSave={() => { setShowAdd(false); fetchData() }} />
      )}
    </div>
  )
}
