import { useState, useEffect, useCallback } from 'react'
import {
  Search, ExternalLink, Shield, ShieldCheck, ShieldX,
  Download, Folder, ChevronRight, Home, FolderPlus,
  File, FileVideo, Loader2, CheckCircle2, XCircle, Link,
  Film, AlertCircle, Sparkles, ArrowRight, Eye,
  FolderOpen, FileText, Zap, Tag,
} from 'lucide-react'
import { searchApi, shareApi, driveApi, mediaApi, discoveryApi } from '../api/client'
import { PageHeader, PageSpinner, EmptyState, ErrorBanner } from '../components/UI'

/* ════════════════════════════════════════════════
   目录选择器 (弹窗)
   ════════════════════════════════════════════════ */
function DirPicker({ onSelect, onClose, initialPath = '/' }) {
  const [path, setPath] = useState(initialPath)
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

  useEffect(() => { fetchDir(initialPath) }, [fetchDir, initialPath])

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

/* ════════════════════════════════════════════════
   媒体库匹配提示
   ════════════════════════════════════════════════ */
function MediaLibHint({ keyword }) {
  const [matches, setMatches] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!keyword || keyword.length < 2) { setMatches(null); return }
    setLoading(true)
    mediaApi.search(keyword, 1, 5)
      .then(d => {
        setMatches(d.items?.length > 0 ? d.items : null)
        setLoading(false)
      })
      .catch(() => { setMatches(null); setLoading(false) })
  }, [keyword])

  if (loading || !matches) return null

  return (
    <div className="bg-amber-500/8 border border-amber-500/20 rounded-lg p-3 mb-4">
      <div className="flex items-center gap-2 text-xs font-medium text-amber-400 mb-2">
        <Film size={14} /> 媒体库中已有相似影片
      </div>
      <div className="flex flex-wrap gap-2">
        {matches.map(m => (
          <a key={m.guid} href={`/detail/${m.guid}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs
                       bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 transition-colors">
            <Film size={10} />
            {m.title}{m.year ? ` (${m.year})` : ''}
            {m.rating ? <span className="text-amber-500/70">★{m.rating}</span> : null}
          </a>
        ))}
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════
   TMDB 元数据智能提示 + 推荐路径
   ════════════════════════════════════════════════ */
function MetaHint({ keyword, onSelectPath }) {
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!keyword || keyword.length < 2) { setMeta(null); return }
    setLoading(true)
    discoveryApi.meta(keyword)
      .then(d => {
        if (d.meta) setMeta(d)
        else setMeta(null)
        setLoading(false)
      })
      .catch(() => { setMeta(null); setLoading(false) })
  }, [keyword])

  if (loading) return (
    <div className="flex items-center gap-2 text-xs text-gray-500 mb-4">
      <Loader2 size={12} className="animate-spin" /> 查询 TMDB 元数据...
    </div>
  )
  if (!meta) return null

  const m = meta.meta
  const paths = meta.save_paths || []

  return (
    <div className="bg-brand-500/5 border border-brand-500/15 rounded-lg p-4 mb-4">
      <div className="flex items-start gap-3">
        {/* Poster thumbnail */}
        {m.poster_url && (
          <img src={m.poster_url} alt="" className="w-12 h-18 rounded object-cover flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={14} className="text-brand-400 flex-shrink-0" />
            <span className="text-sm font-medium text-white">{m.title}</span>
            {m.year && <span className="text-xs text-gray-500">({m.year})</span>}
            {m.rating > 0 && (
              <span className="text-xs text-amber-400">★ {m.rating}</span>
            )}
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-gray-400">
              {meta.media_type === 'tv' ? '剧集' : '电影'}
            </span>
          </div>
          {m.genres?.length > 0 && (
            <div className="flex items-center gap-1 mb-2">
              <Tag size={10} className="text-gray-600" />
              <span className="text-[10px] text-gray-500">{m.genres.join(' / ')}</span>
            </div>
          )}

          {/* Recommended save paths */}
          {paths.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] text-gray-500 mb-1">推荐保存路径:</div>
              {paths.map((p, i) => (
                <button key={i} onClick={() => onSelectPath(p.path)}
                  className="flex items-center gap-2 w-full text-left px-2.5 py-1.5 rounded
                             bg-surface-2 hover:bg-surface-3 transition-colors group">
                  <FolderOpen size={13} className="text-brand-400 flex-shrink-0" />
                  <span className="text-xs text-gray-300 truncate flex-1">{p.path}</span>
                  <span className="text-[10px] text-gray-600">{p.description}</span>
                  <Zap size={10} className="text-brand-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════
   转存后预览
   ════════════════════════════════════════════════ */
function SavedPreview({ path }) {
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    driveApi.ls(path)
      .then(d => { setItems(d.items || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [path])

  if (loading) return (
    <div className="flex items-center gap-2 px-4 py-3 text-xs text-gray-500 border-t border-white/5">
      <Loader2 size={12} className="animate-spin" /> 加载目录预览...
    </div>
  )
  if (!items?.length) return null

  return (
    <div className="border-t border-white/5">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-gray-400 hover:text-gray-300 transition-colors">
        <Eye size={12} />
        <span>转存目录预览 · {items.length} 个文件</span>
        <ChevronRight size={12} className={`ml-auto transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded && (
        <div className="max-h-[200px] overflow-y-auto">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2.5 px-4 py-1.5 text-xs
                                     border-b border-white/[0.02] hover:bg-surface-2">
              {item.is_dir
                ? <Folder size={13} className="text-brand-400 flex-shrink-0" />
                : /\.(mp4|mkv|avi|rmvb|ts|flv|wmv)$/i.test(item.file_name)
                  ? <FileVideo size={13} className="text-purple-400 flex-shrink-0" />
                  : <File size={13} className="text-gray-500 flex-shrink-0" />
              }
              <span className="text-gray-300 truncate flex-1">{item.file_name}</span>
              <span className="text-[10px] text-gray-600 flex-shrink-0">{item.size_fmt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════
   分享预览面板 (增强版)
   ════════════════════════════════════════════════ */
function SharePreview({ url, keyword, suggestedPath, onSaved }) {
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

  const doSave = async (savePath) => {
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

  const handleQuickSave = () => {
    if (suggestedPath) {
      doSave(suggestedPath)
    } else {
      setShowPicker(true)
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
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Link size={16} className="text-brand-400 flex-shrink-0" />
          <span className="text-sm text-gray-300 truncate">{url}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-gray-500">{data?.total} 个文件 · {data?.total_size_fmt}</span>
          {/* 一键转存 */}
          {suggestedPath && (
            <button
              onClick={handleQuickSave}
              disabled={saving}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5
                         bg-green-600 hover:bg-green-500 text-white disabled:bg-surface-3 disabled:text-gray-600"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
              一键转存
            </button>
          )}
          {/* 手动选择目录 */}
          <button
            onClick={() => setShowPicker(true)}
            disabled={saving}
            className="btn-primary text-sm flex items-center gap-1.5"
          >
            {saving && !suggestedPath ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {saving && !suggestedPath ? '转存中...' : '选择目录'}
          </button>
        </div>
      </div>

      {/* Quick save target hint */}
      {suggestedPath && !saveResult && (
        <div className="px-4 py-2 bg-green-500/5 border-b border-white/5 flex items-center gap-2 text-xs text-green-400">
          <Zap size={12} />
          一键转存到: <code className="font-mono text-green-300">{suggestedPath}</code>
        </div>
      )}

      {/* File list */}
      <div className="max-h-[300px] overflow-y-auto">
        {data?.items?.map((item, i) => (
          <div key={i} className="flex items-center gap-2.5 px-4 py-2 text-sm
                                   border-b border-white/[0.03] hover:bg-surface-2">
            {item.is_dir
              ? <Folder size={16} className="text-brand-400 flex-shrink-0" />
              : /\.(mp4|mkv|avi|rmvb|ts|flv|wmv)$/i.test(item.file_name)
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

      {/* 转存后预览 */}
      {saveResult && !saveResult.error && saveResult.path && (
        <SavedPreview path={saveResult.path} />
      )}

      {/* Directory picker */}
      {showPicker && (
        <DirPicker
          onSelect={doSave}
          onClose={() => setShowPicker(false)}
          initialPath={suggestedPath ? suggestedPath.split('/').slice(0, -1).join('/') || '/' : '/'}
        />
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════
   主页面
   ════════════════════════════════════════════════ */
export default function ResourceSearchPage() {
  const [keyword, setKeyword] = useState('')
  const [searchedKeyword, setSearchedKeyword] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)

  // 直接粘贴分享链接模式
  const [directUrl, setDirectUrl] = useState('')
  const [checkResult, setCheckResult] = useState(null)
  const [checking, setChecking] = useState(false)

  // TMDB 推荐路径（全局，可被 MetaHint 和 SharePreview 使用）
  const [suggestedPath, setSuggestedPath] = useState(null)

  const handleSearch = (e) => {
    e.preventDefault()
    if (!keyword.trim()) return
    setLoading(true)
    setError(null)
    setPreviewUrl(null)
    setSuggestedPath(null)
    setSearchedKeyword(keyword.trim())
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

      {/* 智能提示区 (搜索后显示) */}
      {searchedKeyword && !loading && (
        <>
          <MediaLibHint keyword={searchedKeyword} />
          <MetaHint keyword={searchedKeyword} onSelectPath={setSuggestedPath} />
        </>
      )}

      {/* 已选择的推荐路径指示 */}
      {suggestedPath && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg bg-green-500/8 border border-green-500/20">
          <Zap size={14} className="text-green-400 flex-shrink-0" />
          <span className="text-xs text-green-400">一键转存路径:</span>
          <code className="text-xs text-green-300 font-mono truncate flex-1">{suggestedPath}</code>
          <button onClick={() => setSuggestedPath(null)}
            className="text-xs text-gray-500 hover:text-gray-300">清除</button>
        </div>
      )}

      {error && <ErrorBanner message={error} />}

      {/* Share preview */}
      {previewUrl && (
        <div className="mb-6">
          <SharePreview
            url={previewUrl}
            keyword={searchedKeyword}
            suggestedPath={suggestedPath}
            onSaved={() => {}}
          />
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
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {/* 一键转存按钮 (有推荐路径时显示) */}
                      {suggestedPath && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setPreviewUrl(item.url)
                          }}
                          className="px-2 py-1 rounded text-[10px] font-medium
                                     bg-green-600/20 text-green-400 hover:bg-green-600/30 transition-colors
                                     flex items-center gap-1"
                        >
                          <Zap size={10} /> 快速转存
                        </button>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); setPreviewUrl(item.url) }}
                        className="btn-ghost text-xs py-1 px-2 flex items-center gap-1 flex-shrink-0"
                      >
                        <Download size={12} /> 转存
                      </button>
                    </div>
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
