/**
 * 演员卡片组件 — 用于演员搜索结果展示
 *
 * Props:
 *   person  - 演员对象 (person_id, name, original_name, profile_url, known_for_department, known_for, popularity)
 *   source  - 数据源 "tmdb" | "douban"
 */
import { useNavigate } from 'react-router-dom'
import { User, Film, Tv, Star } from 'lucide-react'
import { useState } from 'react'
import { proxyImageUrl } from '../utils/image'

function ProfilePlaceholder({ name }) {
  const initials = (name || '??').slice(0, 1)
  return (
    <div className="w-full h-full bg-gradient-to-br from-surface-3 to-surface-4
                    flex items-center justify-center">
      <User size={48} className="text-gray-600" />
    </div>
  )
}

export default function PersonCard({ person, source = '' }) {
  const navigate = useNavigate()
  const [imgError, setImgError] = useState(false)

  const handleClick = () => {
    let url = `/discover/person/${person.person_id}`
    if (source) url += `?source=${source}`
    navigate(url)
  }

  const deptLabel = {
    Acting: '演员',
    Directing: '导演',
    Writing: '编剧',
    Production: '制片',
  }

  // 通过代理处理防盗链图片
  const imgSrc = proxyImageUrl(person.profile_url)

  return (
    <div
      className="card-hover cursor-pointer overflow-hidden group"
      onClick={handleClick}
    >
      {/* Profile photo */}
      <div className="aspect-[2/3] overflow-hidden relative">
        {imgSrc && !imgError ? (
          <img
            src={imgSrc}
            alt={person.name}
            className="w-full h-full object-cover transition-transform duration-300
                       group-hover:scale-105"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <ProfilePlaceholder name={person.name} />
        )}
        {/* Department badge */}
        {person.known_for_department && (
          <div className="absolute top-2 right-2 px-2 py-1
                          bg-black/70 backdrop-blur-sm rounded-md text-xs text-purple-300 font-medium">
            {deptLabel[person.known_for_department] || person.known_for_department}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="font-medium text-sm text-white truncate" title={person.name}>
          {person.name}
        </h3>
        {person.original_name && person.original_name !== person.name && (
          <p className="text-xs text-gray-500 truncate mt-0.5" title={person.original_name}>
            {person.original_name}
          </p>
        )}

        {/* Known for works */}
        {person.known_for?.length > 0 && (
          <div className="mt-2 space-y-1">
            <div className="text-[10px] text-gray-600 uppercase tracking-wide">代表作</div>
            {person.known_for.slice(0, 2).map((work, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-gray-400">
                {work.media_type === 'tv' ? <Tv size={10} className="flex-shrink-0" /> : <Film size={10} className="flex-shrink-0" />}
                <span className="truncate">{work.title}</span>
                {work.rating > 0 && (
                  <span className="flex items-center gap-0.5 text-amber-400 flex-shrink-0 ml-auto">
                    <Star size={8} className="fill-amber-400" />{work.rating.toFixed(1)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
