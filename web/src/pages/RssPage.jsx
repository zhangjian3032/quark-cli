import { useState, useEffect, useCallback } from 'react'
import { Rss, Plus, Play, Pause, RefreshCw, Trash2, ChevronDown, ChevronUp,
  X, Check, Loader2, Settings2, Zap, TestTube, Clock, Filter, Link,
  AlertCircle, CheckCircle, ArrowLeft, Eye, History } from 'lucide-react'

const API = '/api'

// ── 工具函数 ──

function timeAgo(ts) {
  if (!ts) return '从未'
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

function StatusBadge({ enabled, error }) {
  if (error) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/20 text-red-400">异常</span>
  if (!enabled) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-500/20 text-gray-400">已暂停</span>
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/20 text-green-400">运行中</span>
}

function SchedulerBadge({ running }) {
  if (running) return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/20 text-green-400 animate-pulse">调度运行中</span>
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-500/20 text-gray-400">调度已停止</span>
}

// ── 添加 / 编辑 Feed 弹窗 ──

function FeedModal({ feed, onClose, onSave }) {
  const isEdit = !!feed
  const [form, setForm] = useState({
    name: '', feed_url: '', interval_minutes: 30,
    max_items_per_check: 50, dedupe_window_hours: 168,
    bot_notify: true, enabled: true,
    auth_passkey: '', auth_cookie: '',
    ...(feed ? {
      ...feed,
      auth_passkey: feed.auth?.passkey || '',
      auth_cookie: feed.auth?.cookie || '',
    } : {}),
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        feed_url: form.feed_url.trim(),
        interval_minutes: Number(form.interval_minutes) || 30,
        max_items_per_check: Number(form.max_items_per_check) || 50,
        dedupe_window_hours: Number(form.dedupe_window_hours) || 168,
        bot_notify: form.bot_notify,
        enabled: form.enabled,
        auth: {},
      }
      if (form.auth_passkey.trim()) payload.auth.passkey = form.auth_passkey.trim()
      if (form.auth_cookie.trim()) payload.auth.cookie = form.auth_cookie.trim()

      const url = isEdit ? `${API}/rss/feeds/${feed.id}` : `${API}/rss/feeds`
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

  const F = (label, key, type = 'text', placeholder = '', className = '') => (
    <label className={`block ${className}`}>
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
          <h3 className="font-semibold">{isEdit ? '编辑 Feed' : '添加 RSS Feed'}</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        <div className="p-4 space-y-3">
          {F('名称', 'name', 'text', '如: 电影天堂4K RSS')}
          {F('Feed URL *', 'feed_url', 'url', 'https://example.com/rss.xml')}

          <div className="grid grid-cols-3 gap-3">
            {F('检查间隔(分钟)', 'interval_minutes', 'number')}
            {F('每次最大条数', 'max_items_per_check', 'number')}
            {F('去重窗口(小时)', 'dedupe_window_hours', 'number')}
          </div>

          <div className="border-t border-surface-3 pt-3 mt-3">
            <span className="text-xs text-gray-500 mb-2 block">认证 (可选)</span>
            {F('Passkey', 'auth_passkey', 'text', 'RSS 站点的 passkey')}
            {F('Cookie', 'auth_cookie', 'text', '浏览器 Cookie')}
          </div>

          <div className="flex items-center gap-4 pt-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox" checked={form.bot_notify}
                onChange={e => setForm(f => ({ ...f, bot_notify: e.target.checked }))}
                className="rounded border-surface-3"
              />
              <span className="text-sm text-gray-300">飞书通知</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox" checked={form.enabled}
                onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                className="rounded border-surface-3"
              />
              <span className="text-sm text-gray-300">立即启用</span>
            </label>
          </div>
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button
            onClick={handleSave} disabled={saving || !form.feed_url.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {isEdit ? '保存' : '添加'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 添加规则弹窗 ──

function RuleModal({ feedId, onClose, onSave }) {
  const [form, setForm] = useState({
    match: '', exclude: '', quality: '',
    min_size_gb: '', max_size_gb: '',
    link_type: 'any', action: 'auto_save', save_path: '',
    torrent_client: '', torrent_save_path: '', torrent_category: '', torrent_tags: '', torrent_paused: false,
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = { ...form }
      if (payload.min_size_gb) payload.min_size_gb = parseFloat(payload.min_size_gb)
      else delete payload.min_size_gb
      if (payload.max_size_gb) payload.max_size_gb = parseFloat(payload.max_size_gb)
      else delete payload.max_size_gb

      const resp = await fetch(`${API}/rss/feeds/${feedId}/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '添加失败')
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
          <h3 className="font-semibold">添加规则</h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        <div className="p-4 space-y-3">
          {F('匹配正则 *', 'match', 'text', '如: 4K|2160p|Remux')}
          {F('排除正则', 'exclude', 'text', '如: 抢版|CAM|TS')}
          {F('画质过滤', 'quality', 'text', '如: 4K|1080p')}

          <div className="grid grid-cols-2 gap-3">
            {F('最小体积 (GB)', 'min_size_gb', 'number', '0')}
            {F('最大体积 (GB)', 'max_size_gb', 'number', '100')}
          </div>

          <label className="block">
            <span className="text-xs text-gray-400 mb-1 block">链接类型</span>
            <select
              value={form.link_type}
              onChange={e => setForm(f => ({ ...f, link_type: e.target.value }))}
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
            >
              <option value="any">全部</option>
              <option value="quark">夸克网盘</option>
              <option value="alipan">阿里云盘</option>
              <option value="magnet">磁力链接</option>
              <option value="enclosure">Enclosure</option>
              <option value="torrent_enclosure">Torrent 附件</option>
              <option value="web">网页链接</option>
            </select>
          </label>

          <label className="block">
            <span className="text-xs text-gray-400 mb-1 block">动作</span>
            <select
              value={form.action}
              onChange={e => setForm(f => ({ ...f, action: e.target.value }))}
              className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
            >
              <option value="auto_save">自动转存</option>
              <option value="torrent">推送 qBittorrent</option>
              <option value="notify">仅通知</option>
              <option value="log">仅记录</option>
            </select>
          </label>

          {form.action === 'auto_save' && F('存储路径', 'save_path', 'text', '/RSS转存')}

          {form.action === 'torrent' && (
            <div className="border-t border-surface-3 pt-3 mt-1 space-y-3">
              <span className="text-xs text-gray-500 block">qBittorrent 参数</span>
              {F('qB 客户端 ID', 'torrent_client', 'text', '留空使用默认')}
              {F('下载保存路径', 'torrent_save_path', 'text', '/downloads/rss')}
              <div className="grid grid-cols-2 gap-3">
                {F('分类', 'torrent_category', 'text', 'rss')}
                {F('标签', 'torrent_tags', 'text', '逗号分隔')}
              </div>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.torrent_paused}
                  onChange={e => setForm(f => ({ ...f, torrent_paused: e.target.checked }))}
                  className="rounded border-surface-3" />
                <span className="text-sm text-gray-300">添加后暂停</span>
              </label>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-surface-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-surface-2">取消</button>
          <button
            onClick={handleSave} disabled={saving || !form.match.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            添加规则
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Test Feed 弹窗 ──

function TestItemCard({ item, index }) {
  const [expanded, setExpanded] = useState(false)

  // 从 description 中简单提取链接标签
  const linkBadges = []
  const desc = item.description || ''
  if (/pan\.quark\.cn/i.test(desc) || /pan\.quark\.cn/i.test(item.link || '')) linkBadges.push({ type: 'quark', color: 'text-blue-400 bg-blue-500/20' })
  if (/alipan\.com|aliyundrive/i.test(desc) || /alipan\.com|aliyundrive/i.test(item.link || '')) linkBadges.push({ type: 'alipan', color: 'text-green-400 bg-green-500/20' })
  if (/magnet:\?/i.test(desc)) linkBadges.push({ type: 'magnet', color: 'text-purple-400 bg-purple-500/20' })
  if (item.enclosures && item.enclosures.length > 0) linkBadges.push({ type: 'enclosure', color: 'text-orange-400 bg-orange-500/20' })

  // 清理 HTML 标签用于纯文本显示
  const plainDesc = desc.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

  return (
    <div className="bg-surface-2 border border-surface-3 rounded-lg overflow-hidden">
      <div
        className="p-3 cursor-pointer hover:bg-surface-3/50 transition select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-2">
          <span className="text-xs text-gray-600 font-mono mt-0.5 flex-shrink-0 w-5 text-right">{index + 1}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <div className="text-sm font-medium flex-1 min-w-0" style={{ wordBreak: 'break-word' }}>
                {item.title || '(无标题)'}
              </div>
              {expanded ? <ChevronUp size={14} className="text-gray-500 flex-shrink-0" /> : <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />}
            </div>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {item.pub_date && <span className="text-xs text-gray-500">{new Date(item.pub_date).toLocaleString()}</span>}
              {item.author && <span className="text-xs text-gray-500">· {item.author}</span>}
              {linkBadges.map((b, j) => (
                <span key={j} className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${b.color}`}>{b.type}</span>
              ))}
              {(item.categories || []).length > 0 && (
                <span className="text-xs text-gray-600">{item.categories.slice(0, 3).join(' / ')}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-surface-3 p-3 space-y-2 text-xs bg-surface-1/50">
          {/* 描述 */}
          {plainDesc && (
            <div>
              <div className="text-gray-500 mb-1 font-semibold">描述</div>
              <div className="text-gray-300 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto">{plainDesc.slice(0, 800)}{plainDesc.length > 800 ? '...' : ''}</div>
            </div>
          )}

          {/* 链接 */}
          {item.link && (
            <div>
              <div className="text-gray-500 mb-1 font-semibold">链接</div>
              <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline break-all">{item.link}</a>
            </div>
          )}

          {/* 分类 */}
          {(item.categories || []).length > 0 && (
            <div>
              <div className="text-gray-500 mb-1 font-semibold">分类</div>
              <div className="flex flex-wrap gap-1">
                {item.categories.map((cat, j) => (
                  <span key={j} className="px-1.5 py-0.5 rounded bg-surface-3 text-gray-400">{cat}</span>
                ))}
              </div>
            </div>
          )}

          {/* Enclosures */}
          {(item.enclosures || []).length > 0 && (
            <div>
              <div className="text-gray-500 mb-1 font-semibold">附件 ({item.enclosures.length})</div>
              <div className="space-y-1">
                {item.enclosures.map((enc, j) => (
                  <div key={j} className="flex items-center gap-2">
                    <Link size={10} className="text-gray-500 flex-shrink-0" />
                    <a href={enc.url || enc} target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline break-all truncate">
                      {enc.url || enc}
                    </a>
                    {enc.type && <span className="text-gray-600 flex-shrink-0">{enc.type}</span>}
                    {enc.length && <span className="text-gray-600 flex-shrink-0">{(Number(enc.length) / 1048576).toFixed(1)} MB</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* GUID */}
          {item.guid && (
            <div className="text-gray-600 pt-1 border-t border-surface-3">
              GUID: <span className="font-mono text-gray-500">{item.guid}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TestModal({ feed, onClose }) {
  const [url, setUrl] = useState(feed?.feed_url || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const doTest = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const endpoint = feed?.id ? `${API}/rss/feeds/${feed.id}/test` : `${API}/rss/test`
      const body = feed?.id ? {} : { feed_url: url.trim() }
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '测试失败')
      }
      setResult(await resp.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (feed?.id) doTest()
  }, []) // eslint-disable-line

  const totalItems = result?.item_count ?? 0
  const shownItems = result?.items?.length ?? 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2">
            <TestTube size={18} className="text-brand-400" />
            测试 Feed
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        {!feed?.id && (
          <div className="p-4 border-b border-surface-3 flex gap-2">
            <input
              value={url} onChange={e => setUrl(e.target.value)}
              placeholder="输入 Feed URL..."
              className="flex-1 px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm focus:outline-none focus:border-brand-500"
            />
            <button
              onClick={doTest} disabled={loading || !url.trim()}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              测试
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4">
          {loading && !result && (
            <div className="text-center py-8">
              <Loader2 size={24} className="animate-spin mx-auto text-brand-400 mb-2" />
              <p className="text-sm text-gray-500">正在拉取 Feed...</p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm p-3 bg-red-500/10 rounded-lg">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-3">
              {/* Feed 信息 + 条目统计 */}
              <div className="bg-surface-2 border border-surface-3 rounded-lg p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Feed: <span className="text-white font-medium">{result.feed_title || '未知'}</span></span>
                </div>
                {result.feed_description && (
                  <div className="text-xs text-gray-500 mt-1 line-clamp-2">{result.feed_description}</div>
                )}
                <div className="flex items-center gap-3 mt-2 text-xs">
                  <span className="px-2 py-0.5 rounded-full bg-brand-600/20 text-brand-400 font-semibold">
                    共 {totalItems} 条
                  </span>
                  {totalItems > shownItems && (
                    <span className="text-gray-500">预览前 {shownItems} 条</span>
                  )}
                </div>
              </div>

              {/* 条目列表 */}
              <div className="space-y-2">
                <div className="text-xs text-gray-500">点击条目展开详情</div>
                {(result.items || []).map((item, i) => (
                  <TestItemCard key={i} item={item} index={i} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── 历史记录弹窗 ──

function HistoryModal({ onClose }) {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API}/rss/history?limit=100`)
        const json = await resp.json()
        setRecords(json.records || [])
      } catch { /* ignore */ }
      finally { setLoading(false) }
    })()
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-surface-1 rounded-xl border border-surface-3 w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold flex items-center gap-2">
            <History size={18} className="text-brand-400" />
            RSS 处理历史
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-surface-2 rounded"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="text-center py-8">
              <Loader2 size={24} className="animate-spin mx-auto text-brand-400" />
            </div>
          ) : records.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">暂无记录</div>
          ) : (
            <div className="space-y-2">
              {records.map((r, i) => (
                <div key={i} className="bg-surface-2 border border-surface-3 rounded-lg p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium truncate flex-1">{r.name || r.keyword || '未知'}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      r.status === 'success' ? 'bg-green-500/20 text-green-400' :
                      r.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>{r.status || '未知'}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {r.created_at && <span>{new Date(r.created_at).toLocaleString()}</span>}
                    {r.action && <span className="ml-2">· {r.action}</span>}
                    {r.message && <span className="ml-2">· {r.message}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Feed 详情 (带规则) ──

function FeedDetail({ feed, onBack, onRefresh }) {
  const [showAddRule, setShowAddRule] = useState(false)
  const [checking, setChecking] = useState(false)
  const [testing, setTesting] = useState(false)
  const [editing, setEditing] = useState(false)

  const handleCheck = async (dryRun = false) => {
    setChecking(true)
    try {
      const resp = await fetch(`${API}/rss/feeds/${feed.id}/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: dryRun }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '检查失败')
      }
      const result = await resp.json()
      alert(`检查完成: ${result.new_items || 0} 新匹配, ${result.saved_items || 0} 已转存`)
      onRefresh()
    } catch (e) {
      alert(e.message)
    } finally {
      setChecking(false)
    }
  }

  const removeRule = async (index) => {
    if (!confirm('确认删除此规则?')) return
    try {
      const resp = await fetch(`${API}/rss/feeds/${feed.id}/rules/${index}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('删除失败')
      onRefresh()
    } catch (e) {
      alert(e.message)
    }
  }

  const rules = feed.rules || []
  const stats = feed.stats || {}

  return (
    <div className="space-y-4">
      {/* Back + Header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="p-2 rounded-lg hover:bg-surface-2 transition">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold truncate">{feed.name || feed.feed_url}</h2>
            <StatusBadge enabled={feed.enabled} error={feed.error} />
          </div>
          <div className="text-xs text-gray-500 truncate mt-0.5">{feed.feed_url}</div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
        >
          <Settings2 size={14} />
          编辑
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-brand-400">{stats.total_checked || 0}</div>
          <div className="text-xs text-gray-500">总检查</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-blue-400">{stats.total_matched || 0}</div>
          <div className="text-xs text-gray-500">总匹配</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-green-400">{stats.total_saved || 0}</div>
          <div className="text-xs text-gray-500">已转存</div>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-gray-400">{rules.length}</div>
          <div className="text-xs text-gray-500">规则数</div>
        </div>
      </div>

      {/* Info & Actions */}
      <div className="bg-surface-1 border border-surface-3 rounded-xl p-4">
        <div className="grid grid-cols-2 gap-3 text-sm mb-4">
          <div><span className="text-gray-500">检查间隔:</span> <span className="text-gray-300">{feed.interval_minutes} 分钟</span></div>
          <div><span className="text-gray-500">上次检查:</span> <span className="text-gray-300">{timeAgo(feed.last_check)}</span></div>
          <div><span className="text-gray-500">去重窗口:</span> <span className="text-gray-300">{feed.dedupe_window_hours || 168} 小时</span></div>
          <div><span className="text-gray-500">每次最多:</span> <span className="text-gray-300">{feed.max_items_per_check || 50} 条</span></div>
          {feed.auth?.passkey && <div><span className="text-gray-500">Passkey:</span> <span className="text-gray-300">已配置</span></div>}
          {feed.auth?.cookie && <div><span className="text-gray-500">Cookie:</span> <span className="text-gray-300">已配置</span></div>}
        </div>

        {feed.error && (
          <div className="flex items-center gap-2 text-red-400 text-xs p-2 bg-red-500/10 rounded-lg mb-3">
            <AlertCircle size={14} />
            {feed.error}
          </div>
        )}

        <div className="flex items-center gap-2 pt-3 border-t border-surface-3">
          <button
            onClick={() => handleCheck(false)}
            disabled={checking}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-brand-600/20 text-brand-400 hover:bg-brand-600/30 disabled:opacity-50"
          >
            {checking ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            立即检查
          </button>
          <button
            onClick={() => handleCheck(true)}
            disabled={checking}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
          >
            <Eye size={12} />
            试运行
          </button>
          <button
            onClick={() => setTesting(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
          >
            <TestTube size={12} />
            预览内容
          </button>
        </div>
      </div>

      {/* Rules */}
      <div className="bg-surface-1 border border-surface-3 rounded-xl">
        <div className="flex items-center justify-between p-4 border-b border-surface-3">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Filter size={16} className="text-brand-400" />
            匹配规则 ({rules.length})
          </h3>
          <button
            onClick={() => setShowAddRule(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-brand-600 hover:bg-brand-500"
          >
            <Plus size={12} />
            添加规则
          </button>
        </div>

        {rules.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <Filter size={32} className="mx-auto text-gray-600 mb-3" />
            <p>还没有匹配规则</p>
            <p className="text-xs mt-1">添加规则来过滤和处理 Feed 中的条目</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3">
            {rules.map((rule, i) => (
              <div key={i} className="p-4 hover:bg-surface-2/50 transition">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono px-1.5 py-0.5 bg-brand-600/20 text-brand-300 rounded">
                        #{i + 1}
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        rule.action === 'auto_save' ? 'bg-green-500/20 text-green-400' :
                        rule.action === 'torrent' ? 'bg-purple-500/20 text-purple-400' :
                        rule.action === 'notify' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {rule.action === 'auto_save' ? '自动转存' : rule.action === 'torrent' ? 'qBittorrent' : rule.action === 'notify' ? '通知' : '记录'}
                      </span>
                    </div>
                    <div className="space-y-0.5 text-xs">
                      <div><span className="text-gray-500">匹配:</span> <span className="text-green-400 font-mono">{rule.match || '.*'}</span></div>
                      {rule.exclude && <div><span className="text-gray-500">排除:</span> <span className="text-red-400 font-mono">{rule.exclude}</span></div>}
                      {rule.quality && <div><span className="text-gray-500">画质:</span> <span className="text-gray-300">{rule.quality}</span></div>}
                      {(rule.min_size_gb || rule.max_size_gb) && (
                        <div><span className="text-gray-500">体积:</span> <span className="text-gray-300">{rule.min_size_gb || 0}~{rule.max_size_gb || '∞'} GB</span></div>
                      )}
                      <div><span className="text-gray-500">链接:</span> <span className="text-gray-300">{rule.link_type || 'any'}</span></div>
                      {rule.save_path && <div><span className="text-gray-500">路径:</span> <span className="text-gray-300">{rule.save_path}</span></div>}
                      {rule.torrent_save_path && <div><span className="text-gray-500">qB 路径:</span> <span className="text-gray-300">{rule.torrent_save_path}</span></div>}
                      {rule.torrent_category && <div><span className="text-gray-500">qB 分类:</span> <span className="text-gray-300">{rule.torrent_category}</span></div>}
                      {rule.torrent_tags && <div><span className="text-gray-500">qB 标签:</span> <span className="text-gray-300">{rule.torrent_tags}</span></div>}
                      {rule.torrent_client && <div><span className="text-gray-500">qB 实例:</span> <span className="text-gray-300">{rule.torrent_client}</span></div>}
                    </div>
                  </div>
                  <button
                    onClick={() => removeRule(i)}
                    className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showAddRule && (
        <RuleModal feedId={feed.id} onClose={() => setShowAddRule(false)} onSave={() => { setShowAddRule(false); onRefresh() }} />
      )}
      {testing && (
        <TestModal feed={feed} onClose={() => setTesting(false)} />
      )}
      {editing && (
        <FeedModal feed={feed} onClose={() => setEditing(false)} onSave={() => { setEditing(false); onRefresh() }} />
      )}
    </div>
  )
}

// ── Feed 卡片 ──

function FeedCard({ feed, onRefresh, onSelect }) {
  const [loading, setLoading] = useState(false)
  const stats = feed.stats || {}
  const rules = feed.rules || []

  const action = async (url, method = 'POST', body = null) => {
    setLoading(true)
    try {
      const opts = { method, headers: { 'Content-Type': 'application/json' } }
      if (body !== null) opts.body = JSON.stringify(body)
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
    <div
      className="bg-surface-1 border border-surface-3 rounded-xl p-4 hover:border-surface-4 transition cursor-pointer"
      onClick={() => onSelect(feed)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-10 h-10 bg-orange-600/20 rounded-lg flex items-center justify-center flex-shrink-0">
            <Rss size={20} className="text-orange-400" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-semibold flex items-center gap-2">
              <span className="truncate">{feed.name || '未命名'}</span>
              <StatusBadge enabled={feed.enabled} error={feed.error} />
            </div>
            <div className="text-xs text-gray-500 mt-0.5 truncate">{feed.feed_url}</div>
          </div>
        </div>
      </div>

      {/* Mini Stats */}
      <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
        <span>{rules.length} 规则</span>
        <span>{stats.total_matched || 0} 匹配</span>
        <span>{stats.total_saved || 0} 转存</span>
      </div>

      {/* Info */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>上次检查: {timeAgo(feed.last_check)}</span>
        <span>每 {feed.interval_minutes}m</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-surface-3" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => action(`${API}/rss/feeds/${feed.id}/check`, 'POST', {})}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-brand-600/20 text-brand-400 hover:bg-brand-600/30 disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
          检查
        </button>

        <button
          onClick={() => action(`${API}/rss/feeds/${feed.id}/toggle`)}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg hover:bg-surface-2"
        >
          {feed.enabled ? <Pause size={12} /> : <Play size={12} />}
          {feed.enabled ? '暂停' : '启用'}
        </button>

        <div className="flex-1" />

        <button
          onClick={() => { if (confirm(`确认删除 Feed「${feed.name || feed.feed_url}」?`)) action(`${API}/rss/feeds/${feed.id}`, 'DELETE') }}
          disabled={loading}
          className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ── 主页面 ──

export default function RssPage() {
  const [feeds, setFeeds] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editFeed, setEditFeed] = useState(null)
  const [selectedFeed, setSelectedFeed] = useState(null)
  const [showTest, setShowTest] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [scheduler, setScheduler] = useState({ running: false })
  const [schedulerLoading, setSchedulerLoading] = useState(false)

  const fetchFeeds = useCallback(async () => {
    try {
      const [feedsResp, schedResp] = await Promise.all([
        fetch(`${API}/rss/feeds`),
        fetch(`${API}/rss/scheduler/status`),
      ])
      const feedsJson = await feedsResp.json()
      const schedJson = await schedResp.json()
      setFeeds(feedsJson.feeds || [])
      setScheduler(schedJson)

      // 如果当前有选中 feed，更新它
      setSelectedFeed(prev => {
        if (!prev) return null
        const updated = (feedsJson.feeds || []).find(f => f.id === prev.id)
        return updated || null
      })
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchFeeds()
    const timer = setInterval(fetchFeeds, 8000)
    return () => clearInterval(timer)
  }, [fetchFeeds])

  const toggleScheduler = async () => {
    setSchedulerLoading(true)
    try {
      const endpoint = scheduler.running
        ? `${API}/rss/scheduler/stop`
        : `${API}/rss/scheduler/start`
      await fetch(endpoint, { method: 'POST' })
      await fetchFeeds()
    } catch { /* ignore */ }
    finally { setSchedulerLoading(false) }
  }

  const enabledFeeds = feeds.filter(f => f.enabled)
  const disabledFeeds = feeds.filter(f => !f.enabled)

  // 详情视图
  if (selectedFeed) {
    return (
      <div className="space-y-6">
        <FeedDetail
          feed={selectedFeed}
          onBack={() => setSelectedFeed(null)}
          onRefresh={fetchFeeds}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-3">
            <Rss className="text-orange-400" size={24} />
            RSS 订阅
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            自动抓取 → 规则匹配 → 转存 / 通知
          </p>
        </div>

        <div className="flex items-center gap-3">
          <SchedulerBadge running={scheduler.running} />
          <button
            onClick={toggleScheduler}
            disabled={schedulerLoading}
            className={`p-2 rounded-lg transition ${scheduler.running ? 'hover:bg-red-500/10 text-red-400' : 'hover:bg-green-500/10 text-green-400'}`}
            title={scheduler.running ? '停止调度' : '启动调度'}
          >
            {schedulerLoading ? <Loader2 size={16} className="animate-spin" /> : scheduler.running ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button onClick={() => setShowHistory(true)} className="p-2 rounded-lg hover:bg-surface-2 transition" title="历史记录">
            <History size={16} />
          </button>
          <button onClick={() => setShowTest(true)} className="p-2 rounded-lg hover:bg-surface-2 transition" title="测试 Feed">
            <TestTube size={16} />
          </button>
          <button onClick={fetchFeeds} className="p-2 rounded-lg hover:bg-surface-2 transition">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition"
          >
            <Plus size={16} />
            添加 Feed
          </button>
        </div>
      </div>

      {/* Stats */}
      {feeds.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-orange-400">{feeds.length}</div>
            <div className="text-xs text-gray-500">Feed 总数</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{enabledFeeds.length}</div>
            <div className="text-xs text-gray-500">运行中</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-blue-400">
              {feeds.reduce((s, f) => s + (f.stats?.total_matched || 0), 0)}
            </div>
            <div className="text-xs text-gray-500">总匹配</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-brand-400">
              {feeds.reduce((s, f) => s + (f.stats?.total_saved || 0), 0)}
            </div>
            <div className="text-xs text-gray-500">总转存</div>
          </div>
        </div>
      )}

      {/* Empty */}
      {!loading && feeds.length === 0 && (
        <div className="bg-surface-1 border border-surface-3 rounded-xl p-12 text-center">
          <Rss size={48} className="mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold mb-2">还没有 RSS Feed</h3>
          <p className="text-sm text-gray-500 mb-6">
            添加 RSS 源，配置规则，系统会自动抓取新内容并转存到网盘
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => setShowTest(true)}
              className="px-6 py-2.5 border border-surface-3 hover:bg-surface-2 rounded-lg text-sm transition"
            >
              先测试一下
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-sm font-medium transition"
            >
              添加第一个 Feed
            </button>
          </div>
        </div>
      )}

      {/* Enabled Feeds */}
      {enabledFeeds.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">运行中 ({enabledFeeds.length})</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {enabledFeeds.map(f => <FeedCard key={f.id} feed={f} onRefresh={fetchFeeds} onSelect={setSelectedFeed} />)}
          </div>
        </div>
      )}

      {/* Disabled Feeds */}
      {disabledFeeds.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">已暂停 ({disabledFeeds.length})</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {disabledFeeds.map(f => <FeedCard key={f.id} feed={f} onRefresh={fetchFeeds} onSelect={setSelectedFeed} />)}
          </div>
        </div>
      )}

      {/* Modals */}
      {showAdd && <FeedModal onClose={() => setShowAdd(false)} onSave={() => { setShowAdd(false); fetchFeeds() }} />}
      {editFeed && <FeedModal feed={editFeed} onClose={() => setEditFeed(null)} onSave={() => { setEditFeed(null); fetchFeeds() }} />}
      {showTest && <TestModal feed={null} onClose={() => setShowTest(false)} />}
      {showHistory && <HistoryModal onClose={() => setShowHistory(false)} />}
    </div>
  )
}
