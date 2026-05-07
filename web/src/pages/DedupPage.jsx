import { useState, useEffect } from 'react'
import { mediaApi } from '../api/client'
import { Copy, Trash2, Star, AlertTriangle, HardDrive, RefreshCw, CheckCircle2, CheckSquare, Square } from 'lucide-react'

function formatSize(bytes) {
  if (!bytes || bytes <= 0) return '未知'
  const gb = bytes / (1024 ** 3)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 ** 2)
  return `${mb.toFixed(0)} MB`
}

function QualityBadge({ text, variant = 'default' }) {
  const colors = {
    best: 'bg-green-500/20 text-green-400 border-green-500/30',
    removable: 'bg-red-500/15 text-red-400 border-red-500/30',
    default: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${colors[variant]}`}>
      {text}
    </span>
  )
}

function ScoreBar({ score, maxScore = 350 }) {
  const pct = Math.min(100, (score / maxScore) * 100)
  const color = score >= 250 ? 'bg-green-500' : score >= 150 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-8 text-right">{Math.round(score)}</span>
    </div>
  )
}

function DuplicateGroupCard({ group, index, selectedEntries, onToggleEntry }) {
  const [expanded, setExpanded] = useState(false)

  // 该组中可移除条目的 guid 列表
  const removableGuids = group.entries.filter(e => !e.is_best).map(e => e.guid)
  const selectedInGroup = removableGuids.filter(guid => selectedEntries.has(guid))
  const allRemovableSelected = removableGuids.length > 0 && selectedInGroup.length === removableGuids.length

  return (
    <div className="bg-surface-1 border border-surface-3 rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-surface-2 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center text-brand-400 text-sm font-bold">
            {index}
          </div>
          <div>
            <div className="font-medium text-white">
              {group.title}
              {group.year && <span className="text-gray-400 ml-1.5">({group.year})</span>}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {group.count} 个版本 · 总计 {formatSize(group.total_size)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {selectedInGroup.length > 0 && (
            <span className="text-xs text-brand-400 bg-brand-600/10 px-2 py-1 rounded">
              已选 {selectedInGroup.length}
            </span>
          )}
          {group.saveable_size > 0 && (
            <span className="text-xs text-green-400 bg-green-500/10 px-2 py-1 rounded">
              可节省 {formatSize(group.saveable_size)}
            </span>
          )}
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Entries */}
      {expanded && (
        <div className="border-t border-surface-3 divide-y divide-surface-3">
          {group.entries.map((entry, i) => {
            const isSelected = selectedEntries.has(entry.guid)
            return (
              <div key={entry.guid} className={`px-5 py-3 flex items-center gap-4 ${entry.is_best ? 'bg-green-500/5' : ''}`}>
                {/* Checkbox (仅非最佳版本可选) */}
                <div className="w-5 flex-shrink-0">
                  {!entry.is_best && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onToggleEntry(entry.guid) }}
                      className="text-gray-400 hover:text-white transition-colors"
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-brand-400" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>

                {/* Rank & Badge */}
                <div className="flex items-center gap-2 min-w-[90px]">
                  {entry.is_best ? (
                    <Star className="w-4 h-4 text-green-400" />
                  ) : (
                    <Trash2 className="w-4 h-4 text-red-400/60" />
                  )}
                  <QualityBadge
                    text={entry.is_best ? '推荐保留' : '可移除'}
                    variant={entry.is_best ? 'best' : 'removable'}
                  />
                </div>

                {/* Quality Info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">{entry.quality || '未识别'}</div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">{entry.title}</div>
                </div>

                {/* Score */}
                <ScoreBar score={entry.score} />

                {/* Size */}
                <div className="text-xs text-gray-400 w-20 text-right">
                  {entry.size || '未知'}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function DedupPage() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [libraries, setLibraries] = useState([])
  const [selectedLib, setSelectedLib] = useState('')
  const [selectedEntries, setSelectedEntries] = useState(new Set())

  // 加载媒体库列表
  useEffect(() => {
    mediaApi.libraries()
      .then(libs => setLibraries(Array.isArray(libs) ? libs : []))
      .catch(() => {})
  }, [])

  const runDedup = async () => {
    setLoading(true)
    setError('')
    setData(null)
    setSelectedEntries(new Set())
    try {
      const result = await mediaApi.dedup(selectedLib)
      setData(result)
    } catch (e) {
      setError(e.message || '检测失败')
    } finally {
      setLoading(false)
    }
  }

  // 获取所有可移除条目的 guid
  const allRemovableGuids = (data?.duplicate_groups || []).flatMap(
    g => g.entries.filter(e => !e.is_best).map(e => e.guid)
  )

  const isAllSelected = allRemovableGuids.length > 0 && allRemovableGuids.every(guid => selectedEntries.has(guid))
  const isSomeSelected = selectedEntries.size > 0

  const handleSelectAll = () => {
    if (isAllSelected) {
      // 全部取消
      setSelectedEntries(new Set())
    } else {
      // 全部选中
      setSelectedEntries(new Set(allRemovableGuids))
    }
  }

  const handleToggleEntry = (guid) => {
    setSelectedEntries(prev => {
      const next = new Set(prev)
      if (next.has(guid)) {
        next.delete(guid)
      } else {
        next.add(guid)
      }
      return next
    })
  }

  // 计算选中的总大小
  const selectedSize = (data?.duplicate_groups || []).reduce((total, g) => {
    return total + g.entries
      .filter(e => selectedEntries.has(e.guid))
      .reduce((sum, e) => sum + (e.size_bytes || 0), 0)
  }, 0)

  const summary = data?.summary

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Copy className="w-5 h-5 text-brand-400" />
            同名多版本去重
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            检测媒体库中同一影片的多个画质版本，推荐保留最佳版本
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 bg-surface-1 border border-surface-3 rounded-xl px-5 py-4">
        <select
          value={selectedLib}
          onChange={e => setSelectedLib(e.target.value)}
          className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">全部媒体库</option>
          {libraries.map(lib => (
            <option key={lib.guid} value={lib.guid}>{lib.title} ({lib.count})</option>
          ))}
        </select>

        <button
          onClick={runDedup}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50
                     text-white text-sm font-medium rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          {loading ? '检测中...' : '开始检测'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-xl px-5 py-3 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-surface-1 border border-surface-3 rounded-xl px-5 py-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">重复组数</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.total_groups}</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl px-5 py-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">涉及影片</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.total_entries}</div>
          </div>
          <div className="bg-surface-1 border border-surface-3 rounded-xl px-5 py-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">可节省空间</div>
            <div className="text-2xl font-bold text-green-400 mt-1">
              {formatSize(summary.total_saveable_bytes)}
            </div>
          </div>
        </div>
      )}

      {/* Batch Action Bar */}
      {data && data.duplicate_groups?.length > 0 && (
        <div className="flex items-center justify-between bg-surface-1 border border-surface-3 rounded-xl px-5 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={handleSelectAll}
              className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              {isAllSelected ? (
                <CheckSquare className="w-4 h-4 text-brand-400" />
              ) : (
                <Square className="w-4 h-4" />
              )}
              {isAllSelected ? '取消全选' : '全选可移除'}
            </button>

            {isSomeSelected && (
              <span className="text-xs text-gray-500">
                已选 {selectedEntries.size} 项 · {formatSize(selectedSize)}
              </span>
            )}
          </div>

          {isSomeSelected && (
            <button
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500
                         text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              删除选中 ({selectedEntries.size})
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {data && data.duplicate_groups?.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-500">
          <CheckCircle2 className="w-12 h-12 text-green-400 mb-3" />
          <div className="text-lg font-medium text-white">没有发现重复影片</div>
          <div className="text-sm mt-1">你的媒体库很整洁！</div>
        </div>
      )}

      {data && data.duplicate_groups?.length > 0 && (
        <div className="space-y-3">
          {data.duplicate_groups.map((group, i) => (
            <DuplicateGroupCard
              key={group.key}
              group={group}
              index={i + 1}
              selectedEntries={selectedEntries}
              onToggleEntry={handleToggleEntry}
            />
          ))}
        </div>
      )}
    </div>
  )
}
