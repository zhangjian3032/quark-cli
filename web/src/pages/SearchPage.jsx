import { useState } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import { mediaApi } from '../api/client'
import MediaCard from '../components/MediaCard'
import { PageSpinner, EmptyState, PageHeader, Pagination } from '../components/UI'

export default function SearchPage() {
  const [keyword, setKeyword] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const pageSize = 24

  const doSearch = (p = 1) => {
    if (!keyword.trim()) return
    setLoading(true)
    setPage(p)
    mediaApi.search(keyword.trim(), p, pageSize)
      .then(data => { setResults(data); setLoading(false) })
      .catch(() => setLoading(false))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    doSearch(1)
  }

  return (
    <>
      <PageHeader title="搜索影片" description="在媒体库中搜索" />

      <form onSubmit={handleSubmit} className="flex gap-3 mb-8">
        <div className="relative flex-1">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="输入影片名称..."
            className="input w-full pl-10"
            autoFocus
          />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          搜索
        </button>
      </form>

      {loading ? (
        <PageSpinner />
      ) : results ? (
        results.items?.length > 0 ? (
          <>
            <p className="text-sm text-gray-500 mb-4">
              找到 {results.total} 个结果
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {results.items.map(item => (
                <MediaCard
                  key={item.guid}
                  item={item}
                  posterUrl={item.poster_url}
                  showType
                />
              ))}
            </div>
            <Pagination
              page={page}
              totalPages={Math.ceil(results.total / pageSize)}
              onChange={p => doSearch(p)}
            />
          </>
        ) : (
          <EmptyState
            icon={SearchIcon}
            title={`未找到 "${keyword}"`}
            description="试试其他关键词"
          />
        )
      ) : (
        <EmptyState
          icon={SearchIcon}
          title="搜索媒体库"
          description="输入影片名称开始搜索"
        />
      )}
    </>
  )
}
