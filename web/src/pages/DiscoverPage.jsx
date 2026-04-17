import { useState, useEffect } from 'react'
import { Star, TrendingUp, Flame, SlidersHorizontal } from 'lucide-react'
import { discoveryApi } from '../api/client'
import MediaCard from '../components/MediaCard'
import { PageSpinner, EmptyState, ErrorBanner, PageHeader, Pagination } from '../components/UI'

const LIST_TYPES = [
  { key: 'top_rated', label: '高分', icon: Star },
  { key: 'popular',   label: '热门', icon: Flame },
  { key: 'trending',  label: '趋势', icon: TrendingUp },
  { key: 'discover',  label: '筛选', icon: SlidersHorizontal },
]

const MEDIA_TYPES = [
  { key: 'movie', label: '电影' },
  { key: 'tv',    label: '剧集' },
]

export default function DiscoverPage() {
  const [listType, setListType] = useState('top_rated')
  const [mediaType, setMediaType] = useState('movie')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 筛选参数
  const [minRating, setMinRating] = useState('')
  const [genre, setGenre] = useState('')
  const [year, setYear] = useState('')

  const doFetch = (p = 1) => {
    setLoading(true)
    setError(null)
    setPage(p)

    discoveryApi.list({
      listType,
      mediaType,
      page: p,
      ...(listType === 'discover' ? {
        minRating: minRating ? parseFloat(minRating) : null,
        genre: genre || null,
        year: year ? parseInt(year) : null,
      } : {}),
    })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  useEffect(() => { doFetch(1) }, [listType, mediaType])

  return (
    <>
      <PageHeader title="影视发现" description="TMDB 高分推荐与趋势" />

      {/* Controls */}
      <div className="flex flex-wrap gap-3 mb-6">
        {/* List type tabs */}
        <div className="flex bg-surface-1 rounded-lg p-1 gap-1">
          {LIST_TYPES.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setListType(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
                         transition-colors
                ${listType === key
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-400 hover:text-white'
                }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Media type toggle */}
        <div className="flex bg-surface-1 rounded-lg p-1 gap-1">
          {MEDIA_TYPES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setMediaType(key)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors
                ${mediaType === key
                  ? 'bg-surface-3 text-white'
                  : 'text-gray-400 hover:text-white'
                }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Discover filters */}
      {listType === 'discover' && (
        <div className="flex flex-wrap gap-3 mb-6 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">最低评分</label>
            <input
              type="number" step="0.1" min="0" max="10"
              value={minRating}
              onChange={e => setMinRating(e.target.value)}
              placeholder="如 8.0"
              className="input w-24 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">类型</label>
            <input
              type="text"
              value={genre}
              onChange={e => setGenre(e.target.value)}
              placeholder="如 科幻,动作"
              className="input w-36 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">年份</label>
            <input
              type="number" min="1900" max="2030"
              value={year}
              onChange={e => setYear(e.target.value)}
              placeholder="如 2025"
              className="input w-24 text-sm"
            />
          </div>
          <button onClick={() => doFetch(1)} className="btn-primary text-sm">
            筛选
          </button>
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={() => doFetch(page)} />}

      {loading ? (
        <PageSpinner />
      ) : data?.items?.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {data.items.map(item => (
              <MediaCard
                key={item.tmdb_id}
                item={{ ...item, guid: item.tmdb_id }}
                posterUrl={item.poster_url}
                showType
              />
            ))}
          </div>
          <Pagination page={data.page} totalPages={data.total_pages} onChange={p => doFetch(p)} />
        </>
      ) : (
        <EmptyState icon={Star} title="暂无结果" description="换个条件试试" />
      )}
    </>
  )
}
