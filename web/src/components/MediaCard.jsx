/**
 * 通用媒体卡片 — 用于媒体库、搜索结果、TMDB 发现
 *
 * Props:
 *   item         - 影片对象 (guid/tmdb_id, title, year, rating, media_type, genres, poster_url)
 *   posterUrl    - 海报图片 URL (优先于 item.poster_url)
 *   showType     - 是否显示 电影/剧集 标签
 *   tmdbMode     - true 时点击跳 /discover/:tmdb_id, false 跳 /detail/:guid
 */
import { useNavigate } from 'react-router-dom'
import { Star, Calendar, Film, Tv } from 'lucide-react'
import { useState } from 'react'

function PosterPlaceholder({ title }) {
  const initials = (title || '??').slice(0, 2)
  return (
    <div className="w-full h-full bg-gradient-to-br from-surface-3 to-surface-4
                    flex items-center justify-center">
      <span className="text-3xl font-bold text-gray-600">{initials}</span>
    </div>
  )
}

/** 格式化评分：保留 1 位小数 */
function formatRating(r) {
  if (r == null || r <= 0) return null
  return typeof r === 'number' ? r.toFixed(1) : String(r)
}

export default function MediaCard({ item, posterUrl, showType = false, tmdbMode = false }) {
  const navigate = useNavigate()
  const [imgError, setImgError] = useState(false)
  const ratingStr = formatRating(item.rating)

  const handleClick = () => {
    if (tmdbMode) {
      const type = item.media_type || 'movie'
      navigate(`/discover/${item.tmdb_id}?type=${type}`)
    } else {
      navigate(`/detail/${item.guid}`)
    }
  }

  return (
    <div
      className="card-hover cursor-pointer overflow-hidden group"
      onClick={handleClick}
    >
      {/* Poster */}
      <div className="aspect-[2/3] overflow-hidden relative">
        {posterUrl && !imgError ? (
          <img
            src={posterUrl}
            alt={item.title}
            className="w-full h-full object-cover transition-transform duration-300
                       group-hover:scale-105"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <PosterPlaceholder title={item.title} />
        )}
        {/* Rating badge */}
        {ratingStr && (
          <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1
                          bg-black/70 backdrop-blur-sm rounded-md text-xs">
            <Star size={12} className="text-amber-400 fill-amber-400" />
            <span className="text-amber-200 font-medium">{ratingStr}</span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="font-medium text-sm text-white truncate" title={item.title}>
          {item.title}
        </h3>
        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500">
          {item.year && (
            <span className="flex items-center gap-1">
              <Calendar size={11} />
              {item.year}
            </span>
          )}
          {showType && item.media_type && (
            <span className="flex items-center gap-1">
              {item.media_type === 'tv' ? <Tv size={11} /> : <Film size={11} />}
              {item.media_type === 'tv' ? '剧集' : '电影'}
            </span>
          )}
        </div>
        {item.genres && item.genres.length > 0 && (
          <div className="flex gap-1 mt-2 flex-wrap">
            {item.genres.slice(0, 3).map((g, i) => (
              <span key={i} className="badge-blue text-[10px]">{g}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
