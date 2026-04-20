/**
 * 演员详情页 — 展示演员信息 + 参演作品
 * 路由: /discover/person/:personId?source=tmdb
 */
import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Star, Film, Tv, User, Calendar, Tag,
} from 'lucide-react'
import { discoveryApi } from '../api/client'
import MediaCard from '../components/MediaCard'
import { PageSpinner, ErrorBanner, PageHeader, EmptyState } from '../components/UI'

const CREDIT_FILTERS = [
  { key: '',      label: '全部' },
  { key: 'movie', label: '电影' },
  { key: 'tv',    label: '剧集' },
]

const CREDIT_SORTS = [
  { key: 'rating',  label: '评分最高' },
  { key: 'year',    label: '最新' },
  { key: 'popular', label: '热度' },
]

export default function PersonDetailPage() {
  const { personId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const source = searchParams.get('source') || null

  const [credits, setCredits] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 筛选 & 排序
  const [filterType, setFilterType] = useState('')
  const [sortKey, setSortKey] = useState('rating')

  useEffect(() => {
    setLoading(true)
    setError(null)
    discoveryApi.personCredits(personId, null, source)
      .then(d => { setCredits(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [personId, source])

  if (loading) return <PageSpinner />
  if (error) return <ErrorBanner message={error} />

  const allItems = credits?.credits || []

  // 筛选
  const filtered = filterType
    ? allItems.filter(c => c.media_type === filterType)
    : allItems

  // 排序
  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === 'rating') return (b.rating || 0) - (a.rating || 0)
    if (sortKey === 'year') return (b.year || 0) - (a.year || 0)
    if (sortKey === 'popular') return (b.vote_count || 0) - (a.vote_count || 0)
    return 0
  })

  // 统计
  const movieCount = allItems.filter(c => c.media_type === 'movie').length
  const tvCount = allItems.filter(c => c.media_type === 'tv').length
  const avgRating = allItems.length > 0
    ? (allItems.reduce((s, c) => s + (c.rating || 0), 0) / allItems.length).toFixed(1)
    : '—'

  /** 格式化角色/职务标签 */
  const formatRole = (item) => {
    if (item.character && item.job) return `${item.job} · ${item.character}`
    if (item.character) return item.character
    if (item.job) return item.job
    return ''
  }

  return (
    <>
      <PageHeader title="演员作品">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-400 hover:text-white
                     bg-surface-2 hover:bg-surface-3 rounded-lg transition-colors">
          <ArrowLeft size={16} /> 返回
        </button>
      </PageHeader>

      {/* 统计摘要 */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-surface-3 flex items-center justify-center flex-shrink-0">
            <User size={24} className="text-purple-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">
              演员 ID: {personId}
            </h2>
            <p className="text-sm text-gray-500">
              数据源: {credits?.source === 'douban' ? '豆瓣' : 'TMDB'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-brand-400">{credits?.total || 0}</div>
            <div className="text-xs text-gray-500 mt-1">总作品数</div>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">
              <span className="text-blue-400">{movieCount}</span>
              <span className="text-gray-600 mx-1">/</span>
              <span className="text-green-400">{tvCount}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">电影 / 剧集</div>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-amber-400">{avgRating}</div>
            <div className="text-xs text-gray-500 mt-1">平均评分</div>
          </div>
        </div>
      </div>

      {/* 筛选 & 排序 */}
      <div className="card mb-6 overflow-hidden">
        <div className="flex items-start gap-4 py-2.5 border-b border-white/[0.03]">
          <span className="text-xs text-gray-500 w-[72px] flex-shrink-0 pt-1 text-right">类型</span>
          <div className="flex flex-wrap gap-1.5 flex-1">
            {CREDIT_FILTERS.map(opt => (
              <button
                key={opt.key}
                onClick={() => setFilterType(opt.key)}
                className={`px-2.5 py-1 rounded text-xs transition-colors
                  ${filterType === opt.key
                    ? 'bg-brand-600 text-white font-medium'
                    : 'text-gray-400 hover:text-white hover:bg-surface-2'
                  }`}
              >
                {opt.label}
                {opt.key === 'movie' && ` (${movieCount})`}
                {opt.key === 'tv' && ` (${tvCount})`}
                {opt.key === '' && ` (${allItems.length})`}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-start gap-4 py-2.5">
          <span className="text-xs text-gray-500 w-[72px] flex-shrink-0 pt-1 text-right">排序</span>
          <div className="flex flex-wrap gap-1.5 flex-1">
            {CREDIT_SORTS.map(opt => (
              <button
                key={opt.key}
                onClick={() => setSortKey(opt.key)}
                className={`px-2.5 py-1 rounded text-xs transition-colors
                  ${sortKey === opt.key
                    ? 'bg-brand-600 text-white font-medium'
                    : 'text-gray-400 hover:text-white hover:bg-surface-2'
                  }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 作品网格 */}
      {sorted.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {sorted.map((item, idx) => {
            const roleText = formatRole(item)
            return (
              <div key={item.source_id || idx} className="relative">
                <MediaCard
                  item={item}
                  posterUrl={item.poster_url}
                  showType
                  tmdbMode
                  source={credits?.source || source || ''}
                />
                {roleText && (
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent
                                  px-3 py-2 pointer-events-none rounded-b-lg">
                    <span className="text-[10px] text-gray-300 line-clamp-1">
                      {roleText}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <EmptyState icon={Film} title="暂无作品" description="未找到该演员的参演作品" />
      )}
    </>
  )
}
