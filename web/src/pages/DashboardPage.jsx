import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  RefreshCw, User, HardDrive, Cloud, CalendarClock, FolderSync, Tv,
  CheckCircle, AlertCircle, XCircle, Clock, TrendingUp, Database,
  ChevronRight, Loader2, AlertTriangle,
} from 'lucide-react'

const API = '/api'

/* ─── 工具 ─── */
function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024, units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + units[i]
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
  subscribe: '订阅追剧',
}

/* ─── 卡片组件 ─── */
function StatCard({ icon: Icon, iconColor, label, value, sub, to }) {
  const Wrap = to ? Link : 'div'
  const props = to ? { to } : {}
  return (
    <Wrap {...props}
      className={`bg-surface-1 rounded-xl p-3 sm:p-4 border border-surface-3 flex items-start gap-2 sm:gap-3
        ${to ? 'hover:border-brand-500/40 transition cursor-pointer' : ''}`}>
      <div className={`p-1.5 sm:p-2 rounded-lg bg-surface-2 shrink-0 ${iconColor || 'text-brand-400'}`}>
        <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-gray-500">{label}</div>
        <div className="text-lg font-bold mt-0.5 truncate">{value}</div>
        {sub && <div className="text-[11px] text-gray-600 mt-0.5 truncate">{sub}</div>}
      </div>
    </Wrap>
  )
}

function ProgressRing({ percent, size = 48, stroke = 4, color = '#6366f1' }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - Math.min(percent, 100) / 100)
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="currentColor" strokeWidth={stroke} className="text-surface-3" />
      <circle cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="transition-all duration-500" />
      <text x="50%" y="50%" textAnchor="middle" dy="0.35em"
        className="text-[10px] font-bold fill-gray-300">{Math.round(percent)}%</text>
    </svg>
  )
}


/* ─── 主页面 ─── */
export default function DashboardPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API}/dashboard`)
      setData(await res.json())
    } catch (e) {
      console.error('Dashboard fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  // 每 30 秒自动刷新
  useEffect(() => {
    const timer = setInterval(fetchDashboard, 30000)
    return () => clearInterval(timer)
  }, [fetchDashboard])

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
  }

  const acct = data?.account || {}
  const sched = data?.scheduler || {}
  const sync = data?.sync || {}
  const hist = data?.history || {}
  const disks = data?.disks || {}
  const subs = data?.subscriptions || {}

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">系统概览</p>
        </div>
        <button onClick={fetchDashboard}
          className="p-2 rounded-lg bg-surface-2 hover:bg-surface-3 transition" title="刷新">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-5 gap-3 sm:gap-4">
        <StatCard icon={User} label="账号"
          value={acct.nickname || (acct.error ? '未连接' : '—')}
          sub={acct.vip_type || ''}
          iconColor={acct.vip_status ? 'text-yellow-400' : 'text-gray-400'}
          to="/config" />

        <StatCard icon={Cloud} label="网盘空间"
          value={acct.space_used_human || '—'}
          sub={acct.space_total_human ? `/ ${acct.space_total_human}` : ''}
          iconColor="text-blue-400" to="/drive" />

        <StatCard icon={CalendarClock} label="定时任务"
          value={sched.running ? `${sched.enabled_count} 个运行中` : '未启动'}
          sub={sched.task_count ? `共 ${sched.task_count} 个任务` : ''}
          iconColor={sched.running ? 'text-green-400' : 'text-gray-500'}
          to="/scheduler" />

        <StatCard icon={FolderSync} label="文件同步"
          value={sync.active_tasks > 0 ? `${sync.active_tasks} 同步中` : `${sync.configured_tasks} 个任务`}
          sub={sync.schedule_enabled ? '定时同步已启用' : ''}
          iconColor={sync.active_tasks > 0 ? 'text-brand-400' : 'text-gray-400'}
          to="/sync" />

        <StatCard icon={Tv} label="订阅追剧"
          value={subs.active > 0 ? `${subs.active} 部追更中` : `${subs.total || 0} 部`}
          sub={subs.finished ? `${subs.finished} 部已完结` : ''}
          iconColor={subs.active > 0 ? 'text-purple-400' : 'text-gray-400'}
          to="/subscriptions" />
      </div>

      {/* 网盘空间 + 磁盘使用 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 网盘空间 */}
        {acct.space_percent != null && (
          <div className="bg-surface-1 rounded-xl p-5 border border-surface-3">
            <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
              <Cloud className="w-4 h-4" /> 网盘空间
            </h2>
            <div className="flex items-center gap-4">
              <ProgressRing percent={acct.space_percent} color={
                acct.space_percent > 90 ? '#ef4444' : acct.space_percent > 70 ? '#f59e0b' : '#6366f1'
              } />
              <div>
                <div className="text-sm font-medium">{acct.space_used_human} / {acct.space_total_human}</div>
                <div className="text-xs text-gray-500 mt-1">
                  剩余 {formatSize((acct.space_total || 0) - (acct.space_used || 0))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 本地磁盘 */}
        {Object.keys(disks).length > 0 && (
          <div className="bg-surface-1 rounded-xl p-5 border border-surface-3">
            <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
              <HardDrive className="w-4 h-4" /> 本地磁盘
            </h2>
            <div className="space-y-3">
              {Object.entries(disks).map(([mount, d]) => (
                <div key={mount} className="flex items-center gap-3">
                  <ProgressRing percent={d.percent} size={40} stroke={3} color={
                    d.percent > 90 ? '#ef4444' : d.percent > 70 ? '#f59e0b' : '#22c55e'
                  } />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-mono text-gray-400 truncate">{mount}</div>
                    <div className="text-[11px] text-gray-600">{d.used_human} / {d.total_human}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 7天执行统计 */}
      <div className="bg-surface-1 rounded-xl p-5 border border-surface-3">
        <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" /> 最近 7 天
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4">
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{hist.total || 0}</div>
            <div className="text-xs text-gray-500 mt-1">总执行次数</div>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{hist.by_status?.success || 0}</div>
            <div className="text-xs text-gray-500 mt-1">成功</div>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-yellow-400">{hist.by_status?.partial || 0}</div>
            <div className="text-xs text-gray-500 mt-1">部分成功</div>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-400">{hist.by_status?.error || 0}</div>
            <div className="text-xs text-gray-500 mt-1">失败</div>
          </div>
        </div>

        {/* 按类型 */}
        {hist.by_type && Object.keys(hist.by_type).length > 0 && (
          <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-surface-3">
            {Object.entries(hist.by_type).map(([type, cnt]) => (
              <span key={type} className="px-3 py-1 bg-surface-2 rounded-full text-xs text-gray-400">
                {typeLabel[type] || type}: {cnt}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 最近执行记录 */}
      <div className="bg-surface-1 rounded-xl border border-surface-3">
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-3">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Clock className="w-4 h-4" /> 执行历史
          </h2>
          <Link to="/history" className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
            查看全部 <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="divide-y divide-surface-3">
          {(hist.recent || []).length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-gray-600">暂无执行记录</div>
          )}
          {(hist.recent || []).map((rec, i) => (
            <div key={rec.id || i} className="px-3 sm:px-5 py-2.5 sm:py-3 flex items-center gap-2 sm:gap-3 hover:bg-surface-2/50 transition">
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
              <div className="text-[11px] text-gray-600 shrink-0 text-right">
                <div>{timeAgo(rec.ts)}</div>
                {rec.duration > 0 && <div>{rec.duration.toFixed(1)}s</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
