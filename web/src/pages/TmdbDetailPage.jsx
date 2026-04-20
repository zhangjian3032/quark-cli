/**
 * 影片详情页 — 从「发现」跳入 (支持 TMDB / 豆瓣)
 * 路由: /discover/:id?type=movie&source=tmdb
 */
import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import {
  Star, Calendar, Clock, Film, Tv, Users, FolderOpen,
  Search, Copy, Download, ArrowLeft, ArrowRight, ExternalLink, Tag,
  CheckCircle2, Sparkles, Zap,
} from 'lucide-react'
import { discoveryApi } from '../api/client'
import { PageSpinner, ErrorBanner, PageHeader } from '../components/UI'
import { proxyImageUrl } from '../utils/image'

function copyText(t) { navigator.clipboard.writeText(t).catch(() => {}) }

export default function TmdbDetailPage() {
  const { tmdbId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const mediaType = searchParams.get('type') || 'movie'
  const source = searchParams.get('source') || null

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    discoveryApi.metaById(tmdbId, mediaType, source)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [tmdbId, mediaType, source])

  /** 跳转到搜索转存页 */
  const goSearch = (keyword, savePath) => {
    const params = new URLSearchParams({ keyword })
    if (savePath) params.set('path', savePath)
    navigate(`/resource-search?${params.toString()}`)
  }

  if (loading) return <PageSpinner />
  if (error) return <ErrorBanner message={error} />
  if (!data?.meta) return <ErrorBanner message="未找到影片信息" />

  const m = data.meta
  const keywords = data.search_keywords || []
  const paths = data.save_paths || []
  const defaultPath = paths[0]?.path || ''
  const isDouban = (data.source || source) === 'douban'
  const sourceId = m.source_id || m.tmdb_id || m.douban_id || tmdbId

  return (
    <>
      <PageHeader title="影片详情">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-400 hover:text-white
                     bg-surface-2 hover:bg-surface-3 rounded-lg transition-colors">
          <ArrowLeft size={16} /> 返回
        </button>
      </PageHeader>

      {/* Hero card */}
      <div className="card overflow-hidden mb-6">
        <div className="relative">
          {/* Backdrop */}
          {m.backdrop_url && (
            <div className="h-[200px] overflow-hidden">
              <img src={proxyImageUrl(m.backdrop_url)} alt=""
                className="w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-1 via-surface-1/80 to-transparent" />
            </div>
          )}

          <div className={`flex gap-6 p-6 ${m.backdrop_url ? '-mt-24 relative z-10' : ''}`}>
            {/* Poster */}
            {m.poster_url ? (
              <img src={proxyImageUrl(m.poster_url)} alt=""
                className="w-[160px] rounded-lg shadow-2xl flex-shrink-0 border border-white/10" />
            ) : (
              <div className="w-[160px] aspect-[2/3] rounded-lg bg-surface-3 flex items-center justify-center flex-shrink-0">
                <Film size={48} className="text-gray-600" />
              </div>
            )}

            <div className="flex-1 min-w-0">
              <h2 className="text-2xl font-bold text-white">{m.title}</h2>
              {m.original_title && m.original_title !== m.title && (
                <p className="text-gray-400 mt-1">{m.original_title}</p>
              )}
              {m.tagline && <p className="text-gray-500 italic mt-1">"{m.tagline}"</p>}

              <div className="flex flex-wrap gap-2 mt-4">
                {m.rating > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium
                                   bg-amber-500/15 text-amber-400 border border-amber-500/20">
                    <Star size={12} className="fill-amber-400" /> {m.rating} {m.vote_count ? `(${m.vote_count})` : ''}
                  </span>
                )}
                {m.year && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                   bg-blue-500/15 text-blue-400 border border-blue-500/20">
                    <Calendar size={12} /> {m.year}
                  </span>
                )}
                {m.runtime > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                   bg-blue-500/15 text-blue-400 border border-blue-500/20">
                    <Clock size={12} /> {m.runtime} 分钟
                  </span>
                )}
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                 bg-purple-500/15 text-purple-400 border border-purple-500/20">
                  {data.media_type === 'tv' ? <Tv size={12} /> : <Film size={12} />}
                  {data.media_type === 'tv' ? '剧集' : '电影'}
                </span>
                {m.genres?.map((g, i) => (
                  <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                           bg-green-500/15 text-green-400 border border-green-500/20">
                    <Tag size={10} /> {g}
                  </span>
                ))}
              </div>

              <div className="flex gap-4 mt-3 text-xs text-gray-500 flex-wrap">
                {/* 来源标识 */}
                {isDouban ? (
                  <>
                    <span className="text-green-500">豆瓣: {sourceId}</span>
                    {m.extra?.douban_url && (
                      <a href={m.extra.douban_url} target="_blank" rel="noreferrer"
                        className="hover:text-gray-300 flex items-center gap-1">
                        豆瓣页面 <ExternalLink size={10} />
                      </a>
                    )}
                  </>
                ) : (
                  <>
                    <span>TMDB: {m.tmdb_id || sourceId}</span>
                    {m.imdb_id && (
                      <a href={`https://www.imdb.com/title/${m.imdb_id}/`} target="_blank" rel="noreferrer"
                        className="hover:text-gray-300 flex items-center gap-1">
                        IMDb: {m.imdb_id} <ExternalLink size={10} />
                      </a>
                    )}
                  </>
                )}
                {m.status && <span>状态: {m.status}</span>}
              </div>

              {m.directors?.length > 0 && (
                <p className="text-sm text-gray-400 mt-3">
                  <span className="text-gray-500">导演:</span> {m.directors.join(' / ')}
                </p>
              )}
              {m.cast?.length > 0 && (
                <p className="text-sm text-gray-400 mt-1">
                  <span className="text-gray-500">主演:</span> {m.cast.join(' / ')}
                </p>
              )}

              {m.overview && (
                <p className="text-sm text-gray-400 mt-3 leading-relaxed">{m.overview}</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── 搜索转存快捷操作 ── */}
      <div className="card p-5 mb-6 border-brand-500/20 border">
        <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
          <Zap size={18} className="text-brand-400" /> 搜索转存
        </h3>

        {/* 推荐路径 */}
        {paths.length > 0 && (
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2">推荐保存路径</div>
            <div className="space-y-1.5">
              {paths.map((p, i) => (
                <div key={i} className="flex items-center gap-2 bg-surface-2 rounded-lg px-3 py-2">
                  <FolderOpen size={14} className="text-green-400 flex-shrink-0" />
                  <code className="text-sm text-green-300 truncate flex-1">{p.path}</code>
                  <span className="text-[10px] text-gray-600 flex-shrink-0">{p.description}</span>
                  <button onClick={() => copyText(p.path)} className="p-1 text-gray-600 hover:text-white" title="复制">
                    <Copy size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 搜索关键词 */}
        <div className="text-xs text-gray-500 mb-2">点击关键词跳转到搜索转存</div>
        <div className="space-y-1.5">
          {keywords.map((kw, i) => (
            <button key={i} onClick={() => goSearch(kw, defaultPath)}
              className="w-full flex items-center gap-3 bg-surface-2 hover:bg-surface-3
                         rounded-lg px-3 py-2.5 transition-colors text-left group">
              <Search size={14} className="text-brand-400 flex-shrink-0" />
              <code className="text-sm text-brand-300 flex-1">{kw}</code>
              <span className="flex items-center gap-1 text-[10px] text-gray-600
                               group-hover:text-brand-400 transition-colors">
                搜索转存 <ArrowRight size={10} />
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* ── 其他匹配 ── */}
      {data.other_results?.length > 0 && (
        <div className="card p-5">
          <h3 className="font-semibold text-white mb-3">其他匹配</h3>
          <div className="space-y-1">
            {data.other_results.map((r, i) => {
              const rid = r.source_id || r.tmdb_id || r.douban_id
              return (
                <button key={i}
                  onClick={() => {
                    let url = `/discover/${rid}?type=${data.media_type}`
                    if (data.source) url += `&source=${data.source}`
                    navigate(url)
                  }}
                  className="w-full flex items-center justify-between text-sm py-2 px-2
                             rounded hover:bg-surface-2 transition-colors text-left">
                  <span className="text-gray-300">{r.title} ({r.year})</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-amber-400">★ {r.rating}</span>
                    <ArrowRight size={12} className="text-gray-600" />
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </>
  )
}
