/**
 * qBittorrent 管理页面
 * 连接状态 / 种子列表 / 手动添加 / 配置管理
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Download, Plus, RefreshCw, Settings2, Loader2, CheckCircle,
  AlertCircle, X, ArrowUpDown, Pause, Play, Clock, HardDrive,
  Magnet, Link2, Filter, Search, Zap,
} from 'lucide-react'
import { torrentApi } from '../api/client'

// ── 工具函数 ──

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return '—'
  return formatBytes(bytesPerSec) + '/s'
}

function formatProgress(progress) {
  return (progress * 100).toFixed(1) + '%'
}

function formatEta(seconds) {
  if (!seconds || seconds <= 0 || seconds >= 8640000) return '—'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  return `${Math.floor(seconds / 86400)}d`
}

function timeAgo(ts) {
  if (!ts || ts <= 0) return '—'
  const diff = (Date.now() / 1000) - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}m 前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h 前`
  return `${Math.floor(diff / 86400)}d 前`
}

const STATE_MAP = {
  downloading: { label: '下载中', color: 'text-blue-400 bg-blue-500/20', icon: Download },
  uploading: { label: '做种中', color: 'text-green-400 bg-green-500/20', icon: ArrowUpDown },
  stalledDL: { label: '等待下载', color: 'text-yellow-400 bg-yellow-500/20', icon: Clock },
  stalledUP: { label: '等待做种', color: 'text-gray-400 bg-gray-500/20', icon: Clock },
  pausedDL: { label: '已暂停', color: 'text-orange-400 bg-orange-500/20', icon: Pause },
  pausedUP: { label: '已完成', color: 'text-green-400 bg-green-500/20', icon: CheckCircle },
  queuedDL: { label: '排队中', color: 'text-purple-400 bg-purple-500/20', icon: Clock },
  queuedUP: { label: '排队做种', color: 'text-purple-400 bg-purple-500/20', icon: Clock },
  checkingDL: { label: '校验中', color: 'text-cyan-400 bg-cyan-500/20', icon: Loader2 },
  checkingUP: { label: '校验中', color: 'text-cyan-400 bg-cyan-500/20', icon: Loader2 },
  moving: { label: '移动中', color: 'text-cyan-400 bg-cyan-500/20', icon: Loader2 },
  error: { label: '错误', color: 'text-red-400 bg-red-500/20', icon: AlertCircle },
  missingFiles: { label: '文件丢失', color: 'text-red-400 bg-red-500/20', icon: AlertCircle },
  unknown: { label: '未知', color: 'text-gray-400 bg-gray-500/20', icon: Clock },
}

function StateBadge({ state }) {
  const info = STATE_MAP[state] || STATE_MAP.unknown
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${info.color}`}>
      {state === 'downloading' || state === 'checkingDL' || state === 'checkingUP' || state === 'moving'
        ? <Loader2 size={10} className="animate-spin" />
        : null
      }
      {info.label}
    </span>
  )
}

const FILTER_OPTIONS = [
  { key: 'all',         label: '全部' },
  { key: 'downloading', label: '下载中' },
  { key: 'seeding',     label: '做种' },
  { key: 'completed',   label: '已完成' },
  { key: 'paused',      label: '已暂停' },
  { key: 'active',      label: '活跃' },
]

// ── 添加种子弹窗 ──

function AddModal({ onClose, onAdded }) {
  const [url, setUrl] = useState('')
  const [savePath, setSavePath] = useState('')
  const [category, setCategory] = useState('')
  const [tags, setTags] = useState('')
  const [paused, setPaused] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const isMagnet = url.trim().startsWith('magnet:')

  const handleAdd = async () => {
    if (!url.trim()) return
    setLoading(true)
    setError('')
    try {
      const data = { url: url.trim() }
      if (savePath.trim()) data.save_path = savePath.trim()
      if (category.trim()) data.category = category.trim()
      if (tags.trim()) data.tags = tags.trim()
      if (paused) data.paused = true
      const result = await torrentApi.add(data)
      if (result.success) {
        onAdded()
      } else {
        setError(result.error || '添加失败')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-lg">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2">
            <Plus size={18} className="text-brand-400" />
            添加种子
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        <div className="p-4 space-y-3">
          <label className="block">
            <span className="text-xs text-gray-400 mb-1 block">磁力链接 / Torrent URL *</span>
            <textarea
              value={url} onChange={e => setUrl(e.target.value)}
              placeholder="magnet:?xt=urn:btih:... 或 https://...torrent"
              rows={3}
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm
                         focus:outline-none focus:border-brand-500 resize-none font-mono"
            />
            {url.trim() && (
              <div className="flex items-center gap-1.5 mt-1">
                {isMagnet
                  ? <><Magnet size={12} className="text-purple-400" /><span className="text-xs text-purple-400">磁力链接</span></>
                  : <><Link2 size={12} className="text-blue-400" /><span className="text-xs text-blue-400">Torrent URL</span></>
                }
              </div>
            )}
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-gray-400 mb-1 block">保存路径</span>
              <input type="text" value={savePath} onChange={e => setSavePath(e.target.value)}
                placeholder="/downloads/movies"
                className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500" />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400 mb-1 block">分类</span>
              <input type="text" value={category} onChange={e => setCategory(e.target.value)}
                placeholder="movies"
                className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500" />
            </label>
          </div>

          <label className="block">
            <span className="text-xs text-gray-400 mb-1 block">标签 (逗号分隔)</span>
            <input type="text" value={tags} onChange={e => setTags(e.target.value)}
              placeholder="rss, 4k"
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500" />
          </label>

          <label className="flex items-center gap-2">
            <input type="checkbox" checked={paused} onChange={e => setPaused(e.target.checked)}
              className="rounded border-surface-3" />
            <span className="text-sm text-gray-300">添加后暂停</span>
          </label>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-xs p-2 bg-red-500/10 rounded-lg">
              <AlertCircle size={14} />{error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button onClick={handleAdd} disabled={loading || !url.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2">
            {loading && <Loader2 size={14} className="animate-spin" />}
            添加
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 配置弹窗 ──

function ConfigModal({ onClose, onSaved }) {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ id: 'default', host: '127.0.0.1', port: 8080, username: 'admin', password: '', use_https: false })

  useEffect(() => {
    torrentApi.config()
      .then(c => {
        setConfig(c)
        const qb = (c.qbittorrent || [])[0]
        if (qb) setForm({ ...form, ...qb })
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, []) // eslint-disable-line

  const handleSave = async () => {
    setSaving(true)
    try {
      await torrentApi.updateConfig({
        default: form.id,
        qbittorrent: [{ ...form, port: Number(form.port) }],
      })
      onSaved()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const F = (label, key, type = 'text', placeholder = '') => (
    <label className="block">
      <span className="text-xs text-gray-400 mb-1 block">{label}</span>
      <input type={type} value={form[key] ?? ''} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500" />
    </label>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2">
            <Settings2 size={18} className="text-brand-400" />
            qBittorrent 配置
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        {loading ? (
          <div className="p-8 text-center"><Loader2 size={24} className="animate-spin mx-auto text-brand-400" /></div>
        ) : (
          <div className="p-4 space-y-3">
            {F('实例 ID', 'id', 'text', 'default')}
            <div className="grid grid-cols-3 gap-3">
              {F('Host', 'host', 'text', '127.0.0.1')}
              {F('Port', 'port', 'number', '8080')}
              <label className="block">
                <span className="text-xs text-gray-400 mb-1 block">HTTPS</span>
                <div className="flex items-center h-[38px]">
                  <input type="checkbox" checked={form.use_https}
                    onChange={e => setForm(f => ({ ...f, use_https: e.target.checked }))}
                    className="rounded border-surface-3" />
                </div>
              </label>
            </div>
            {F('用户名', 'username', 'text', 'admin')}
            {F('密码', 'password', 'password', '密码')}
          </div>
        )}

        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2">
            {saving && <Loader2 size={14} className="animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 主页面 ──

export default function TorrentPage() {
  const [torrents, setTorrents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(null) // null=unknown, true/false
  const [version, setVersion] = useState('')
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [showConfig, setShowConfig] = useState(false)

  const fetchTorrents = useCallback(async () => {
    try {
      const result = await torrentApi.list({ filter, limit: 100 })
      setTorrents(result.torrents || [])
      setConnected(true)
      setError(null)
    } catch (e) {
      setError(e.message)
      if (e.message.includes('未配置') || e.message.includes('连接失败') || e.message.includes('登录失败')) {
        setConnected(false)
      }
    } finally {
      setLoading(false)
    }
  }, [filter])

  const checkConnection = useCallback(async () => {
    try {
      const result = await torrentApi.test()
      setConnected(result.success)
      setVersion(result.version || '')
      if (result.success) fetchTorrents()
      else setLoading(false)
    } catch (e) {
      setConnected(false)
      setLoading(false)
    }
  }, [fetchTorrents])

  useEffect(() => {
    checkConnection()
  }, []) // eslint-disable-line

  useEffect(() => {
    if (connected) {
      fetchTorrents()
      const timer = setInterval(fetchTorrents, 5000)
      return () => clearInterval(timer)
    }
  }, [connected, filter, fetchTorrents])

  // 搜索过滤
  const filtered = search.trim()
    ? torrents.filter(t => t.name?.toLowerCase().includes(search.toLowerCase()))
    : torrents

  // 统计
  const stats = {
    total: torrents.length,
    downloading: torrents.filter(t => t.state === 'downloading' || t.state === 'stalledDL').length,
    seeding: torrents.filter(t => t.state === 'uploading' || t.state === 'stalledUP').length,
    completed: torrents.filter(t => t.progress >= 1).length,
    dlSpeed: torrents.reduce((s, t) => s + (t.dlspeed || 0), 0),
    upSpeed: torrents.reduce((s, t) => s + (t.upspeed || 0), 0),
  }

  // 未连接状态
  if (connected === false) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-3">
              <Download className="text-green-400" size={24} />
              qBittorrent
            </h1>
            <p className="text-sm text-gray-500 mt-1">种子下载管理</p>
          </div>
        </div>

        <div className="bg-surface-1 border border-surface-3 rounded-xl p-12 text-center">
          <AlertCircle size={48} className="mx-auto text-yellow-400 mb-4" />
          <h3 className="text-lg font-semibold mb-2">未连接 qBittorrent</h3>
          <p className="text-sm text-gray-500 mb-2">
            {error || '请先配置 qBittorrent Web UI 的连接信息'}
          </p>
          <p className="text-xs text-gray-600 mb-6">
            确保 qBittorrent 已启用 Web UI，并且地址和端口可访问
          </p>
          <div className="flex items-center justify-center gap-3">
            <button onClick={() => setShowConfig(true)}
              className="flex items-center gap-2 px-6 py-2.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition">
              <Settings2 size={16} /> 配置连接
            </button>
            <button onClick={() => { setLoading(true); checkConnection() }}
              className="flex items-center gap-2 px-6 py-2.5 border border-surface-3 hover:bg-surface-2 rounded-lg text-sm transition">
              <RefreshCw size={16} /> 重试
            </button>
          </div>
        </div>

        {showConfig && <ConfigModal onClose={() => setShowConfig(false)} onSaved={() => { setShowConfig(false); checkConnection() }} />}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-3">
            <Download className="text-green-400" size={24} />
            qBittorrent
            {version && <span className="text-xs text-gray-500 font-normal">{version}</span>}
          </h1>
          <p className="text-sm text-gray-500 mt-1">种子下载管理</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/20 text-green-400 animate-pulse">已连接</span>
          <button onClick={() => setShowConfig(true)} className="p-2 rounded-lg hover:bg-surface-2 transition" title="配置">
            <Settings2 size={16} />
          </button>
          <button onClick={fetchTorrents} className="p-2 rounded-lg hover:bg-surface-2 transition" title="刷新">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition">
            <Plus size={16} /> 添加种子
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-white">{stats.total}</div>
          <div className="text-xs text-gray-500">总数</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-blue-400">{stats.downloading}</div>
          <div className="text-xs text-gray-500">下载中</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-green-400">{stats.seeding}</div>
          <div className="text-xs text-gray-500">做种</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-brand-400">{stats.completed}</div>
          <div className="text-xs text-gray-500">已完成</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-blue-400">{formatSpeed(stats.dlSpeed)}</div>
          <div className="text-xs text-gray-500">↓ 下载速度</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-green-400">{formatSpeed(stats.upSpeed)}</div>
          <div className="text-xs text-gray-500">↑ 上传速度</div>
        </div>
      </div>

      {/* 筛选 + 搜索 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-surface-1 border border-surface-3 rounded-lg p-1">
          {FILTER_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => setFilter(opt.key)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                ${filter === opt.key ? 'bg-brand-600 text-white' : 'text-gray-400 hover:text-white hover:bg-surface-2'}`}>
              {opt.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="搜索种子名称..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-surface-1 border border-surface-3 rounded-lg
                       focus:outline-none focus:border-brand-500 placeholder:text-gray-600" />
        </div>
      </div>

      {/* Torrent List */}
      {loading ? (
        <div className="text-center py-12">
          <Loader2 size={32} className="animate-spin mx-auto text-brand-400 mb-3" />
          <p className="text-sm text-gray-500">加载中...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-12 text-center">
          <Download size={48} className="mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold mb-2">
            {search ? '未找到匹配的种子' : '暂无种子'}
          </h3>
          <p className="text-sm text-gray-500">
            {search ? '换个关键词试试' : '点击右上角添加种子或磁力链接'}
          </p>
        </div>
      ) : (
        <div className="bg-surface-1 border border-surface-3 rounded-xl overflow-hidden">
          <div className="divide-y divide-surface-3">
            {filtered.map((t, i) => (
              <div key={t.hash || i} className="p-4 hover:bg-surface-2/50 transition">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-sm truncate" title={t.name}>{t.name || '(未知)'}</h4>
                      <StateBadge state={t.state} />
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{formatBytes(t.size)}</span>
                      {t.category && (
                        <span className="px-1.5 py-0.5 rounded bg-surface-3 text-gray-400">{t.category}</span>
                      )}
                      {t.tags && (
                        <span className="text-gray-600">{t.tags}</span>
                      )}
                      <span>添加: {timeAgo(t.added_on)}</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-sm font-medium">{formatProgress(t.progress)}</div>
                    <div className="text-xs text-gray-500">
                      {t.dlspeed > 0 && <span className="text-blue-400">↓{formatSpeed(t.dlspeed)}</span>}
                      {t.dlspeed > 0 && t.upspeed > 0 && <span className="mx-1">·</span>}
                      {t.upspeed > 0 && <span className="text-green-400">↑{formatSpeed(t.upspeed)}</span>}
                    </div>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="mt-2 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500
                      ${t.progress >= 1 ? 'bg-green-500' : 'bg-brand-500'}`}
                    style={{ width: `${(t.progress * 100).toFixed(1)}%` }}
                  />
                </div>
                {/* Extra info */}
                <div className="flex items-center gap-4 mt-1.5 text-[10px] text-gray-600">
                  {t.eta > 0 && t.eta < 8640000 && <span>ETA: {formatEta(t.eta)}</span>}
                  <span>↓ {formatBytes(t.downloaded)}</span>
                  <span>↑ {formatBytes(t.uploaded)}</span>
                  {t.ratio >= 0 && <span>比率: {t.ratio.toFixed(2)}</span>}
                  {t.num_seeds >= 0 && <span>种子: {t.num_seeds}</span>}
                  {t.num_leechs >= 0 && <span>下载者: {t.num_leechs}</span>}
                  {t.save_path && <span className="truncate max-w-[200px]" title={t.save_path}>路径: {t.save_path}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modals */}
      {showAdd && <AddModal onClose={() => setShowAdd(false)} onAdded={() => { setShowAdd(false); fetchTorrents() }} />}
      {showConfig && <ConfigModal onClose={() => setShowConfig(false)} onSaved={() => { setShowConfig(false); checkConnection() }} />}
    </div>
  )
}
