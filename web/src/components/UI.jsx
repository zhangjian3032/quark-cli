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
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {description && <p className="text-sm text-gray-500 mt-1">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-center gap-2 mt-8">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="btn-ghost text-sm"
      >
        上一页
      </button>
      <span className="text-sm text-gray-500">
        {page} / {totalPages}
      </span>
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
