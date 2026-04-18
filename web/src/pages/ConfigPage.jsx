import { useState, useEffect, useCallback } from 'react'
import {
  User, Crown, HardDrive, Gift, CheckCircle2, XCircle,
  Shield, Loader2, Sparkles, Calendar, TrendingUp,
  Settings, Cookie, Server, Film, Save, Trash2, Plus,
  Eye, EyeOff, RefreshCw, AlertCircle, FileText, MessageSquare, Bot,
  Download, Upload,
} from 'lucide-react'
import { accountApi, configApi } from '../api/client'
import { PageSpinner, ErrorBanner, PageHeader } from '../components/UI'

/* ════════════════════════════════════════════════
   圆环进度条
   ════════════════════════════════════════════════ */
function RingProgress({ pct, size = 120, stroke = 10, color = '#3b82f6' }) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" className="transition-all duration-700" />
      </svg>
      <div className="absolute text-center">
        <div className="text-xl font-bold text-white">{pct}%</div>
        <div className="text-[10px] text-gray-500">已使用</div>
      </div>
    </div>
  )
}

/** 信息卡片 */
function StatCard({ icon: Icon, iconColor, label, value, sub }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${iconColor}`}>
          <Icon size={20} />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-gray-500">{label}</div>
          <div className="text-lg font-semibold text-white truncate">{value}</div>
          {sub && <div className="text-[10px] text-gray-600">{sub}</div>}
        </div>
      </div>
    </div>
  )
}

/** Toast 提示 */
function Toast({ msg, type = 'success' }) {
  if (!msg) return null
  const color = type === 'success' ? 'text-green-400' : type === 'error' ? 'text-red-400' : 'text-amber-400'
  const Icon = type === 'success' ? CheckCircle2 : type === 'error' ? XCircle : AlertCircle
  return (
    <div className={`flex items-center gap-2 text-sm ${color} mt-2`}>
      <Icon size={14} /> {msg}
    </div>
  )
}

/* ════════════════════════════════════════════════
   Section: 账号信息 + 签到
   ════════════════════════════════════════════════ */
function AccountSection() {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [signing, setSigning] = useState(false)
  const [signResult, setSignResult] = useState(null)

  useEffect(() => {
    accountApi.info()
      .then(d => { setInfo(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const handleSign = async () => {
    setSigning(true)
    setSignResult(null)
    try {
      const result = await accountApi.sign()
      setSignResult(result)
      if (result.success) {
        setInfo(prev => prev ? { ...prev, signed_today: true, sign_progress: result.progress } : prev)
      }
    } catch (e) {
      setSignResult({ success: false, error: e.message })
    } finally {
      setSigning(false)
    }
  }

  if (loading) return <div className="card p-6 animate-pulse"><div className="h-20 bg-surface-3 rounded-lg" /></div>
  if (error) return <ErrorBanner message={error} />
  if (!info) return null

  const ringColor = info.used_pct > 90 ? '#ef4444' : info.used_pct > 70 ? '#f59e0b' : '#3b82f6'

  return (
    <>
      {/* Profile card */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-5">
          <div className="relative flex-shrink-0">
            {info.avatar ? (
              <img src={info.avatar} alt="" className="w-20 h-20 rounded-full object-cover ring-2 ring-surface-3" />
            ) : (
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-brand-500 to-purple-600
                              flex items-center justify-center ring-2 ring-surface-3">
                <User size={36} className="text-white" />
              </div>
            )}
            {info.super_vip && (
              <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-amber-500 rounded-full
                              flex items-center justify-center ring-2 ring-surface-1">
                <Crown size={14} className="text-white" />
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-2xl font-bold text-white">{info.nickname || '未知用户'}</h2>
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              {info.vip_type && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium
                                 bg-amber-500/15 text-amber-400 border border-amber-500/20">
                  <Crown size={12} /> {info.vip_type}
                </span>
              )}
              {info.phone && <span className="text-sm text-gray-500">{info.phone}</span>}
            </div>
            <div className="flex items-center gap-1.5 mt-2 text-xs text-green-400">
              <Shield size={12} /> Cookie 有效
            </div>
          </div>
          <div className="hidden sm:block flex-shrink-0">
            <RingProgress pct={info.used_pct || 0} color={ringColor} />
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon={HardDrive} iconColor="bg-blue-500/15 text-blue-400" label="总空间" value={info.total_fmt || '—'} />
        <StatCard icon={TrendingUp} iconColor="bg-purple-500/15 text-purple-400" label="已使用" value={info.used_fmt || '—'} sub={`${info.used_pct || 0}%`} />
        <StatCard icon={Gift} iconColor="bg-green-500/15 text-green-400" label="签到奖励" value={info.sign_reward_fmt || '—'} />
        <StatCard icon={Sparkles} iconColor="bg-amber-500/15 text-amber-400" label="活动奖励" value={info.other_reward_fmt || '—'} />
      </div>

      {/* Sign-in card */}
      <div className="card p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Calendar size={20} className="text-brand-400" /> 每日签到
          </h3>
          {info.sign_progress > 0 && info.sign_target > 0 && (
            <span className="text-xs text-gray-500">连签 {info.sign_progress}/{info.sign_target} 天</span>
          )}
        </div>
        {info.sign_target > 0 && (
          <div className="flex items-center gap-1.5 mb-5 overflow-x-auto pb-1 -mx-1 px-1">
            {Array.from({ length: info.sign_target }, (_, i) => (
              <div key={i}
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium
                            flex-shrink-0 transition-colors
                  ${i < info.sign_progress
                    ? 'bg-brand-500 text-white'
                    : i === info.sign_progress
                      ? 'bg-surface-3 text-gray-400 ring-2 ring-brand-500/50'
                      : 'bg-surface-3 text-gray-600'
                  }`}>
                {i + 1}
              </div>
            ))}
          </div>
        )}
        <div className="flex items-center gap-4">
          {info.can_sign ? (
            <button onClick={handleSign} disabled={signing || info.signed_today}
              className={`px-3 sm:px-6 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 sm:gap-2
                ${info.signed_today
                  ? 'bg-surface-3 text-gray-500 cursor-default'
                  : 'bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-600/20'}`}>
              {signing ? <><Loader2 size={16} className="animate-spin" /> 签到中...</>
                : info.signed_today ? <><CheckCircle2 size={16} /> 今日已签到</>
                : <><Gift size={16} /> 立即签到</>}
            </button>
          ) : (
            <div className="text-sm text-gray-500">Cookie 缺少移动端参数，无法签到。请从夸克 APP 抓取完整 Cookie。</div>
          )}
          {signResult && (
            <div className={`flex items-center gap-2 text-sm ${signResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {signResult.success
                ? <><CheckCircle2 size={16} /> {signResult.already_signed ? '今日已签到' : '签到成功'}{signResult.reward_fmt && ` +${signResult.reward_fmt}`}</>
                : <><XCircle size={16} /> {signResult.error || '签到失败'}</>}
            </div>
          )}
        </div>
        {info.signed_today && info.sign_daily_reward > 0 && (
          <div className="mt-3 text-xs text-gray-600">今日已获得 {info.sign_daily_reward_fmt}</div>
        )}
      </div>
    </>
  )
}

/* ════════════════════════════════════════════════
   Section: Cookie 管理
   ════════════════════════════════════════════════ */
function CookieSection({ config, onRefresh }) {
  const [newCookie, setNewCookie] = useState('')
  const [editIndex, setEditIndex] = useState(0)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const handleSave = async () => {
    if (!newCookie.trim()) return
    setSaving(true)
    setToast(null)
    try {
      const res = await configApi.setCookie(newCookie.trim(), editIndex)
      if (res.warning) {
        setToast({ msg: res.warning, type: 'warn' })
      } else {
        setToast({ msg: `Cookie 已保存${res.nickname ? ` — ${res.nickname}` : ''}`, type: 'success' })
      }
      setNewCookie('')
      onRefresh()
    } catch (e) {
      setToast({ msg: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async (idx) => {
    try {
      await configApi.removeCookie(idx)
      setToast({ msg: `已移除账号 #${idx + 1}`, type: 'success' })
      onRefresh()
    } catch (e) {
      setToast({ msg: e.message, type: 'error' })
    }
  }

  return (
    <div className="card p-6 mb-6">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
        <Cookie size={20} className="text-amber-400" /> Cookie 管理
      </h3>

      {/* Existing cookies */}
      {config.cookies && config.cookies.length > 0 && (
        <div className="space-y-2 mb-4">
          {config.cookies.map((c, i) => (
            <div key={i} className="flex items-center gap-3 p-3 bg-surface-2 rounded-lg">
              <div className="w-8 h-8 rounded-full bg-brand-600/20 flex items-center justify-center text-xs font-bold text-brand-400">
                #{i + 1}
              </div>
              <code className="flex-1 text-xs text-gray-400 truncate font-mono">{c || '（空）'}</code>
              <button onClick={() => handleRemove(i)}
                className="p-1.5 rounded-lg hover:bg-red-500/15 text-gray-500 hover:text-red-400 transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add / replace cookie */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <textarea
            value={newCookie}
            onChange={e => setNewCookie(e.target.value)}
            placeholder="粘贴 Cookie 字符串..."
            rows={3}
            className="w-full bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white
                       placeholder-gray-600 focus:outline-none focus:border-brand-500 resize-none font-mono"
          />
          <div className="flex items-center gap-2 mt-2">
            <label className="text-xs text-gray-500">账号序号:</label>
            <select value={editIndex} onChange={e => setEditIndex(Number(e.target.value))}
              className="bg-surface-2 border border-surface-3 rounded px-2 py-1 text-xs text-white">
              {Array.from({ length: Math.max((config.cookies?.length || 0) + 1, 3) }, (_, i) => (
                <option key={i} value={i}>#{i + 1}{i < (config.cookies?.length || 0) ? ' (替换)' : ' (新增)'}</option>
              ))}
            </select>
          </div>
        </div>
        <button onClick={handleSave} disabled={saving || !newCookie.trim()}
          className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-surface-3 disabled:text-gray-600
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 mt-1">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          保存
        </button>
      </div>
      <Toast msg={toast?.msg} type={toast?.type} />
    </div>
  )
}

/* ════════════════════════════════════════════════
   Section: fnOS 配置
   ════════════════════════════════════════════════ */
function FnosSection({ config, onRefresh }) {
  const fnos = config.fnos || {}
  const [form, setForm] = useState({
    host: fnos.host || '',
    port: fnos.port || 5666,
    ssl: fnos.ssl || false,
    api_key: fnos.api_key || '',
    timeout: fnos.timeout || 30,
    username: '',
    password: '',
  })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [showPwd, setShowPwd] = useState(false)

  useEffect(() => {
    setForm(f => ({
      ...f,
      host: fnos.host || '',
      port: fnos.port || 5666,
      ssl: fnos.ssl || false,
      api_key: fnos.api_key || '',
      timeout: fnos.timeout || 30,
    }))
  }, [config])

  const handleSave = async () => {
    setSaving(true)
    setToast(null)
    try {
      const payload = { host: form.host, port: Number(form.port), ssl: form.ssl, timeout: Number(form.timeout) }
      if (form.api_key) payload.api_key = form.api_key
      if (form.username && form.password) {
        payload.username = form.username
        payload.password = form.password
      }
      const res = await configApi.setFnos(payload)
      const msg = res.login ? `配置已保存，登录成功 — ${res.login.username}` : '配置已保存'
      setToast({ msg, type: 'success' })
      setForm(f => ({ ...f, username: '', password: '' }))
      onRefresh()
    } catch (e) {
      setToast({ msg: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"

  return (
    <div className="card p-6 mb-6">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
        <Server size={20} className="text-blue-400" /> fnOS 配置
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">主机地址</label>
          <input value={form.host} onChange={e => setForm({ ...form, host: e.target.value })}
            placeholder="192.168.1.100 或 http://nas.local" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">端口</label>
          <input type="number" value={form.port} onChange={e => setForm({ ...form, port: e.target.value })}
            className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">超时 (秒)</label>
          <input type="number" value={form.timeout} onChange={e => setForm({ ...form, timeout: e.target.value })}
            className={inputCls} />
        </div>
        <div className="flex items-end gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.ssl} onChange={e => setForm({ ...form, ssl: e.target.checked })}
              className="w-4 h-4 rounded bg-surface-2 border-surface-3 text-brand-500 focus:ring-brand-500" />
            <span className="text-sm text-gray-400">使用 HTTPS</span>
          </label>
          {fnos.token && (
            <span className="inline-flex items-center gap-1 text-xs text-green-400">
              <CheckCircle2 size={12} /> Token 已配置
            </span>
          )}
        </div>
      </div>

      {/* Login section */}
      <div className="border-t border-surface-3 pt-4 mt-2 mb-4">
        <div className="text-xs text-gray-500 mb-3">登录获取 Token（可选，留空则仅保存连接配置）</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">用户名</label>
            <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
              placeholder="fnOS 用户名" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">密码</label>
            <div className="relative">
              <input type={showPwd ? 'text' : 'password'}
                value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="fnOS 密码" className={inputCls + ' pr-10'} />
              <button onClick={() => setShowPwd(!showPwd)} type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving || !form.host}
          className="px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-surface-3 disabled:text-gray-600
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {form.username && form.password ? '保存并登录' : '保存配置'}
        </button>
        <Toast msg={toast?.msg} type={toast?.type} />
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════
   Section: TMDB 配置
   ════════════════════════════════════════════════ */
function TmdbSection({ config, onRefresh }) {
  const tmdb = config.tmdb || {}
  const [form, setForm] = useState({
    api_key: '',
    language: tmdb.language || 'zh-CN',
    region: tmdb.region || 'CN',
  })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    setForm(f => ({ ...f, language: tmdb.language || 'zh-CN', region: tmdb.region || 'CN' }))
  }, [config])

  const handleSave = async () => {
    setSaving(true)
    setToast(null)
    try {
      const payload = { language: form.language, region: form.region }
      if (form.api_key.trim()) {
        payload.api_key = form.api_key.trim()
      }
      await configApi.setTmdb(payload)
      setToast({ msg: '配置已保存', type: 'success' })
      setForm(f => ({ ...f, api_key: '' }))
      onRefresh()
    } catch (e) {
      setToast({ msg: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"

  return (
    <div className="card p-6 mb-6">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
        <Film size={20} className="text-green-400" /> TMDB 配置
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div className="md:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">API Key</label>
          <div className="relative">
            <input type={showKey ? 'text' : 'password'}
              value={form.api_key}
              onChange={e => setForm({ ...form, api_key: e.target.value })}
              placeholder={tmdb.api_key ? `当前: ${tmdb.api_key}（留空保持不变）` : '输入 TMDB API Key'}
              className={inputCls + ' pr-10'} />
            <button onClick={() => setShowKey(!showKey)} type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <div className="text-[10px] text-gray-600 mt-1">
            获取方式: <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noreferrer"
              className="text-brand-400 hover:underline">themoviedb.org/settings/api</a>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">语言</label>
          <select value={form.language} onChange={e => setForm({ ...form, language: e.target.value })} className={inputCls}>
            <option value="zh-CN">简体中文 (zh-CN)</option>
            <option value="zh-TW">繁体中文 (zh-TW)</option>
            <option value="en-US">English (en-US)</option>
            <option value="ja-JP">日本語 (ja-JP)</option>
            <option value="ko-KR">한국어 (ko-KR)</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">地区</label>
          <select value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} className={inputCls}>
            <option value="CN">中国 (CN)</option>
            <option value="TW">台湾 (TW)</option>
            <option value="HK">香港 (HK)</option>
            <option value="US">美国 (US)</option>
            <option value="JP">日本 (JP)</option>
            <option value="KR">韩国 (KR)</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-surface-3 disabled:text-gray-600
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          保存配置
        </button>
        <Toast msg={toast?.msg} type={toast?.type} />
      </div>
    </div>
  )
}


/* ════════════════════════════════════════════════
   Section: 飞书机器人配置
   ════════════════════════════════════════════════ */
function FeishuBotSection({ onRefresh }) {
  const [botConfig, setBotConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    app_id: '', app_secret: '', base_path: '/媒体',
    notify_open_id: '', api_base: '',
  })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [showSecret, setShowSecret] = useState(false)

  useEffect(() => {
    configApi.readBot()
      .then(d => {
        setBotConfig(d)
        setForm(f => ({
          ...f,
          base_path: d.base_path || '/媒体',
          notify_open_id: d.notify_open_id || '',
          api_base: d.api_base || '',
        }))
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setToast(null)
    try {
      const payload = {
        base_path: form.base_path,
        notify_open_id: form.notify_open_id.trim(),
        api_base: form.api_base.trim(),
      }
      if (form.app_id.trim()) payload.app_id = form.app_id.trim()
      if (form.app_secret.trim()) payload.app_secret = form.app_secret.trim()
      await configApi.setBot(payload)
      setToast({ msg: '配置已保存', type: 'success' })
      setForm(f => ({ ...f, app_id: '', app_secret: '' }))
      // reload bot config
      configApi.readBot().then(d => {
        setBotConfig(d)
        setForm(f => ({
          ...f,
          notify_open_id: d.notify_open_id || '',
          api_base: d.api_base || '',
        }))
      })
      onRefresh()
    } catch (e) {
      setToast({ msg: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"

  return (
    <div className="card p-6 mb-6">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
        <Bot size={20} className="text-indigo-400" /> 飞书机器人
      </h3>

      {/* Status */}
      {!loading && botConfig && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-surface-2 rounded-lg">
          <div className={`w-2.5 h-2.5 rounded-full ${botConfig.configured ? 'bg-green-400' : 'bg-gray-600'}`} />
          <span className="text-sm text-gray-300">
            {botConfig.configured ? '已配置' : '未配置'}
          </span>
          {botConfig.configured && (
            <span className="text-xs text-gray-500 font-mono ml-auto">
              APP_ID: {botConfig.app_id}
            </span>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">App ID</label>
          <input value={form.app_id}
            onChange={e => setForm({ ...form, app_id: e.target.value })}
            placeholder={botConfig?.app_id ? `当前: ${botConfig.app_id}（留空保持不变）` : '飞书应用 App ID'}
            className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">App Secret</label>
          <div className="relative">
            <input type={showSecret ? 'text' : 'password'}
              value={form.app_secret}
              onChange={e => setForm({ ...form, app_secret: e.target.value })}
              placeholder={botConfig?.app_secret ? `当前: ${botConfig.app_secret}（留空保持不变）` : '飞书应用 App Secret'}
              className={inputCls + ' pr-10'} />
            <button onClick={() => setShowSecret(!showSecret)} type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
              {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">通知人 Open ID</label>
          <input value={form.notify_open_id}
            onChange={e => setForm({ ...form, notify_open_id: e.target.value })}
            placeholder="ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            className={inputCls} />
          <div className="text-[10px] text-gray-600 mt-1">
            定时任务完成后私聊通知的用户，可在任务级别覆盖
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">转存基准路径</label>
          <input value={form.base_path}
            onChange={e => setForm({ ...form, base_path: e.target.value })}
            placeholder="/媒体"
            className={inputCls} />
        </div>
        <div className="md:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">API Base URL（可选）</label>
          <input value={form.api_base}
            onChange={e => setForm({ ...form, api_base: e.target.value })}
            placeholder="默认 https://open.feishu.cn"
            className={inputCls} />
          <div className="text-[10px] text-gray-600 mt-1">
            飞书 API 基地址，国际版可改为 https://open.larksuite.com，留空使用默认值
          </div>
        </div>
      </div>

      <div className="text-[10px] text-gray-600 mb-4">
        创建飞书应用: <a href="https://open.feishu.cn/app" target="_blank" rel="noreferrer"
          className="text-brand-400 hover:underline">open.feishu.cn/app</a>
        {' → '}创建自建应用 → 获取凭证 → 开启机器人能力 → 事件订阅开启长连接模式
      </div>

      <div className="bg-surface-2 rounded-lg p-4 mb-4">
        <div className="text-xs text-gray-400 mb-2 flex items-center gap-1.5">
          <MessageSquare size={12} /> 启动方式
        </div>
        <code className="text-xs text-green-400 font-mono">quark-cli bot</code>
        <div className="text-[10px] text-gray-600 mt-1">
          或指定凭证: <code className="text-gray-500">quark-cli bot --app-id xxx --app-secret xxx</code>
        </div>
      </div>

      <div className="bg-surface-2 rounded-lg p-4 mb-4">
        <div className="text-xs text-gray-400 mb-2">💡 使用说明</div>
        <div className="text-xs text-gray-500 space-y-1">
          <div>• 向机器人发送影视名称即可自动转存，如：<span className="text-gray-300">流浪地球2</span></div>
          <div>• 搜索剧集：<span className="text-gray-300">tv:三体</span></div>
          <div>• 指定年份：<span className="text-gray-300">沙丘 2024</span></div>
          <div>• 仅预览不转存：<span className="text-gray-300">dry:流浪地球2</span></div>
          <div>• 查看帮助：<span className="text-gray-300">help</span> / 查看状态：<span className="text-gray-300">status</span></div>
        </div>
      </div>

      <div className="bg-surface-2 rounded-lg p-4 mb-4">
        <div className="text-xs text-gray-400 mb-2">🔔 通知人 Open ID 获取方式</div>
        <div className="text-xs text-gray-500 space-y-1">
          <div>• 方式一：向机器人发送任意消息，在后台日志查看 <code className="text-gray-400">event.sender.sender_id.open_id</code></div>
          <div>• 方式二：飞书管理后台 → 通讯录 → 成员详情 → Open ID</div>
          <div>• 格式：<code className="text-gray-400">ou_</code> 开头的字符串</div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-surface-3 disabled:text-gray-600
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          保存配置
        </button>
        <Toast msg={toast?.msg} type={toast?.type} />
      </div>
    </div>
  )
}


/* ════════════════════════════════════════════════
   Section: 配置导出 / 导入
   ════════════════════════════════════════════════ */
function ExportImportSection({ onRefresh }) {
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [toast, setToast] = useState(null)

  const handleExport = async () => {
    setExporting(true)
    setToast(null)
    try {
      const data = await configApi.export()
      const json = JSON.stringify(data, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ts = new Date().toISOString().slice(0, 10)
      a.download = `quark-cli-config-${ts}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setToast({ msg: '配置已导出', type: 'success' })
    } catch (e) {
      setToast({ msg: '导出失败: ' + e.message, type: 'error' })
    } finally {
      setExporting(false)
    }
  }

  const handleImport = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json,application/json'
    input.onchange = async (e) => {
      const file = e.target.files?.[0]
      if (!file) return
      setImporting(true)
      setToast(null)
      try {
        const text = await file.text()
        const data = JSON.parse(text)
        if (typeof data !== 'object' || Array.isArray(data)) {
          throw new Error('无效的配置文件格式')
        }
        const result = await configApi.import(data)
        const keys = result.keys_imported?.join(', ') || ''
        setToast({ msg: `导入成功${keys ? ` (${keys})` : ''}`, type: 'success' })
        onRefresh()
      } catch (e) {
        if (e instanceof SyntaxError) {
          setToast({ msg: '文件不是有效的 JSON 格式', type: 'error' })
        } else {
          setToast({ msg: '导入失败: ' + e.message, type: 'error' })
        }
      } finally {
        setImporting(false)
      }
    }
    input.click()
  }

  return (
    <div className="card p-6 mb-6">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
        <FileText size={20} className="text-gray-400" /> 配置管理
      </h3>
      <p className="text-xs text-gray-500 mb-4">
        导出完整配置 (含 Cookie / Token) 用于备份或迁移到其他设备。导入时自动合并，Cookie 采用追加模式不会覆盖现有。
      </p>
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={handleExport} disabled={exporting}
          className="px-5 py-2.5 bg-surface-2 hover:bg-surface-3 border border-surface-3
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          导出配置
        </button>
        <button onClick={handleImport} disabled={importing}
          className="px-5 py-2.5 bg-surface-2 hover:bg-surface-3 border border-surface-3
                     text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          {importing ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          导入配置
        </button>
      </div>
      <Toast msg={toast?.msg} type={toast?.type} />
      <div className="mt-4 p-3 bg-surface-2 rounded-lg text-xs text-gray-500 space-y-1">
        <div>⚠️ 导出文件包含明文敏感信息 (Cookie、API Key、Token)，请妥善保管。</div>
        <div>💡 也可以直接编辑配置文件: <code className="text-gray-400 font-mono">~/.quark-cli/config.json</code></div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════
   Main: ConfigPage
   ════════════════════════════════════════════════ */
export default function ConfigPage() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadConfig = useCallback(() => {
    configApi.read()
      .then(d => { setConfig(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  if (loading) return <PageSpinner />
  if (error) return <ErrorBanner message={error} />

  return (
    <>
      <PageHeader title="配置" />

      {/* 配置文件路径 */}
      {config?.config_path && (
        <div className="flex items-center gap-2 text-xs text-gray-600 mb-6 -mt-2">
          <FileText size={12} />
          <code className="font-mono">{config.config_path}</code>
        </div>
      )}

      {/* 账号信息 + 签到 */}
      <AccountSection />

      {/* Cookie 管理 */}
      <CookieSection config={config} onRefresh={loadConfig} />

      {/* fnOS 配置 */}
      <FnosSection config={config} onRefresh={loadConfig} />

      {/* TMDB 配置 */}
      <TmdbSection config={config} onRefresh={loadConfig} />

      {/* 飞书机器人 */}
      <FeishuBotSection onRefresh={loadConfig} />

      {/* 配置导出 / 导入 */}
      <ExportImportSection onRefresh={loadConfig} />
    </>
  )
}
