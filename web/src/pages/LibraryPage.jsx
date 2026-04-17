import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Library, FolderOpen } from 'lucide-react'
import { mediaApi } from '../api/client'
import MediaCard from '../components/MediaCard'
import { PageSpinner, EmptyState, ErrorBanner, PageHeader, Pagination } from '../components/UI'

export default function LibraryPage() {
  const { libId } = useParams()
  const navigate = useNavigate()

  const [libraries, setLibraries] = useState([])
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const pageSize = 24

  // 加载媒体库列表
  useEffect(() => {
    mediaApi.libraries()
      .then(setLibraries)
      .catch(e => setError(e.message))
  }, [])

  // 加载媒体库内容
  useEffect(() => {
    if (!libId && libraries.length > 0) {
      // 默认进第一个库
      navigate(`/library/${libraries[0].guid}`, { replace: true })
      return
    }
    if (!libId) return

    setLoading(true)
    setError(null)
    mediaApi.libraryItems(libId, page, pageSize)
      .then(data => { setItems(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [libId, page, libraries, navigate])

  const currentLib = libraries.find(l => l.guid === libId)
  const totalPages = items ? Math.ceil(items.total / pageSize) : 1

  return (
    <>
      <PageHeader
        title={currentLib?.title || '媒体库'}
        description={items ? `共 ${items.total} 部` : ''}
      />

      {/* Library tabs */}
      {libraries.length > 0 && (
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {libraries.map(lib => (
            <button
              key={lib.guid}
              onClick={() => { setPage(1); navigate(`/library/${lib.guid}`) }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                         whitespace-nowrap transition-colors
                ${lib.guid === libId
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface-2 text-gray-400 hover:text-white hover:bg-surface-3'
                }`}
            >
              <FolderOpen size={16} />
              {lib.title}
              <span className="text-xs opacity-60">{lib.count}</span>
            </button>
          ))}
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={() => setPage(page)} />}

      {loading ? (
        <PageSpinner />
      ) : items && items.items?.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {items.items.map(item => (
              <MediaCard key={item.guid} item={item} showType />
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onChange={setPage} />
        </>
      ) : (
        <EmptyState icon={Library} title="暂无影片" description="该媒体库还没有影片" />
      )}
    </>
  )
}
