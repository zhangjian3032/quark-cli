import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, Copy, FolderOpen, ExternalLink, ArrowRight,
  Star, Calendar, Clock, Film, Tv, Tag, Zap, Download,
} from 'lucide-react'
import { discoveryApi } from '../api/client'
import SearchInputWithHistory from '../components/SearchInputWithHistory'
import { PageSpinner, EmptyState, PageHeader, ErrorBanner } from '../components/UI'

export default function MetaPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [mediaType, setMediaType] = useState('movie')
  const [source, setSource] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const doSearch = (q) => {
    const keyword = (q ?? query).trim()
    if (!keyword) return
    setQuery(keyword)
    setLoading(true)
    setError(null)
    discoveryApi.meta(keyword, mediaType, null, source || null)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  const copyText = (text) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  /** 跳转到搜索转存页 */
  const goSearch = (keyword, savePath) => {
    const params = new URLSearchParams({ keyword })
    if (savePath) params.set('path', savePath)
    navigate(`/resource-search?${params.toString()}`)
  }

  const meta = data?.meta
  const keywords = data?.search_keywords || []
  const paths = data?.save_paths || []
  const defaultPath = paths[0]?.path || ''

  return (
    <>
      <PageHeader title="元数据查询" description="TMDB/豆瓣 影视信息 + 搜索关键词 + 保存路径建议" />

      <div className="flex gap-3 mb-8 items-start">
        <SearchInputWithHistory
          value={query}
          onChange={setQuery}
          onSearch={doSearch}
          placeholder="输入影视名称，如 '流浪地球2'..."
          historyNs="meta_search"
        />
        <select
          value={mediaType}
          onChange={e => setMediaType(e.target.value)}
          className="input w-24 text-sm flex-shrink-0"
        >
          <option value="movie">电影</option>
          <option value="tv">剧集</option>
        </select>
        <select
          value={source}
          onChange={e => setSource(e.target.value)}
          className="input w-20 text-sm flex-shrink-0"
        >
          <option value="">自动</option>
          <option value="tmdb">TMDB</option>
          <option value="douban">豆瓣</option>
        </select>
      </div>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <PageSpinner />
      ) : meta ? (
        <div className="space-y-6">
          {/* Hero card */}
          <div className="card overflow-hidden">
            <div className="flex gap-6 p-6">
              {meta.poster_url && (
                <img src={meta.poster_url} alt="" className="w-[160px] rounded-lg shadow-xl flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <h2 className="text-2xl font-bold text-white">{meta.title}</h2>
                {meta.original_title && meta.original_title !== meta.title && (
                  <p className="text-gray-400 mt-1">{meta.original_title}</p>
                )}
                {meta.tagline && <p className="text-gray-500 italic mt-1">"{meta.tagline}"</p>}

                <div className="flex flex-wrap gap-2 mt-4">
                  {meta.rating > 0 && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium
                                     bg-amber-500/15 text-amber-400 border border-amber-500/20">
                      <Star size={12} className="fill-amber-400" /> {meta.rating} ({meta.vote_count})
                    </span>
                  )}
                  {meta.year && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                     bg-blue-500/15 text-blue-400 border border-blue-500/20">
                      <Calendar size={12} /> {meta.year}
                    </span>
                  )}
                  {meta.runtime > 0 && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                     bg-blue-500/15 text-blue-400 border border-blue-500/20">
                      <Clock size={12} /> {meta.runtime} 分钟
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                   bg-purple-500/15 text-purple-400 border border-purple-500/20">
                    {data.media_type === 'tv' ? <Tv size={12} /> : <Film size={12} />}
                    {data.media_type === 'tv' ? '剧集' : '电影'}
                  </span>
                  {meta.genres?.map((g, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                                             bg-green-500/15 text-green-400 border border-green-500/20">
                      <Tag size={10} /> {g}
                    </span>
                  ))}
                </div>

                <div className="flex gap-4 mt-3 text-xs text-gray-500 flex-wrap">
                  {data.source === 'douban' ? (
                    <>
                      <span className="text-green-500">豆瓣: {meta.source_id || meta.douban_id}</span>
                      {meta.extra?.douban_url && (
                        <a href={meta.extra.douban_url} target="_blank" rel="noreferrer"
                          className="hover:text-gray-300 flex items-center gap-1">
                          豆瓣页面 <ExternalLink size={10} />
                        </a>
                      )}
                    </>
                  ) : (
                    <>
                      <span>TMDB: {meta.tmdb_id || meta.source_id}</span>
                      {meta.imdb_id && (
                        <a href={`https://www.imdb.com/title/${meta.imdb_id}/`} target="_blank" rel="noreferrer"
                          className="hover:text-gray-300 flex items-center gap-1">
                          IMDb: {meta.imdb_id} <ExternalLink size={10} />
                        </a>
                      )}
                    </>
                  )}
                  {meta.status && <span>状态: {meta.status}</span>}
                </div>

                {/* Directors & Cast */}
                {meta.directors?.length > 0 && (
                  <p className="text-sm text-gray-400 mt-3">
                    <span className="text-gray-500">导演:</span> {meta.directors.join(' / ')}
                  </p>
                )}
                {meta.cast?.length > 0 && (
                  <p className="text-sm text-gray-400 mt-1">
                    <span className="text-gray-500">主演:</span> {meta.cast.join(' / ')}
                  </p>
                )}

                {meta.overview && (
                  <p className="text-sm text-gray-400 mt-3 leading-relaxed line-clamp-3">{meta.overview}</p>
                )}
              </div>
            </div>
          </div>

          {/* Search keywords — with search+save jump */}
          {keywords.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <Search size={18} /> 搜索关键词建议
              </h3>
              <div className="space-y-2">
                {keywords.map((kw, i) => (
                  <div key={i} className="flex items-center gap-2 bg-surface-2 rounded-lg px-4 py-2.5">
                    <code className="text-sm text-brand-300 flex-1">{kw}</code>
                    <button
                      onClick={() => copyText(kw)}
                      className="btn-ghost p-1.5 text-gray-500 hover:text-white"
                      title="复制"
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      onClick={() => goSearch(kw, defaultPath)}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium
                                 bg-brand-600/20 text-brand-400 hover:bg-brand-600/30 transition-colors"
                      title="跳转搜索转存"
                    >
                      <Download size={12} /> 搜索转存
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Save paths */}
          {paths.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <FolderOpen size={18} /> 保存路径建议
              </h3>
              <div className="space-y-2">
                {paths.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 bg-surface-2 rounded-lg px-4 py-2.5">
                    <FolderOpen size={14} className="text-green-400 flex-shrink-0" />
                    <code className="text-sm text-emerald-300 truncate flex-1">{p.path}</code>
                    <span className="text-xs text-gray-500 flex-shrink-0">{p.description}</span>
                    <button
                      onClick={() => copyText(p.path)}
                      className="btn-ghost p-1.5 text-gray-500 hover:text-white"
                      title="复制"
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      onClick={() => goSearch(keywords[0] || query, p.path)}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium
                                 bg-green-600/20 text-green-400 hover:bg-green-600/30 transition-colors"
                      title="使用此路径搜索转存"
                    >
                      <Zap size={12} /> 转存到此
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Other results */}
          {data.other_results?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-white mb-3">其他匹配</h3>
              <div className="space-y-1">
                {data.other_results.map((r, i) => (
                  <button key={i}
                    onClick={() => {
                      const rid = r.source_id || r.tmdb_id || r.douban_id
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
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={Search}
          title="查询影视元数据"
          description="输入影视名称，获取详情、搜索关键词建议和保存路径建议"
        />
      )}
    </>
  )
}
