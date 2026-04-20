/**
 * 带搜索历史下拉的搜索输入框
 *
 * Props:
 *   value        - 受控值
 *   onChange      - 输入变化回调
 *   onSearch      - 点击搜索 / 回车触发的回调 (query) => void
 *   placeholder   - 占位文字
 *   historyNs     - 历史记录命名空间 (如 'person', 'meta')
 *   disabled      - 是否禁用搜索按钮
 *   className     - 外层容器追加样式
 */
import { useState, useRef, useEffect } from 'react'
import { Search, Clock, X } from 'lucide-react'
import { getSearchHistory, addSearchHistory, removeSearchHistory, clearSearchHistory } from '../utils/searchHistory'

export default function SearchInputWithHistory({
  value,
  onChange,
  onSearch,
  placeholder = '搜索…',
  historyNs = 'default',
  disabled = false,
  className = '',
}) {
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState([])
  const containerRef = useRef(null)
  const inputRef = useRef(null)

  // 刷新历史列表
  const refreshHistory = () => setHistory(getSearchHistory(historyNs))

  // 输入框获得焦点时显示历史
  const handleFocus = () => {
    refreshHistory()
    setShowHistory(true)
  }

  // 点击外部关闭
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowHistory(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const doSearch = (q) => {
    const query = (q ?? value).trim()
    if (!query) return
    addSearchHistory(historyNs, query)
    setShowHistory(false)
    if (onSearch) onSearch(query)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') doSearch()
  }

  const handleSelectHistory = (item) => {
    onChange(item)
    // 立即搜索
    setTimeout(() => doSearch(item), 0)
  }

  const handleRemoveItem = (e, item) => {
    e.stopPropagation()
    removeSearchHistory(historyNs, item)
    refreshHistory()
  }

  const handleClearAll = (e) => {
    e.stopPropagation()
    clearSearchHistory(historyNs)
    setHistory([])
  }

  // 过滤: 如果输入框有内容, 只显示匹配的历史
  const filteredHistory = value.trim()
    ? history.filter(h => h.toLowerCase().includes(value.trim().toLowerCase()))
    : history

  return (
    <div ref={containerRef} className={`relative flex-1 ${className}`}>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            placeholder={placeholder}
            className="w-full pl-9 pr-3 py-2 text-sm text-white bg-surface-2 border border-surface-3
                       rounded-lg focus:outline-none focus:border-brand-500 placeholder:text-gray-600
                       transition-colors"
          />
        </div>
        <button
          onClick={() => doSearch()}
          disabled={disabled || !value.trim()}
          className="btn-primary text-sm px-4 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          搜索
        </button>
      </div>

      {/* 搜索历史下拉 */}
      {showHistory && filteredHistory.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-16 mt-1 bg-surface-2 border border-surface-3
                        rounded-lg shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/5">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider flex items-center gap-1">
              <Clock size={10} /> 最近搜索
            </span>
            <button
              onClick={handleClearAll}
              className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors"
            >
              清空
            </button>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {filteredHistory.map((item, i) => (
              <div
                key={i}
                onClick={() => handleSelectHistory(item)}
                className="flex items-center justify-between px-3 py-2 text-sm text-gray-300
                           hover:bg-surface-3 cursor-pointer transition-colors group"
              >
                <span className="truncate">{item}</span>
                <button
                  onClick={(e) => handleRemoveItem(e, item)}
                  className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-gray-400
                             transition-all p-0.5"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
