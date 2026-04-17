import { useState, useEffect, useCallback } from 'react'
import {
  Folder, File, FileText, FileVideo, FileAudio, FileImage, FileArchive,
  ChevronRight, Home, Search, Plus, Trash2, Pencil, Download, HardDrive,
  ArrowUp, RefreshCw, X, Check,
} from 'lucide-react'
import { driveApi } from '../api/client'
import { PageSpinner, ErrorBanner, PageHeader, EmptyState } from '../components/UI'

/** 根据文件类型/名称选择图标 */
function FileIcon({ item, size = 18 }) {
  if (item.is_dir) return <Folder size={size} className="text-brand-400" />
  const name = (item.file_name || '').toLowerCase()
  if (/\.(mp4|mkv|avi|mov|wmv|flv|ts|rmvb)$/.test(name))
    return <FileVideo size={size} className="text-purple-400" />
  if (/\.(mp3|flac|wav|aac|ogg|wma|ape)$/.test(name))
    return <FileAudio size={size} className="text-green-400" />
  if (/\.(jpg|jpeg|png|gif|bmp|webp|svg|ico)$/.test(name))
    return <FileImage size={size} className="text-pink-400" />
  if (/\.(zip|rar|7z|tar|gz|bz2|xz)$/.test(name))
    return <FileArchive size={size} className="text-amber-400" />
  if (/\.(txt|md|srt|ass|ssa|sub|nfo|log|json|xml|csv)$/.test(name))
    return <FileText size={size} className="text-gray-400" />
  return <File size={size} className="text-gray-500" />
}

/** 面包屑导航 */
function Breadcrumb({ path, onNavigate }) {
  const parts = path.split('/').filter(Boolean)
  return (
    <div className="flex items-center gap-1 text-sm overflow-x-auto pb-1 min-h-[32px]">
      <button
        onClick={() => onNavigate('/')}
        className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-3
                   text-gray-400 hover:text-white transition-colors flex-shrink-0"
      >
        <Home size={14} /> 根目录
      </button>
      {parts.map((part, i) => {
        const fullPath = '/' + parts.slice(0, i + 1).join('/')
        const isLast = i === parts.length - 1
        return (
          <span key={fullPath} className="flex items-center gap-1 flex-shrink-0">
            <ChevronRight size={14} className="text-gray-600" />
            <button
              onClick={() => onNavigate(fullPath)}
              className={`px-2 py-1 rounded transition-colors truncate max-w-[200px]
                ${isLast
                  ? 'text-white font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-surface-3'
                }`}
              title={part}
            >
              {part}
            </button>
          </span>
        )
      })}
    </div>
  )
}

/** 新建文件夹对话框 */
function MkdirDialog({ currentPath, onCreated, onClose }) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    setError(null)
    try {
      const fullPath = currentPath === '/'
        ? `/${name.trim()}`
        : `${currentPath}/${name.trim()}`
      await driveApi.mkdir(fullPath)
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
         onClick={onClose}>
      <div className="card p-6 w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white mb-4">新建文件夹</h3>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="输入文件夹名称..."
            className="input w-full mb-3"
            autoFocus
          />
          {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="btn-ghost">取消</button>
            <button type="submit" className="btn-primary" disabled={loading || !name.trim()}>
              {loading ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/** 重命名内联编辑 */
function RenameInput({ item, onDone, onCancel }) {
  const [name, setName] = useState(item.file_name)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    const trimmed = name.trim()
    if (!trimmed || trimmed === item.file_name) { onCancel(); return }
    setLoading(true)
    try {
      await driveApi.rename(item.fid, trimmed)
      onDone()
    } catch {
      onCancel()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-1 flex-1 min-w-0">
      <input
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); if (e.key === 'Escape') onCancel() }}
        className="input text-sm py-1 flex-1 min-w-0"
        autoFocus
        disabled={loading}
      />
      <button onClick={handleSubmit} className="p-1 text-green-400 hover:text-green-300" title="确认">
        <Check size={16} />
      </button>
      <button onClick={onCancel} className="p-1 text-gray-500 hover:text-gray-300" title="取消">
        <X size={16} />
      </button>
    </div>
  )
}

/** 删除确认对话框 */
function DeleteDialog({ items, onConfirm, onClose }) {
  const [loading, setLoading] = useState(false)

  const handleDelete = async () => {
    setLoading(true)
    try {
      await driveApi.delete(items.map(i => i.fid))
      onConfirm()
    } catch {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
         onClick={onClose}>
      <div className="card p-6 w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white mb-2">确认删除</h3>
        <p className="text-gray-400 text-sm mb-4">
          将删除 {items.length} 个文件/文件夹，移入回收站。
        </p>
        <div className="max-h-40 overflow-y-auto mb-4 space-y-1">
          {items.map(item => (
            <div key={item.fid} className="flex items-center gap-2 text-sm text-gray-300">
              <FileIcon item={item} size={14} />
              <span className="truncate">{item.file_name}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-ghost">取消</button>
          <button onClick={handleDelete} disabled={loading}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium
                       transition-colors disabled:opacity-50">
            {loading ? '删除中...' : '确认删除'}
          </button>
        </div>
      </div>
    </div>
  )
}

/** 格式化时间 */
function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
    return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

export default function DrivePage() {
  const [path, setPath] = useState('/')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [showMkdir, setShowMkdir] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [renamingFid, setRenamingFid] = useState(null)
  const [searchMode, setSearchMode] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [spaceInfo, setSpaceInfo] = useState(null)

  const fetchDir = useCallback((p) => {
    setLoading(true)
    setError(null)
    setSelected(new Set())
    setRenamingFid(null)
    driveApi.ls(p)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  useEffect(() => { fetchDir(path) }, [path, fetchDir])
  useEffect(() => {
    driveApi.space().then(setSpaceInfo).catch(() => {})
  }, [])

  const navigateTo = (p) => {
    setSearchMode(false)
    setSearchKeyword('')
    setPath(p)
  }

  const goUp = () => {
    if (path === '/') return
    const parts = path.split('/').filter(Boolean)
    parts.pop()
    navigateTo(parts.length > 0 ? '/' + parts.join('/') : '/')
  }

  const handleItemClick = (item) => {
    if (item.is_dir) {
      const newPath = path === '/' ? `/${item.file_name}` : `${path}/${item.file_name}`
      navigateTo(newPath)
    }
  }

  const toggleSelect = (fid, e) => {
    e.stopPropagation()
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(fid)) next.delete(fid)
      else next.add(fid)
      return next
    })
  }

  const handleSearch = (e) => {
    e.preventDefault()
    if (!searchKeyword.trim()) return
    setLoading(true)
    setError(null)
    setSearchMode(true)
    driveApi.search(searchKeyword.trim(), path)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  const handleDownload = async (item) => {
    try {
      const result = await driveApi.download(item.fid)
      if (result.items?.[0]?.download_url) {
        window.open(result.items[0].download_url, '_blank')
      }
    } catch {}
  }

  const selectedItems = data?.items?.filter(i => selected.has(i.fid)) || []
  const usedPct = spaceInfo
    ? ((spaceInfo.use_capacity / spaceInfo.total_capacity) * 100).toFixed(1)
    : null

  return (
    <>
      {/* Header with space info */}
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <PageHeader
          title="网盘文件"
          description={spaceInfo ? `${spaceInfo.used_fmt} / ${spaceInfo.total_fmt} (${usedPct}%)` : ''}
        />
        {spaceInfo && (
          <div className="flex items-center gap-3 mt-1">
            <HardDrive size={16} className="text-gray-500" />
            <div className="w-32 h-2 bg-surface-3 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  Number(usedPct) > 90 ? 'bg-red-500' : Number(usedPct) > 70 ? 'bg-amber-500' : 'bg-brand-500'
                }`}
                style={{ width: `${usedPct}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Breadcrumb path={path} onNavigate={navigateTo} />

        <div className="flex-1" />

        {/* Search */}
        <form onSubmit={handleSearch} className="flex items-center gap-1">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={searchKeyword}
              onChange={e => setSearchKeyword(e.target.value)}
              placeholder="搜索当前目录..."
              className="input text-sm py-1.5 pl-8 w-40 focus:w-56 transition-all"
            />
          </div>
        </form>

        {/* Actions */}
        <button onClick={goUp} disabled={path === '/'} title="上级目录"
          className="btn-ghost p-2 disabled:opacity-30">
          <ArrowUp size={16} />
        </button>
        <button onClick={() => fetchDir(path)} title="刷新" className="btn-ghost p-2">
          <RefreshCw size={16} />
        </button>
        <button onClick={() => setShowMkdir(true)} title="新建文件夹"
          className="btn-ghost p-2 text-green-400 hover:text-green-300">
          <Plus size={16} />
        </button>
        {selected.size > 0 && (
          <button onClick={() => setShowDelete(true)} title="删除选中"
            className="btn-ghost p-2 text-red-400 hover:text-red-300">
            <Trash2 size={16} />
            <span className="text-xs ml-1">{selected.size}</span>
          </button>
        )}
      </div>

      {/* Search active banner */}
      {searchMode && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-brand-600/20 rounded-lg text-sm">
          <Search size={14} className="text-brand-400" />
          <span className="text-gray-300">搜索 "{searchKeyword}" 的结果：{data?.total || 0} 个</span>
          <button onClick={() => { setSearchMode(false); setSearchKeyword(''); fetchDir(path) }}
            className="ml-auto text-brand-400 hover:text-brand-300 text-xs">
            清除搜索
          </button>
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={() => fetchDir(path)} />}

      {loading ? (
        <PageSpinner />
      ) : data?.items?.length > 0 ? (
        <div className="card overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[40px_1fr_100px_180px_80px] gap-2 px-4 py-2.5
                          border-b border-white/5 text-xs text-gray-500 font-medium uppercase tracking-wider">
            <div />
            <div>名称</div>
            <div className="text-right">大小</div>
            <div>修改时间</div>
            <div className="text-center">操作</div>
          </div>

          {/* File list */}
          {data.items.map(item => (
            <div
              key={item.fid}
              className={`grid grid-cols-[40px_1fr_100px_180px_80px] gap-2 px-4 py-2.5 items-center
                         border-b border-white/[0.03] transition-colors group
                         ${selected.has(item.fid) ? 'bg-brand-600/10' : 'hover:bg-surface-2'}
                         ${item.is_dir ? 'cursor-pointer' : ''}`}
              onClick={() => handleItemClick(item)}
            >
              {/* Checkbox */}
              <div className="flex justify-center">
                <input
                  type="checkbox"
                  checked={selected.has(item.fid)}
                  onChange={e => toggleSelect(item.fid, e)}
                  className="w-4 h-4 rounded border-gray-600 bg-surface-3 text-brand-500
                             focus:ring-brand-500 focus:ring-offset-0 cursor-pointer"
                />
              </div>

              {/* Name */}
              <div className="flex items-center gap-2.5 min-w-0">
                <FileIcon item={item} />
                {renamingFid === item.fid ? (
                  <RenameInput
                    item={item}
                    onDone={() => { setRenamingFid(null); fetchDir(path) }}
                    onCancel={() => setRenamingFid(null)}
                  />
                ) : (
                  <span className={`truncate text-sm ${item.is_dir ? 'text-brand-300 font-medium' : 'text-gray-200'}`}
                        title={item.file_name}>
                    {item.file_name}
                  </span>
                )}
              </div>

              {/* Size */}
              <div className="text-right text-xs text-gray-500">{item.size_fmt}</div>

              {/* Time */}
              <div className="text-xs text-gray-600">{formatTime(item.updated_at)}</div>

              {/* Actions */}
              <div className="flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                   onClick={e => e.stopPropagation()}>
                <button
                  onClick={() => setRenamingFid(item.fid)}
                  className="p-1 text-gray-500 hover:text-white" title="重命名"
                >
                  <Pencil size={14} />
                </button>
                {!item.is_dir && (
                  <button
                    onClick={() => handleDownload(item)}
                    className="p-1 text-gray-500 hover:text-brand-400" title="下载"
                  >
                    <Download size={14} />
                  </button>
                )}
                <button
                  onClick={() => { setSelected(new Set([item.fid])); setShowDelete(true) }}
                  className="p-1 text-gray-500 hover:text-red-400" title="删除"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}

          {/* Footer */}
          <div className="px-4 py-3 text-xs text-gray-600 flex items-center gap-4">
            <span>{data.dirs_count} 个文件夹</span>
            <span>{data.files_count} 个文件</span>
            <span>总计 {data.total_size_fmt}</span>
          </div>
        </div>
      ) : (
        <EmptyState icon={Folder} title="空目录" description="这里还没有文件" />
      )}

      {/* Dialogs */}
      {showMkdir && (
        <MkdirDialog
          currentPath={path}
          onCreated={() => { setShowMkdir(false); fetchDir(path) }}
          onClose={() => setShowMkdir(false)}
        />
      )}
      {showDelete && selectedItems.length > 0 && (
        <DeleteDialog
          items={selectedItems}
          onConfirm={() => { setShowDelete(false); fetchDir(path) }}
          onClose={() => setShowDelete(false)}
        />
      )}
    </>
  )
}
