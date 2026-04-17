import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Star, Calendar, Clock, Users, Film } from 'lucide-react'
import { mediaApi } from '../api/client'
import { PageSpinner, ErrorBanner } from '../components/UI'

/** 格式化评分：保留 1 位小数 */
function formatRating(r) {
  if (r == null || r <= 0) return null
  return typeof r === 'number' ? r.toFixed(1) : String(r)
}

export default function DetailPage() {
  const { guid } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [poster, setPoster] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      mediaApi.detail(guid, true, true),
      mediaApi.posterUrl(guid).catch(() => null),
    ])
      .then(([d, p]) => {
        setDetail(d)
        setPoster(p)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [guid])

  if (loading) return <PageSpinner />
  if (error) return <ErrorBanner message={error} />
  if (!detail) return null

  const ratingStr = formatRating(detail.rating)

  // poster_url 优先来自 detail 本身（已内联），fallback 到单独 poster 接口
  const posterSrc = detail.poster_url || poster?.poster_url || ''
  const backdropSrc = poster?.backdrop_url || ''

  return (
    <>
      <button
        onClick={() => navigate(-1)}
        className="btn-ghost mb-4 -ml-2 flex items-center gap-2 text-sm"
      >
        <ArrowLeft size={16} /> 返回
      </button>

      {/* Hero */}
      <div className="card overflow-hidden">
        <div className="relative">
          {/* Backdrop */}
          {backdropSrc && (
            <div className="h-[300px] overflow-hidden">
              <img
                src={backdropSrc}
                alt=""
                className="w-full h-full object-cover opacity-40"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-1 via-surface-1/60 to-transparent" />
            </div>
          )}

          {/* Content overlay */}
          <div className={`${backdropSrc ? 'absolute bottom-0 left-0 right-0' : ''} p-6 flex gap-6`}>
            {/* Poster */}
            {posterSrc && (
              <img
                src={posterSrc}
                alt={detail.title}
                className="w-[180px] rounded-lg shadow-2xl flex-shrink-0 hidden sm:block"
              />
            )}

            {/* Info */}
            <div className="flex-1 min-w-0">
              <h1 className="text-3xl font-bold text-white">{detail.title}</h1>
              {detail.original_title && detail.original_title !== detail.title && (
                <p className="text-lg text-gray-400 mt-1">{detail.original_title}</p>
              )}

              <div className="flex flex-wrap items-center gap-4 mt-4">
                {ratingStr && (
                  <div className="flex items-center gap-1.5">
                    <Star size={18} className="text-amber-400 fill-amber-400" />
                    <span className="text-lg font-semibold text-amber-200">{ratingStr}</span>
                  </div>
                )}
                {detail.year && (
                  <span className="flex items-center gap-1.5 text-gray-400">
                    <Calendar size={16} /> {detail.year}
                  </span>
                )}
                {detail.media_type && (
                  <span className="flex items-center gap-1.5 text-gray-400">
                    <Film size={16} /> {detail.media_type === 'tv' ? '剧集' : '电影'}
                  </span>
                )}
              </div>

              {detail.overview && (
                <p className="text-sm text-gray-400 mt-4 leading-relaxed line-clamp-4">
                  {detail.overview}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Seasons */}
      {detail.seasons?.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Film size={20} /> 季列表
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {detail.seasons.map(s => (
              <div key={s.guid} className="card p-4">
                <div className="text-sm font-medium text-white">
                  {s.title || `第 ${s.season_number} 季`}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {s.episode_count ? `${s.episode_count} 集` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cast */}
      {detail.cast?.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Users size={20} /> 演职人员
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {detail.cast.map((p, i) => (
              <div key={i} className="card p-3 text-center">
                <div className="w-12 h-12 rounded-full bg-surface-3 mx-auto mb-2
                                flex items-center justify-center text-lg text-gray-500">
                  {(p.name || '?')[0]}
                </div>
                <div className="text-sm text-white truncate">{p.name}</div>
                <div className="text-[10px] text-gray-500 truncate mt-0.5">{p.role}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
