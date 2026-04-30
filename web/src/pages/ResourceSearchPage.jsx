import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Search, ExternalLink, Shield, ShieldCheck, ShieldX,
  Download, Folder, ChevronRight, ChevronDown, Home, FolderPlus,
  File, FileVideo, Loader2, CheckCircle2, XCircle, Link,
  Film, AlertCircle, Sparkles, ArrowRight, Eye,
  FolderOpen, FileText, Zap, Tag, Check, Square, CheckSquare, Wand2, Replace, RotateCcw,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { searchApi, shareApi, driveApi, mediaApi, discoveryApi, renameApi } from '../api/client'
import { PageHeader, PageSpinner, EmptyState, ErrorBanner } from '../components/UI'
import SearchInputWithHistory from '../components/SearchInputWithHistory'
import { addSearchHistory } from '../utils/searchHistory'

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
      <div className="flex items-start gap-2 sm:gap-3">
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
   工具函数: 格式化字节
   ════════════════════════════════════════════════ */
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 2 : 0) + ' ' + units[i]
}

/* ════════════════════════════════════════════════
   转存后重命名结果预览
   ════════════════════════════════════════════════ */
function RenameResultPreview({ details }) {
  const [expanded, setExpanded] = useState(true)

  if (!details?.length) return null

  return (
    <div className="border-t border-white/5">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-purple-400 hover:text-purple-300 transition-colors">
        <Wand2 size={12} />
        <span>重命名结果 · {details.length} 个文件</span>
        <ChevronRight size={12} className={`ml-auto transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded && (
        <div className="max-h-[200px] overflow-y-auto">
          {details.map((d, i) => (
            <div key={i} className="flex items-center gap-2 px-4 py-1.5 text-xs
                                     border-b border-white/[0.02] hover:bg-surface-2">
              <span className="text-gray-500 truncate flex-1 line-through" title={d.original}>
                {d.original}
              </span>
              <ArrowRight size={10} className="text-purple-500/50 flex-shrink-0" />
              <span className="text-purple-300 truncate flex-1 font-medium" title={d.renamed}>
                {d.renamed}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════
   分享预览面板 (增强版 — 支持目录展开 + 选择性转存)
   ════════════════════════════════════════════════ */
function SharePreview({ url, keyword, suggestedPath, onSaved }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showPicker, setShowPicker] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState(null)

  // 目录展开状态: { [fid]: { loading, items, expanded } }
  const [dirState, setDirState] = useState({})
  // 选中文件: Set of "fid::token"
  const [selected, setSelected] = useState(new Set())
  // 全选模式 (默认全选)
  const [selectAll, setSelectAll] = useState(true)

  // ── 正则重命名 ──
  const [showRename, setShowRename] = useState(false)
  const [renamePattern, setRenamePattern] = useState('')
  const [renameReplace, setRenameReplace] = useState('')
  const [presets, setPresets] = useState(null)
  const [renamePreview, setRenamePreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSaveResult(null)
    setDirState({})
    setSelected(new Set())
    setSelectAll(true)
    setShowRename(false)
    setRenamePattern('')
    setRenameReplace('')
    setRenamePreview(null)
    shareApi.list(url)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [url])

  /* ── 目录展开/折叠 ── */
  const toggleDir = async (item) => {
    const fid = item.fid
    const cur = dirState[fid]

    // 已展开 → 折叠
    if (cur?.expanded) {
      setDirState(s => ({ ...s, [fid]: { ...s[fid], expanded: false } }))
      return
    }

    // 已加载 → 展开
    if (cur?.items) {
      setDirState(s => ({ ...s, [fid]: { ...s[fid], expanded: true } }))
      return
    }

    // 首次加载
    setDirState(s => ({ ...s, [fid]: { loading: true, items: null, expanded: true } }))
    try {
      const result = await shareApi.subdir(url, fid)
      setDirState(s => ({
        ...s,
        [fid]: { loading: false, items: result.items || [], expanded: true },
      }))
    } catch {
      setDirState(s => ({
        ...s,
        [fid]: { loading: false, items: [], expanded: true, error: true },
      }))
    }
  }

  /* ── 选择/取消选择 ── */
  const toggleSelect = (fid, token) => {
    const key = `${fid}::${token}`
    setSelectAll(false)
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSelectAll = () => {
    if (selectAll) {
      // 全选 → 取消全部
      setSelectAll(false)
      setSelected(new Set())
    } else {
      // 恢复全选
      setSelectAll(true)
      setSelected(new Set())
    }
  }

  /* ── 递归收集所有文件 (含子目录已展开的) ── */
  const getAllFiles = useCallback(() => {
    const files = []
    const collect = (items) => {
      for (const item of items) {
        if (item.is_dir) {
          const sub = dirState[item.fid]
          if (sub?.items) collect(sub.items)
        } else {
          files.push(item)
        }
      }
    }
    if (data?.items) collect(data.items)
    return files
  }, [data, dirState])

  /* ── 计算选中文件信息 ── */
  const selectionInfo = useMemo(() => {
    if (selectAll) {
      // 全选 = 用 data 原始统计 (包含未展开的子目录)
      const allFiles = getAllFiles()
      const knownSize = allFiles.reduce((s, f) => s + (f.size || 0), 0)
      // 如果有未展开的目录，大小可能不完整，用原始 total_size
      const totalSize = data?.total_size || knownSize
      return {
        count: data?.total || allFiles.length,
        size: totalSize,
        sizeFmt: formatBytes(totalSize),
        hasUnexpanded: (data?.items || []).some(i => i.is_dir && !dirState[i.fid]?.items),
      }
    }
    // 部分选择
    let count = 0, size = 0
    const allFiles = getAllFiles()
    for (const f of allFiles) {
      const key = `${f.fid}::${f.share_fid_token}`
      if (selected.has(key)) {
        count++
        size += f.size || 0
      }
    }
    return { count, size, sizeFmt: formatBytes(size), hasUnexpanded: false }
  }, [selectAll, selected, data, dirState, getAllFiles])

  /* ── 转存 ── */
  const doSave = async (savePath) => {
    setShowPicker(false)
    setSaving(true)
    setSaveResult(null)
    try {
      let fidList, fidTokenList

      if (!selectAll && selected.size > 0) {
        // 选择性转存
        fidList = []
        fidTokenList = []
        for (const key of selected) {
          const [fid, token] = key.split('::')
          fidList.push(fid)
          fidTokenList.push(token)
        }
      }

      const result = await shareApi.save(
            url, savePath, '', fidList, fidTokenList,
            renamePattern || undefined, renameReplace || undefined,
          )
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

  /* ── 渲染文件行 (递归) ── */
  const renderFileRow = (item, depth = 0) => {
    const isDir = item.is_dir
    const ds = dirState[item.fid]
    const isExpanded = ds?.expanded
    const isLoading = ds?.loading

    const isVideo = /\.(mp4|mkv|avi|rmvb|ts|flv|wmv)$/i.test(item.file_name)
    const key = `${item.fid}::${item.share_fid_token}`
    const isChecked = selectAll || selected.has(key)

    return (
      <div key={item.fid}>
        <div
          className="flex items-center gap-2 px-4 py-2 text-sm
                     border-b border-white/[0.03] hover:bg-surface-2 transition-colors"
          style={{ paddingLeft: `${16 + depth * 20}px` }}
        >
          {/* Checkbox (仅文件) */}
          {!isDir ? (
            <button
              onClick={() => toggleSelect(item.fid, item.share_fid_token)}
              className="flex-shrink-0 text-gray-500 hover:text-brand-400 transition-colors"
            >
              {isChecked
                ? <CheckSquare size={15} className="text-brand-400" />
                : <Square size={15} />
              }
            </button>
          ) : (
            <span className="w-[15px] flex-shrink-0" />
          )}

          {/* Icon + expand button for dirs */}
          {isDir ? (
            <button
              onClick={() => toggleDir(item)}
              className="flex items-center gap-1 flex-shrink-0 text-brand-400 hover:text-brand-300 transition-colors"
            >
              {isLoading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : isExpanded ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
              {isExpanded ? <FolderOpen size={16} /> : <Folder size={16} />}
            </button>
          ) : (
            isVideo
              ? <FileVideo size={16} className="text-purple-400 flex-shrink-0" />
              : <File size={16} className="text-gray-500 flex-shrink-0" />
          )}

          {/* File name */}
          <span
            className={`truncate flex-1 ${isDir ? 'text-brand-300 cursor-pointer hover:text-brand-200' : 'text-gray-200'}`}
            title={item.file_name}
            onClick={isDir ? () => toggleDir(item) : undefined}
          >
            {item.file_name}
          </span>

          {/* Size */}
          <span className="text-xs text-gray-600 flex-shrink-0">
            {isDir ? (ds?.items ? `${ds.items.length} 项` : '') : item.size_fmt}
          </span>
        </div>

        {/* Expanded children */}
        {isDir && isExpanded && ds?.items && (
          ds.items.map(child => renderFileRow(child, depth + 1))
        )}
        {isDir && isExpanded && ds?.error && (
          <div className="text-xs text-red-400 py-2"
               style={{ paddingLeft: `${36 + depth * 20}px` }}>
            加载失败
          </div>
        )}
      </div>
    )
  }

  /* ── Render ── */

  if (loading) return (
    <div className="card p-6 flex items-center justify-center gap-2 text-gray-500">
      <Loader2 size={18} className="animate-spin" /> 加载分享内容...
    </div>
  )
  if (error) return <ErrorBanner message={error} />

  const canSave = selectAll || selected.size > 0

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Link size={16} className="text-brand-400 flex-shrink-0" />
          <span className="text-sm text-gray-300 truncate">{url}</span>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
          {/* 一键转存 */}
          {suggestedPath && (
            <button
              onClick={handleQuickSave}
              disabled={saving || !canSave}
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
            disabled={saving || !canSave}
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

      {/* Selection bar */}
      <div className="px-4 py-2 border-b border-white/5 flex items-center justify-between bg-surface-1/50">
        <button
          onClick={handleSelectAll}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors"
        >
          {selectAll
            ? <CheckSquare size={14} className="text-brand-400" />
            : <Square size={14} />
          }
          {selectAll ? '全选' : '全选'}
        </button>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>
            已选 <span className="text-gray-300 font-medium">{selectAll ? (data?.total || '全部') : selectionInfo.count}</span> 个文件
          </span>
          <span className="text-gray-600">·</span>
          <span>
            大小 <span className="text-gray-300 font-medium">{selectionInfo.sizeFmt}</span>
            {selectionInfo.hasUnexpanded && (
              <span className="text-gray-600 ml-1" title="展开目录后显示精确大小">≈</span>
            )}
          </span>
        </div>
      </div>

      {/* ── 正则重命名面板 ── */}
      <div className="px-4 py-2 border-b border-white/5 flex items-center gap-2">
        <button
          onClick={() => {
            if (!showRename && !presets) {
              renameApi.presets().then(d => setPresets(d)).catch(() => {})
            }
            setShowRename(s => !s)
          }}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors
            ${showRename ? 'bg-purple-500/15 text-purple-300' : 'text-gray-500 hover:text-gray-300 hover:bg-surface-2'}`}
        >
          <Wand2 size={13} />
          正则重命名
        </button>
        {renamePattern && (
          <span className="text-[10px] text-purple-400/70 truncate">
            {renamePattern} → {renameReplace}
          </span>
        )}
      </div>

      {showRename && (
        <div className="px-4 py-3 border-b border-white/5 bg-surface-1/50 space-y-3">
          {/* 预设快捷按钮 */}
          {presets?.presets?.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-gray-600 flex-shrink-0">预设:</span>
              {presets.presets.map(p => (
                <button
                  key={p.name}
                  onClick={() => { setRenamePattern(p.name); setRenameReplace(p.replace); setRenamePreview(null) }}
                  className={`text-[10px] px-2 py-1 rounded transition-colors
                    ${renamePattern === p.name
                      ? 'bg-purple-500/20 text-purple-300 ring-1 ring-purple-500/30'
                      : 'bg-surface-2 text-gray-400 hover:text-gray-200 hover:bg-surface-3'
                    }`}
                  title={p.description}
                >
                  {p.name}
                </button>
              ))}
              {renamePattern && (
                <button
                  onClick={() => { setRenamePattern(''); setRenameReplace(''); setRenamePreview(null) }}
                  className="text-[10px] text-gray-600 hover:text-gray-400 flex items-center gap-0.5"
                >
                  <RotateCcw size={10} /> 清除
                </button>
              )}
            </div>
          )}

          {/* 输入框 */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-gray-600 mb-1 block">匹配 (pattern)</label>
              <input
                type="text"
                value={renamePattern}
                onChange={e => { setRenamePattern(e.target.value); setRenamePreview(null) }}
                placeholder="正则表达式或 $TV"
                className="input text-xs py-1.5 w-full font-mono"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-600 mb-1 block">替换 (replace)</label>
              <input
                type="text"
                value={renameReplace}
                onChange={e => { setRenameReplace(e.target.value); setRenamePreview(null) }}
                placeholder="替换模板，如 {TASKNAME}E{E}.{EXT}"
                className="input text-xs py-1.5 w-full font-mono"
              />
            </div>
          </div>

          {/* 魔法变量提示 */}
          {presets?.variables?.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] text-gray-600 flex-shrink-0">变量:</span>
              {presets.variables.map(v => (
                <button
                  key={v.name}
                  onClick={() => setRenameReplace(r => r + v.name)}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-gray-500
                             hover:text-purple-300 hover:bg-purple-500/10 transition-colors font-mono"
                  title={v.description}
                >
                  {v.name}
                </button>
              ))}
            </div>
          )}

          {/* 预览按钮 */}
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                if (!renamePattern && !renameReplace) return
                setPreviewLoading(true)
                try {
                  const result = await renameApi.preview(url, renamePattern, renameReplace)
                  setRenamePreview(result)
                } catch (e) {
                  setRenamePreview({ error: e.message })
                } finally {
                  setPreviewLoading(false)
                }
              }}
              disabled={previewLoading || (!renamePattern && !renameReplace)}
              className="btn-primary text-xs py-1.5 flex items-center gap-1.5"
            >
              {previewLoading ? <Loader2 size={12} className="animate-spin" /> : <Eye size={12} />}
              预览效果
            </button>
            {renamePreview?.items && (
              <span className="text-[10px] text-gray-500">
                {renamePreview.items.filter(i => i.changed).length} 个文件将被重命名，
                {renamePreview.items.filter(i => i.filtered).length} 个被过滤
              </span>
            )}
          </div>

          {/* 预览结果 */}
          {renamePreview?.error && (
            <div className="text-xs text-red-400 flex items-center gap-1">
              <XCircle size={12} /> {renamePreview.error}
            </div>
          )}
          {renamePreview?.items?.length > 0 && (
            <div className="max-h-[200px] overflow-y-auto rounded-lg border border-white/5">
              {renamePreview.items.map((item, i) => (
                <div key={i} className={`flex items-center gap-2 px-3 py-1.5 text-xs border-b border-white/[0.03]
                  ${item.filtered ? 'opacity-30' : ''}`}>
                  <span className="text-gray-500 truncate flex-1" title={item.original}>
                    {item.original}
                  </span>
                  {item.changed && !item.filtered ? (
                    <>
                      <Replace size={11} className="text-purple-400 flex-shrink-0" />
                      <span className="text-purple-300 truncate flex-1 font-medium" title={item.renamed}>
                        {item.renamed}
                      </span>
                    </>
                  ) : item.filtered ? (
                    <span className="text-red-400/50 text-[10px] flex-shrink-0">过滤</span>
                  ) : (
                    <span className="text-gray-600 text-[10px] flex-shrink-0">不变</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* File list with tree */}
      <div className="max-h-[400px] overflow-y-auto">
        {data?.items?.map(item => renderFileRow(item, 0))}
      </div>

      {/* Save result */}
      {saveResult && (
        <div className={`px-4 py-3 text-sm flex items-center gap-2
          ${saveResult.error ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
          {saveResult.error
            ? <><XCircle size={16} /> 转存失败: {saveResult.error}</>
            : <><CheckCircle2 size={16} /> 成功转存 {saveResult.saved} 个文件到 {saveResult.path}
                {saveResult.skipped > 0 && `（跳过 ${saveResult.skipped} 个已存在）`}
                {saveResult.renamed > 0 && `，重命名 ${saveResult.renamed} 个`}</>
          }
        </div>
      )}

      {/* 转存后重命名详情 */}
      {saveResult?.rename_details?.length > 0 && (
        <RenameResultPreview details={saveResult.rename_details} />
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
  const [searchParams, setSearchParams] = useSearchParams()
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

  // TMDB 推荐路径
  const [suggestedPath, setSuggestedPath] = useState(null)

  // 自动搜索标记
  const [autoSearchDone, setAutoSearchDone] = useState(false)

  const doSearch = useCallback((kw) => {
    if (!kw.trim()) return
    addSearchHistory('resource_search', kw.trim())
    setLoading(true)
    setError(null)
    setPreviewUrl(null)
    setSearchedKeyword(kw.trim())
    searchApi.query(kw.trim())
      .then(d => { setResults(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  // 从 URL 参数读取 keyword 和 path，自动触发搜索
  useEffect(() => {
    if (autoSearchDone) return
    const urlKw = searchParams.get('keyword')
    const urlPath = searchParams.get('path')
    if (urlKw) {
      setKeyword(urlKw)
      if (urlPath) setSuggestedPath(urlPath)
      doSearch(urlKw)
      setAutoSearchDone(true)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, autoSearchDone, doSearch, setSearchParams])

  const handleSearch = (e) => {
    e.preventDefault()
    if (!keyword.trim()) return
    setSuggestedPath(null)
    doSearch(keyword.trim())
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
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Search size={16} className="text-brand-400" />
            <span className="text-sm font-medium text-gray-300">关键词搜索</span>
          </div>
          <SearchInputWithHistory
            value={keyword}
            onChange={setKeyword}
            onSearch={(q) => { setKeyword(q); setSuggestedPath(null); doSearch(q) }}
            placeholder="输入影视名称搜索资源..."
            historyNs="resource_search"
            disabled={loading}
          />
        </div>

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

      {/* 智能提示区 */}
      {searchedKeyword && !loading && (
        <>
          <MediaLibHint keyword={searchedKeyword} />
          <MetaHint keyword={searchedKeyword} onSelectPath={setSuggestedPath} />
        </>
      )}

      {/* 已选择的推荐路径 */}
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
                        <span className="text-xs sm:text-sm text-green-400 font-mono truncate max-w-[200px] sm:max-w-none">
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
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
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
