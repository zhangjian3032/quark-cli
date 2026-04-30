import { useState } from 'react'
import { Loader2 } from 'lucide-react'

export function Spinner({ className = '' }) {
  return <Loader2 className={`animate-spin text-brand-400 ${className}`} size={24} />
}

export function PageSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <Spinner />
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {Icon && <Icon size={48} className="text-gray-600 mb-4" />}
      <h3 className="text-lg font-medium text-gray-400">{title}</h3>
      {description && <p className="text-sm text-gray-600 mt-1">{description}</p>}
    </div>
  )
}

export function ErrorBanner({ message, onRetry }) {
  return (
    <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-4 flex items-center justify-between">
      <span className="text-red-300 text-sm">{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-red-300 text-sm">重试</button>
      )}
    </div>
  )
}

export function PageHeader({ title, description, children }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 sm:mb-6 gap-2">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-white">{title}</h1>
        {description && <p className="text-sm text-gray-500 mt-1">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export function Pagination({ page, totalPages, onChange }) {
  const [inputVal, setInputVal] = useState('')
  const [editing, setEditing] = useState(false)

  if (totalPages <= 1) return null

  const handleGo = () => {
    const n = parseInt(inputVal, 10)
    if (n >= 1 && n <= totalPages && n !== page) {
      onChange(n)
    }
    setEditing(false)
    setInputVal('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleGo()
    if (e.key === 'Escape') { setEditing(false); setInputVal('') }
  }

  return (
    <div className="flex items-center justify-center gap-2 mt-8">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="btn-ghost text-sm"
      >
        上一页
      </button>

      {editing ? (
        <div className="flex items-center gap-1.5">
          <input
            type="number"
            min={1}
            max={totalPages}
            value={inputVal}
            onChange={e => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleGo}
            autoFocus
            placeholder={String(page)}
            className="w-16 px-2 py-1 text-sm text-center text-white bg-surface-2 border border-surface-3
                       rounded focus:outline-none focus:border-brand-500
                       [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
          <span className="text-sm text-gray-500">/ {totalPages}</span>
        </div>
      ) : (
        <button
          onClick={() => { setEditing(true); setInputVal('') }}
          className="text-sm text-gray-500 hover:text-brand-400 transition-colors cursor-pointer"
          title="点击输入页码"
        >
          {page} / {totalPages}
        </button>
      )}

      <button
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        className="btn-ghost text-sm"
      >
        下一页
      </button>
    </div>
  )
}
