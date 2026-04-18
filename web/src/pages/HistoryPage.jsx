import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw, CheckCircle, AlertTriangle, XCircle, Clock, Filter,
  Loader2, Trash2, ChevronDown,
} from 'lucide-react'

const API = '/api'

const statusIcon = {
  success: <CheckCircle className="w-3.5 h-3.5 text-green-400" />,
  partial: <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />,
  error: <XCircle className="w-3.5 h-3.5 text-red-400" />,
}

const typeLabel = {
  task: '定时任务',
  sync: '文件同步',
  sign: '签到',
  auto_save: '自动转存',
}

function timeAgo(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  const now = new Date()
  const sec = Math.floor((now - d) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return Math.floor(sec / 60) + ' 分钟前'
  if (sec < 86400) return Math.floor(sec / 3600) + ' 小时前'
  return Math.floor(sec / 86400) + ' 天前'
}


export default function HistoryPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [hasMore, setHasMore] = useState(true)

  const fetchRecords = useCallback(async (append = false) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterType) params.set('type', filterType)
      if (filterStatus) params.set('status', filterStatus)
      params.set('limit', '50')
      params.set('offset', append ? records.length.toString() : '0')

      const res = await fetch(`${API}/history?${params}`)
      const data = await res.json()
      if (append) {
        setRecords(prev => [...prev, ...data.records])
      } else {
        setRecords(data.records || [])
      }
      setHasMore(data.records?.length === 50)
    } catch (e) {
      console.error('History fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [filterType, filterStatus, records.length])

  useEffect(() => { fetchRecords() }, [filterType, filterStatus]) // eslint-disable-line

  const handleCleanup = async () => {
    if (!confirm('确认清理 90 天前的历史记录？')) return
    try {
      const res = await fetch(`${API}/history/cleanup?keep_days=90`, { method: 'DELETE' })
      const data = await res.json()
      alert(`已清理 ${data.deleted} 条记录`)
      fetchRecords()
    } catch (e) {
      alert('清理失败: ' + e.message)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">执行历史</h1>
          <p className="text-sm text-gray-500 mt-1">所有任务和同步的执行记录</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCleanup}
            className="p-2 rounded-lg bg-surface-2 hover:bg-red-900/30 transition" title="清理旧记录">
            <Trash2 className="w-4 h-4 text-gray-500" />
          </button>
          <button onClick={() => fetchRecords()}
            className="p-2 rounded-lg bg-surface-2 hover:bg-surface-3 transition" title="刷新">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 筛选器 */}
      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
        <Filter className="w-4 h-4 text-gray-500" />
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-1.5 text-sm outline-none">
          <option value="">全部类型</option>
          <option value="task">定时任务</option>
          <option value="sync">文件同步</option>
          <option value="sign">签到</option>
          <option value="auto_save">自动转存</option>
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-1.5 text-sm outline-none">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="partial">部分成功</option>
          <option value="error">失败</option>
        </select>
      </div>

      {/* 记录列表 */}
      <div className="bg-surface-1 rounded-xl border border-surface-3 divide-y divide-surface-3">
        {records.length === 0 && !loading && (
          <div className="px-5 py-12 text-center text-sm text-gray-600">暂无记录</div>
        )}
        {records.map((rec) => (
          <div key={rec.id}>
            <button
              onClick={() => setExpanded(expanded === rec.id ? null : rec.id)}
              className="w-full px-3 sm:px-5 py-2.5 sm:py-3 flex items-center gap-2 sm:gap-3 hover:bg-surface-2/50 transition text-left"
            >
              {statusIcon[rec.status] || statusIcon.success}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">{rec.name}</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-surface-2 text-gray-500">
                    {typeLabel[rec.type] || rec.type}
                  </span>
                </div>
                <div className="text-xs text-gray-600 mt-0.5 truncate">{rec.summary}</div>
              </div>
              <div className="text-[11px] text-gray-600 shrink-0 text-right min-w-[60px]">
                <div>{timeAgo(rec.ts)}</div>
                {rec.duration > 0 && <div>{rec.duration.toFixed(1)}s</div>}
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-gray-600 transition-transform shrink-0 ${
                expanded === rec.id ? 'rotate-180' : ''}`} />
            </button>
            {expanded === rec.id && (
              <div className="px-3 sm:px-5 pb-3">
                <div className="bg-surface-2 rounded-lg p-3 text-xs font-mono text-gray-400 max-h-60 overflow-auto">
                  <div className="text-gray-600 mb-1">时间: {rec.ts}</div>
                  <pre className="whitespace-pre-wrap break-all">
                    {JSON.stringify(rec.detail, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="px-5 py-4 flex justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
          </div>
        )}
      </div>

      {/* 加载更多 */}
      {hasMore && records.length > 0 && !loading && (
        <div className="flex justify-center">
          <button onClick={() => fetchRecords(true)}
            className="px-4 py-2 bg-surface-2 hover:bg-surface-3 rounded-lg text-sm transition">
            加载更多
          </button>
        </div>
      )}
    </div>
  )
}
