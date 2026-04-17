import { useState, useEffect, useCallback } from 'react'
import {
  Search, ExternalLink, Shield, ShieldCheck, ShieldX,
  Download, Folder, ChevronRight, Home, FolderPlus,
  File, FileVideo, Loader2, CheckCircle2, XCircle, Link,
} from 'lucide-react'
import { searchApi, shareApi, driveApi } from '../api/client'
import { PageHeader, PageSpinner, EmptyState, ErrorBanner } from '../components/UI'

/** 目录选择器 (弹窗) */
function DirPicker({ onSelect, onClose }) {
  const [path, setPath] = useState('/')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [newDir, setNewDir] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchDir = useCallback((p) => {
    setLoading(true)
    driveApi.ls(p)
      .then(d => {
        setItems(d.items?.filter(i => i.is_dir) || [])
        setPath(p)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => { fetchDir('/') }, [fetchDir])

  const goTo = (p) => fetchDir(p)

  const createDir = async () => {
    if (!newDir.trim()) return
    setCreating(true)
    try {
      const fullPath = path === '/' ? `/${newDir.trim()}` : `${path}/${newDir.trim()}`
      await driveApi.mkdir(fullPath)
      setNewDir('')
      fetchDir(path)
    } finally { setCreating(false) }
  }

  const parts = path.split('/').filter(Boolean)

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
         onClick={onClose}>
      <div className="card p-5 w-full max-w-lg mx-4 max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white mb-3">选择保存目录</h3>

        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-sm mb-3 overflow-x-auto flex-shrink-0">
          <button onClick={() => goTo('/')} className="text-gray-400 hover:text-white px-1">
            <Home size={14} />
          </button>
          {parts.map((p, i) => (
            <span key={i} className="flex items-center gap-1">
              <ChevronRight size={12} className="text-gray-600" />
              <button onClick={() => goTo('/' + parts.slice(0, i + 1).join('/'))}
                className="text-gray-400 hover:text-white px-1 truncate max-w-[120px]">
                {p}
              </button>
            </span>
          ))}
        </div>

        {/* Directory list */}
        <div className="flex-1 overflow-y-auto mb-3 min-h-[200px] max-h-[300px] border border-white/5 rounded-lg">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="animate-spin text-gray-500" />
            </div>
          ) : items.length > 0 ? (
            items.map(item => (
              <button key={item.fid}
                onClick={() => goTo(path === '/' ? `/${item.file_name}` : `${path}/${item.file_name}`)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-300
                           hover:bg-surface-2 transition-colors text-left border-b border-white/[0.03]">
                <Folder size={16} className="text-brand-400 flex-shrink-0" />
                <span className="truncate">{item.file_name}</span>
              </button>
            ))
          ) : (
            <div className="text-center py-8 text-gray-600 text-sm">空目录</div>
          )}
        </div>

        {/* New folder */}
        <div className="flex items-center gap-2 mb-4">
          <FolderPlus size={16} className="text-gray-500 flex-shrink-0" />
          <input
            type="text"
            value={newDir}
            onChange={e => setNewDir(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && createDir()}
            placeholder="新建文件夹..."
            className="input text-sm py-1.5 flex-1"
          />
          {newDir.trim() && (
            <button onClick={createDir} disabled={creating}
              className="btn-primary text-xs py-1.5">
              创建
            </button>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 truncate">当前: {path}</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-ghost text-sm">取消</button>
            <button onClick={() => onSelect(path)} className="btn-primary text-sm">
              保存到此目录
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** 分享预览面板 */
function SharePreview({ url, onSaved }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showPicker, setShowPicker] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSaveResult(null)
    shareApi.list(url)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [url])

  const handleSave = async (savePath) => {
    setShowPicker(false)
    setSaving(true)
    setSaveResult(null)
    try {
      const result = await shareApi.save(url, savePath)
      setSaveResult(result)
      if (onSaved) onSaved(result)
    } catch (e) {
      setSaveResult({ error: e.message })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="card p-6 flex items-center justify-center gap-2 text-gray-500">
      <Loader2 size={18} className="animate-spin" /> 加载分享内容...
    </div>
  )
  if (error) return <ErrorBanner message={error} />

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <Link size={16} className="text-brand-400 flex-shrink-0" />
          <span className="text-sm text-gray-300 truncate">{url}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-gray-500">{data?.total} 个文件 · {data?.total_size_fmt}</span>
          <button
            onClick={() => setShowPicker(true)}
            disabled={saving}
            className="btn-primary text-sm flex items-center gap-1.5"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {saving ? '转存中...' : '转存'}
          </button>
        </div>
      </div>

      {/* File list */}
      <div className="max-h-[300px] overflow-y-auto">
        {data?.items?.map((item, i) => (
          <div key={i} className="flex items-center gap-2.5 px-4 py-2 text-sm
                                   border-b border-white/[0.03] hover:bg-surface-2">
            {item.is_dir
              ? <Folder size={16} className="text-brand-400 flex-shrink-0" />
              : /\.(mp4|mkv|avi|rmvb|ts)$/i.test(item.file_name)
                ? <FileVideo size={16} className="text-purple-400 flex-shrink-0" />
                : <File size={16} className="text-gray-500 flex-shrink-0" />
            }
            <span className="text-gray-200 truncate flex-1" title={item.file_name}>
              {item.file_name}
            </span>
            <span className="text-xs text-gray-600 flex-shrink-0">{item.size_fmt}</span>
          </div>
        ))}
      </div>

      {/* Save result */}
      {saveResult && (
        <div className={`px-4 py-3 text-sm flex items-center gap-2
          ${saveResult.error ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
          {saveResult.error
            ? <><XCircle size={16} /> 转存失败: {saveResult.error}</>
            : <><CheckCircle2 size={16} /> 成功转存 {saveResult.saved} 个文件到 {saveResult.path}
                {saveResult.skipped > 0 && `（跳过 ${saveResult.skipped} 个已存在）`}</>
          }
        </div>
      )}

      {/* Directory picker */}
      {showPicker && <DirPicker onSelect={handleSave} onClose={() => setShowPicker(false)} />}
    </div>
  )
}

export default function ResourceSearchPage() {
  const [keyword, setKeyword] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)

  // 直接粘贴分享链接模式
  const [directUrl, setDirectUrl] = useState('')
  const [checkResult, setCheckResult] = useState(null)
  const [checking, setChecking] = useState(false)

  const handleSearch = (e) => {
    e.preventDefault()
    if (!keyword.trim()) return
    setLoading(true)
    setError(null)
    setPreviewUrl(null)
    searchApi.query(keyword.trim())
      .then(d => { setResults(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  const handleCheckUrl = async (e) => {
    e.preventDefault()
    if (!directUrl.trim()) return
    setChecking(true)
    setCheckResult(null)
    try {
      const result = await shareApi.check(directUrl.trim())
      setCheckResult(result)
      if (result.valid) {
        setPreviewUrl(directUrl.trim())
      }
    } catch (err) {
      setCheckResult({ valid: false, error: err.message })
    } finally {
      setChecking(false)
    }
  }

  return (
    <>
      <PageHeader title="资源搜索" description="搜索网盘资源或直接粘贴分享链接转存" />

      {/* Search form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Keyword search */}
        <form onSubmit={handleSearch} className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Search size={16} className="text-brand-400" />
            <span className="text-sm font-medium text-gray-300">关键词搜索</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              placeholder="输入影视名称搜索资源..."
              className="input flex-1 text-sm"
            />
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>
        </form>

        {/* Direct URL */}
        <form onSubmit={handleCheckUrl} className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Link size={16} className="text-green-400" />
            <span className="text-sm font-medium text-gray-300">直接粘贴链接</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={directUrl}
              onChange={e => setDirectUrl(e.target.value)}
              placeholder="粘贴 pan.quark.cn 分享链接..."
              className="input flex-1 text-sm"
            />
            <button type="submit" className="btn-primary" disabled={checking}>
              {checking ? '检查中...' : '检查'}
            </button>
          </div>
          {/* Check result badge */}
          {checkResult && (
            <div className={`flex items-center gap-1.5 mt-2 text-xs
              ${checkResult.valid ? 'text-green-400' : 'text-red-400'}`}>
              {checkResult.valid
                ? <><ShieldCheck size={14} /> 有效 · {checkResult.file_count} 个文件 · {checkResult.total_size_fmt}</>
                : <><ShieldX size={14} /> 无效{checkResult.error ? `: ${checkResult.error}` : ''}</>
              }
            </div>
          )}
        </form>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Share preview */}
      {previewUrl && (
        <div className="mb-6">
          <SharePreview url={previewUrl} onSaved={() => {}} />
        </div>
      )}

      {/* Search results */}
      {loading ? (
        <PageSpinner />
      ) : results ? (
        results.results?.length > 0 ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-500">
                找到 {results.total} 个结果
              </span>
            </div>
            <div className="space-y-2">
              {results.results.map((item, i) => (
                <div key={i}
                  className="card p-4 hover:bg-surface-2 transition-colors cursor-pointer"
                  onClick={() => setPreviewUrl(item.url)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <Shield size={18} className="text-gray-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm text-green-400 font-mono truncate">
                          {item.url}
                        </span>
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-600 hover:text-gray-400 flex-shrink-0"
                          onClick={e => e.stopPropagation()}
                        >
                          <ExternalLink size={14} />
                        </a>
                      </div>
                      {(item.note || item.title) && (
                        <p className="text-xs text-gray-500 truncate">
                          {item.note || item.title}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-gray-600">
                        {item.source && <span>来源: {item.source}</span>}
                        {item.password && (
                          <span className="text-amber-500">密码: {item.password}</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); setPreviewUrl(item.url) }}
                      className="btn-ghost text-xs py-1 px-2 flex items-center gap-1 flex-shrink-0"
                    >
                      <Download size={12} /> 转存
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <EmptyState icon={Search} title="未找到资源" description="试试其他关键词" />
        )
      ) : null}
    </>
  )
}
