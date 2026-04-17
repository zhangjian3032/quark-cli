import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Library, FolderOpen, Search as SearchIcon, X } from 'lucide-react'
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

  // ── 搜索状态 ──
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchPage, setSearchPage] = useState(1)

  const isSearchMode = searchResults !== null

  // 加载媒体库列表
  useEffect(() => {
    mediaApi.libraries()
      .then(setLibraries)
      .catch(e => setError(e.message))
  }, [])

  // 加载媒体库内容
  useEffect(() => {
    if (isSearchMode) return

    if (!libId && libraries.length > 0) {
      navigate(`/library/${libraries[0].guid}`, { replace: true })
      return
    }
    if (!libId) return

    setLoading(true)
    setError(null)
    mediaApi.libraryItems(libId, page, pageSize)
      .then(data => { setItems(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [libId, page, libraries, navigate, isSearchMode])

  // ── 搜索 ──
  const doSearch = useCallback((kw, p = 1) => {
    if (!kw.trim()) return
    setSearchLoading(true)
    setSearchPage(p)
    mediaApi.search(kw.trim(), p, pageSize)
      .then(data => { setSearchResults(data); setSearchLoading(false) })
      .catch(() => { setSearchLoading(false) })
  }, [])

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    if (!searchKeyword.trim()) return
    doSearch(searchKeyword, 1)
  }

  const clearSearch = () => {
    setSearchKeyword('')
    setSearchResults(null)
    setSearchPage(1)
  }

  const currentLib = libraries.find(l => l.guid === libId)
  const totalPages = items ? Math.ceil(items.total / pageSize) : 1
  const searchTotalPages = searchResults ? Math.ceil(searchResults.total / pageSize) : 1

  return (
    <>
      <PageHeader
        title={isSearchMode ? '搜索结果' : (currentLib?.title || '媒体库')}
        description={
          isSearchMode
            ? (searchResults ? `找到 ${searchResults.total} 个结果` : '')
            : (items ? `共 ${items.total} 部` : '')
        }
      />

      {/* 搜索栏 */}
      <form onSubmit={handleSearchSubmit} className="flex gap-3 mb-5">
        <div className="relative flex-1">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={searchKeyword}
            onChange={e => setSearchKeyword(e.target.value)}
            placeholder="搜索媒体库..."
            className="input w-full pl-10 pr-10"
          />
          {searchKeyword && (
            <button type="button" onClick={clearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors">
              <X size={16} />
            </button>
          )}
        </div>
        <button type="submit" className="btn-primary" disabled={searchLoading || !searchKeyword.trim()}>
          搜索
        </button>
      </form>

      {/* 搜索模式 */}
      {isSearchMode ? (
        <>
          {/* 返回浏览 */}
          <button onClick={clearSearch}
            className="text-xs text-brand-400 hover:text-brand-300 mb-4 flex items-center gap-1 transition-colors">
            ← 返回媒体库浏览
          </button>

          {searchLoading ? (
            <PageSpinner />
          ) : searchResults?.items?.length > 0 ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {searchResults.items.map(item => (
                  <MediaCard key={item.guid} item={item} posterUrl={item.poster_url} showType />
                ))}
              </div>
              <Pagination
                page={searchPage}
                totalPages={searchTotalPages}
                onChange={p => doSearch(searchKeyword, p)}
              />
            </>
          ) : (
            <EmptyState
              icon={SearchIcon}
              title={`未找到 "${searchKeyword}"`}
              description="试试其他关键词"
            />
          )}
        </>
      ) : (
        <>
          {/* 媒体库标签 */}
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
                  <MediaCard key={item.guid} item={item} posterUrl={item.poster_url} showType />
                ))}
              </div>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            </>
          ) : (
            <EmptyState icon={Library} title="暂无影片" description="该媒体库还没有影片" />
          )}
        </>
      )}
    </>
  )
}
