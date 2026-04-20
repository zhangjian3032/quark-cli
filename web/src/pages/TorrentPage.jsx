/**
 * qBittorrent 管理页面
 * 多实例管理 / 任务排序 / 配置删除 / 暂停恢复删除
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Download, Plus, RefreshCw, Settings2, Loader2, CheckCircle,
  AlertCircle, X, ArrowUpDown, ArrowUp, ArrowDown, Pause, Play,
  Clock, HardDrive, Magnet, Link2, Filter, Search, Zap,
  Trash2, Star, Wifi, WifiOff, Eye, EyeOff, Save, ChevronDown,
  Server,
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
      {(state === 'downloading' || state === 'checkingDL' || state === 'checkingUP' || state === 'moving')
        && <Loader2 size={10} className="animate-spin" />
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

const SORT_OPTIONS = [
  { key: 'added_on', label: '添加时间' },
  { key: 'name',     label: '名称' },
  { key: 'size',     label: '大小' },
  { key: 'progress', label: '进度' },
  { key: 'dlspeed',  label: '下载速度' },
  { key: 'upspeed',  label: '上传速度' },
  { key: 'state',    label: '状态' },
]


// ── 排序表头 ──

function SortButton({ label, field, current, reverse, onSort }) {
  const active = current === field
  return (
    <button
      onClick={() => onSort(field)}
      className={`flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide transition-colors
        hover:text-white ${active ? 'text-brand-400' : 'text-gray-500'}`}
    >
      {label}
      {active
        ? (reverse ? <ArrowDown size={10} /> : <ArrowUp size={10} />)
        : <ArrowUpDown size={9} className="opacity-40" />
      }
    </button>
  )
}


// ── 添加种子弹窗 ──

function AddModal({ onClose, onAdded, clientId }) {
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
      if (clientId) data.client_id = clientId
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


// ── 多实例配置管理弹窗 ──

function ConfigModal({ onClose, onSaved }) {
  const [clients, setClients] = useState([])
  const [defaultId, setDefaultId] = useState('')
  const [loading, setLoading] = useState(true)
  const [editId, setEditId] = useState(null) // null = 新增
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '', host: '', port: 8080, username: 'admin', password: '',
    use_https: false, default_save_path: '', default_category: '',
  })
  const [showPwd, setShowPwd] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState({})
  const [testResult, setTestResult] = useState({})
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [error, setError] = useState('')

  const loadClients = useCallback(() => {
    torrentApi.clients()
      .then(d => {
        setClients(d.clients || [])
        setDefaultId(d.default || '')
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  useEffect(() => { loadClients() }, [loadClients])

  const resetForm = () => {
    setForm({ name: '', host: '', port: 8080, username: 'admin', password: '', use_https: false, default_save_path: '', default_category: '' })
    setEditId(null)
    setShowPwd(false)
  }

  const startEdit = (c) => {
    setEditId(c.id)
    setForm({
      name: c.name || '', host: c.host || '', port: c.port || 8080,
      username: c.username || 'admin', password: '',
      use_https: c.use_https || false,
      default_save_path: c.default_save_path || '',
      default_category: c.default_category || '',
    })
    setShowForm(true)
    setShowPwd(false)
  }

  const startAdd = () => {
    resetForm()
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.host.trim()) return
    setSaving(true)
    setError('')
    try {
      const payload = { ...form, port: Number(form.port) }
      if (editId && !payload.password) delete payload.password
      if (editId) {
        await torrentApi.updateClient(editId, payload)
      } else {
        await torrentApi.addClient(payload)
      }
      resetForm()
      setShowForm(false)
      loadClients()
      onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await torrentApi.deleteClient(id)
      setConfirmDeleteId(null)
      loadClients()
      onSaved()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleSetDefault = async (id) => {
    try {
      await torrentApi.setDefault(id)
      loadClients()
      onSaved()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleTest = async (id) => {
    setTesting(p => ({ ...p, [id]: true }))
    setTestResult(p => ({ ...p, [id]: null }))
    try {
      const result = await torrentApi.testClient(id)
      setTestResult(p => ({ ...p, [id]: result }))
    } catch (e) {
      setTestResult(p => ({ ...p, [id]: { success: false, error: e.message } }))
    } finally {
      setTesting(p => ({ ...p, [id]: false }))
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
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-lg max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2">
            <Settings2 size={18} className="text-brand-400" />
            qBittorrent 实例管理
          </h3>
          <div className="flex items-center gap-2">
            <button onClick={startAdd}
              className="flex items-center gap-1 px-3 py-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-xs font-medium transition">
              <Plus size={14} /> 添加
            </button>
            <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="p-8 text-center"><Loader2 size={24} className="animate-spin mx-auto text-brand-400" /></div>
          ) : clients.length === 0 && !showForm ? (
            <div className="p-8 text-center">
              <Server size={36} className="mx-auto text-gray-600 mb-3" />
              <p className="text-sm text-gray-500 mb-2">未配置任何 qBittorrent 实例</p>
              <button onClick={startAdd}
                className="px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition">
                添加实例
              </button>
            </div>
          ) : (
            <>
              {/* 实例列表 */}
              {clients.map(c => {
                const isDefault = c.id === defaultId
                const tr = testResult[c.id]
                return (
                  <div key={c.id}
                    className={`p-3 rounded-lg border transition-colors ${
                      isDefault ? 'bg-brand-600/5 border-brand-500/20' : 'bg-surface-2 border-surface-3'
                    }`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isDefault ? 'bg-brand-600/20 text-brand-400' : 'bg-surface-3 text-gray-500'
                      }`}>
                        <Server size={18} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white truncate">{c.name || c.id}</span>
                          {isDefault && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/15 text-brand-400 font-medium flex-shrink-0">默认</span>
                          )}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-0.5 truncate">
                          {c.use_https ? 'https' : 'http'}://{c.host}:{c.port}
                        </div>
                      </div>

                      <div className="flex items-center gap-0.5 flex-shrink-0">
                        {!isDefault && (
                          <button onClick={() => handleSetDefault(c.id)}
                            className="p-1.5 rounded hover:bg-brand-500/15 text-gray-500 hover:text-brand-400 transition" title="设为默认">
                            <Star size={14} />
                          </button>
                        )}
                        <button onClick={() => handleTest(c.id)} disabled={testing[c.id]}
                          className="p-1.5 rounded hover:bg-green-500/15 text-gray-500 hover:text-green-400 transition" title="测试">
                          {testing[c.id] ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
                        </button>
                        <button onClick={() => startEdit(c)}
                          className="p-1.5 rounded hover:bg-surface-3 text-gray-500 hover:text-white transition" title="编辑">
                          <Settings2 size={14} />
                        </button>
                        {confirmDeleteId === c.id ? (
                          <>
                            <button onClick={() => handleDelete(c.id)}
                              className="px-2 py-1 rounded text-[10px] bg-red-500/15 text-red-400 hover:bg-red-500/25">确认</button>
                            <button onClick={() => setConfirmDeleteId(null)}
                              className="px-1.5 py-1 rounded text-[10px] text-gray-500 hover:text-gray-300">取消</button>
                          </>
                        ) : (
                          <button onClick={() => setConfirmDeleteId(c.id)}
                            className="p-1.5 rounded hover:bg-red-500/15 text-gray-500 hover:text-red-400 transition" title="删除">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>

                    {tr && (
                      <div className={`mt-2 flex items-center gap-2 text-xs ${tr.success ? 'text-green-400' : 'text-red-400'}`}>
                        {tr.success ? <><Wifi size={12} /> 连接成功 — {tr.version}</> : <><WifiOff size={12} /> {tr.error}</>}
                      </div>
                    )}
                  </div>
                )
              })}

              {/* 添加/编辑表单 */}
              {showForm && (
                <div className="p-3 rounded-lg border border-brand-500/20 bg-surface-2 space-y-3">
                  <h4 className="text-xs font-semibold text-white">{editId ? '编辑实例' : '添加新实例'}</h4>
                  <div className="grid grid-cols-2 gap-3">
                    {F('名称', 'name', 'text', '如: 家里NAS')}
                    {F('主机地址 *', 'host', 'text', '192.168.1.100')}
                    {F('端口', 'port', 'number', '8080')}
                    {F('用户名', 'username', 'text', 'admin')}
                    <label className="block">
                      <span className="text-xs text-gray-400 mb-1 block">密码{editId ? ' (留空不改)' : ''}</span>
                      <div className="relative">
                        <input type={showPwd ? 'text' : 'password'}
                          value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                          placeholder={editId ? '留空不改' : '密码'}
                          className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500 pr-9" />
                        <button onClick={() => setShowPwd(!showPwd)} type="button"
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                          {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </label>
                    <label className="flex items-end gap-2 pb-2">
                      <input type="checkbox" checked={form.use_https}
                        onChange={e => setForm(f => ({ ...f, use_https: e.target.checked }))}
                        className="rounded border-surface-3" />
                      <span className="text-xs text-gray-400">HTTPS</span>
                    </label>
                    {F('默认下载路径', 'default_save_path', 'text', '/downloads')}
                    {F('默认分类', 'default_category', 'text', '可选')}
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={handleSave} disabled={saving || !form.host.trim()}
                      className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 rounded-lg text-xs font-medium flex items-center gap-1.5">
                      {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                      {editId ? '保存' : '添加'}
                    </button>
                    <button onClick={() => { setShowForm(false); resetForm() }}
                      className="px-4 py-2 text-xs text-gray-400 hover:text-white">取消</button>
                  </div>
                </div>
              )}
            </>
          )}

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-xs p-2 bg-red-500/10 rounded-lg">
              <AlertCircle size={14} />{error}
            </div>
          )}
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

  // 多实例
  const [clients, setClients] = useState([])
  const [defaultClientId, setDefaultClientId] = useState('')
  const [activeClientId, setActiveClientId] = useState('')

  // 过滤 + 排序
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('added_on')
  const [reverse, setReverse] = useState(true)
  const [search, setSearch] = useState('')

  // 任务操作
  const [actionLoading, setActionLoading] = useState({})
  const [confirmDelete, setConfirmDelete] = useState(null) // hash

  // 弹窗
  const [showAdd, setShowAdd] = useState(false)
  const [showConfig, setShowConfig] = useState(false)

  // 加载实例列表
  const loadClients = useCallback(() => {
    torrentApi.clients()
      .then(d => {
        const cl = d.clients || []
        setClients(cl)
        setDefaultClientId(d.default || '')
        setActiveClientId(prev => {
          if (prev && cl.some(c => c.id === prev)) return prev
          return d.default || cl[0]?.id || ''
        })
      })
      .catch(() => {})
  }, [])

  useEffect(() => { loadClients() }, [loadClients])

  // 获取任务
  const fetchTorrents = useCallback(async () => {
    if (!activeClientId) {
      setLoading(false)
      setConnected(false)
      return
    }
    try {
      const result = await torrentApi.list({
        filter, sort, reverse, limit: 100, clientId: activeClientId,
      })
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
  }, [filter, sort, reverse, activeClientId])

  const checkConnection = useCallback(async () => {
    if (!activeClientId) {
      setConnected(false)
      setLoading(false)
      return
    }
    try {
      const result = await torrentApi.test({ client_id: activeClientId })
      setConnected(result.success)
      setVersion(result.version || '')
      if (result.success) fetchTorrents()
      else setLoading(false)
    } catch (e) {
      setConnected(false)
      setLoading(false)
    }
  }, [activeClientId, fetchTorrents])

  useEffect(() => {
    setLoading(true)
    checkConnection()
  }, [activeClientId]) // eslint-disable-line

  // 定时刷新
  useEffect(() => {
    if (!connected) return
    fetchTorrents()
    const timer = setInterval(fetchTorrents, 5000)
    return () => clearInterval(timer)
  }, [connected, filter, sort, reverse, fetchTorrents])

  // 排序切换
  const handleSort = (field) => {
    if (sort === field) {
      setReverse(r => !r)
    } else {
      setSort(field)
      setReverse(true)
    }
  }

  // 任务操作
  const handleAction = async (hash, action) => {
    setActionLoading(p => ({ ...p, [hash]: action }))
    try {
      if (action === 'pause') await torrentApi.pauseTask(hash, activeClientId)
      else if (action === 'resume') await torrentApi.resumeTask(hash, activeClientId)
      else if (action === 'delete') {
        await torrentApi.deleteTask(hash, false, activeClientId)
        setConfirmDelete(null)
      } else if (action === 'delete_files') {
        await torrentApi.deleteTask(hash, true, activeClientId)
        setConfirmDelete(null)
      }
      setTimeout(fetchTorrents, 500)
    } catch (e) {
      setError(e.message)
    } finally {
      setActionLoading(p => ({ ...p, [hash]: null }))
    }
  }

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
  if (connected === false && !loading) {
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

        {showConfig && <ConfigModal onClose={() => setShowConfig(false)} onSaved={() => { setShowConfig(false); loadClients(); setTimeout(checkConnection, 300) }} />}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-3">
            <Download className="text-green-400" size={24} />
            qBittorrent
            {version && <span className="text-xs text-gray-500 font-normal">{version}</span>}
          </h1>
          <p className="text-sm text-gray-500 mt-1">种子下载管理</p>
        </div>
        <div className="flex items-center gap-2">
          {/* 实例切换下拉 */}
          {clients.length > 1 && (
            <div className="relative">
              <select
                value={activeClientId}
                onChange={e => setActiveClientId(e.target.value)}
                className="appearance-none bg-surface-1 border border-surface-3 rounded-lg pl-3 pr-8 py-2
                           text-sm text-white focus:outline-none focus:border-brand-500 cursor-pointer"
              >
                {clients.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.id}{c.id === defaultClientId ? ' ★' : ''}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>
          )}

          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/20 text-green-400 animate-pulse">已连接</span>
          <button onClick={() => setShowConfig(true)} className="p-2 rounded-lg hover:bg-surface-2 transition" title="实例管理">
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

      {/* 筛选 + 排序 + 搜索 */}
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

        {/* 排序下拉 */}
        <div className="flex items-center gap-1 bg-surface-1 border border-surface-3 rounded-lg px-2 py-1">
          <ArrowUpDown size={12} className="text-gray-500" />
          <select value={sort} onChange={e => setSort(e.target.value)}
            className="bg-transparent text-xs text-gray-300 focus:outline-none cursor-pointer pr-1">
            {SORT_OPTIONS.map(o => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
          <button onClick={() => setReverse(r => !r)}
            className="p-0.5 rounded hover:bg-surface-2 text-gray-400 hover:text-white transition" title="切换排序方向">
            {reverse ? <ArrowDown size={12} /> : <ArrowUp size={12} />}
          </button>
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
      {loading && torrents.length === 0 ? (
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
          {/* 桌面端表头 (排序) */}
          <div className="hidden lg:grid grid-cols-[1fr_80px_70px_90px_80px_70px_100px] gap-2 px-4 py-2 border-b border-surface-3 bg-surface-2/30">
            <SortButton label="名称" field="name" current={sort} reverse={reverse} onSort={handleSort} />
            <SortButton label="大小" field="size" current={sort} reverse={reverse} onSort={handleSort} />
            <SortButton label="进度" field="progress" current={sort} reverse={reverse} onSort={handleSort} />
            <SortButton label="状态" field="state" current={sort} reverse={reverse} onSort={handleSort} />
            <SortButton label="速度" field="dlspeed" current={sort} reverse={reverse} onSort={handleSort} />
            <SortButton label="时间" field="added_on" current={sort} reverse={reverse} onSort={handleSort} />
            <div className="text-[10px] font-semibold text-gray-500 text-right">操作</div>
          </div>

          <div className="divide-y divide-surface-3">
            {filtered.map((t, i) => {
              const pct = t.progress * 100
              const isPaused = t.state?.startsWith('paused')
              const isDownloading = t.state === 'downloading' || t.state === 'stalledDL'
              const isCompleted = pct >= 100

              return (
                <div key={t.hash || i} className="group hover:bg-surface-2/50 transition">
                  {/* Desktop row */}
                  <div className="hidden lg:grid grid-cols-[1fr_80px_70px_90px_80px_70px_100px] gap-2 px-4 py-3 items-center">
                    <div className="min-w-0">
                      <h4 className="font-medium text-sm truncate" title={t.name}>{t.name || '(未知)'}</h4>
                      <div className="flex items-center gap-2 mt-0.5">
                        {t.category && <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-gray-400">{t.category}</span>}
                        {t.tags && <span className="text-[10px] text-gray-600">{t.tags}</span>}
                      </div>
                    </div>
                    <div className="text-xs text-gray-400">{formatBytes(t.size)}</div>
                    <div>
                      <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden mb-1">
                        <div className={`h-full rounded-full transition-all ${isCompleted ? 'bg-green-500' : 'bg-brand-500'}`}
                          style={{ width: `${pct.toFixed(1)}%` }} />
                      </div>
                      <span className="text-[10px] text-gray-400">{formatProgress(t.progress)}</span>
                    </div>
                    <StateBadge state={t.state} />
                    <div className="text-xs">
                      {isDownloading && t.dlspeed > 0 && <div className="text-blue-400">↓{formatSpeed(t.dlspeed)}</div>}
                      {t.upspeed > 0 && <div className="text-green-400">↑{formatSpeed(t.upspeed)}</div>}
                      {t.eta > 0 && t.eta < 8640000 && isDownloading && <div className="text-[10px] text-gray-500">{formatEta(t.eta)}</div>}
                    </div>
                    <div className="text-[11px] text-gray-500">{timeAgo(t.added_on)}</div>
                    {/* 操作 */}
                    <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      {isPaused ? (
                        <button onClick={() => handleAction(t.hash, 'resume')} disabled={!!actionLoading[t.hash]}
                          className="p-1.5 rounded hover:bg-green-500/15 text-gray-500 hover:text-green-400 transition" title="恢复">
                          {actionLoading[t.hash] === 'resume' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        </button>
                      ) : !isCompleted ? (
                        <button onClick={() => handleAction(t.hash, 'pause')} disabled={!!actionLoading[t.hash]}
                          className="p-1.5 rounded hover:bg-yellow-500/15 text-gray-500 hover:text-yellow-400 transition" title="暂停">
                          {actionLoading[t.hash] === 'pause' ? <Loader2 size={14} className="animate-spin" /> : <Pause size={14} />}
                        </button>
                      ) : null}
                      {confirmDelete === t.hash ? (
                        <div className="flex items-center gap-0.5">
                          <button onClick={() => handleAction(t.hash, 'delete')}
                            className="px-1.5 py-1 rounded text-[10px] bg-red-500/15 text-red-400 hover:bg-red-500/25">仅删任务</button>
                          <button onClick={() => handleAction(t.hash, 'delete_files')}
                            className="px-1.5 py-1 rounded text-[10px] bg-red-600/20 text-red-300 hover:bg-red-600/30">连文件删</button>
                          <button onClick={() => setConfirmDelete(null)}
                            className="px-1 py-1 rounded text-[10px] text-gray-500 hover:text-gray-300">×</button>
                        </div>
                      ) : (
                        <button onClick={() => setConfirmDelete(t.hash)}
                          className="p-1.5 rounded hover:bg-red-500/15 text-gray-500 hover:text-red-400 transition" title="删除">
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Mobile row */}
                  <div className="lg:hidden p-4">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-medium text-sm truncate flex-1" title={t.name}>{t.name || '(未知)'}</h4>
                      <StateBadge state={t.state} />
                    </div>
                    <div className="mt-2 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${isCompleted ? 'bg-green-500' : 'bg-brand-500'}`}
                        style={{ width: `${pct.toFixed(1)}%` }} />
                    </div>
                    <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
                      <span>{formatBytes(t.size)}</span>
                      <span>{formatProgress(t.progress)}</span>
                      {isDownloading && t.dlspeed > 0 && <span className="text-blue-400">↓{formatSpeed(t.dlspeed)}</span>}
                      <span className="ml-auto">{timeAgo(t.added_on)}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      {isPaused ? (
                        <button onClick={() => handleAction(t.hash, 'resume')}
                          className="px-3 py-1 rounded text-xs bg-green-500/15 text-green-400">恢复</button>
                      ) : !isCompleted ? (
                        <button onClick={() => handleAction(t.hash, 'pause')}
                          className="px-3 py-1 rounded text-xs bg-yellow-500/15 text-yellow-400">暂停</button>
                      ) : null}
                      <button onClick={() => confirmDelete === t.hash ? handleAction(t.hash, 'delete') : setConfirmDelete(t.hash)}
                        className="px-3 py-1 rounded text-xs bg-red-500/15 text-red-400">
                        {confirmDelete === t.hash ? '确认删除' : '删除'}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 底部统计 */}
          <div className="px-4 py-2 border-t border-surface-3 bg-surface-2/30 flex items-center gap-4 text-[11px] text-gray-500">
            <span>共 {filtered.length} 个{search ? ' (筛选)' : ''}</span>
            <span>↓ {formatSpeed(stats.dlSpeed)}</span>
            <span>↑ {formatSpeed(stats.upSpeed)}</span>
          </div>
        </div>
      )}

      {/* Modals */}
      {showAdd && <AddModal clientId={activeClientId} onClose={() => setShowAdd(false)} onAdded={() => { setShowAdd(false); fetchTorrents() }} />}
      {showConfig && <ConfigModal onClose={() => setShowConfig(false)} onSaved={() => { loadClients(); setTimeout(checkConnection, 300) }} />}
    </div>
  )
}
