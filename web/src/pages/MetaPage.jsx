import { useState } from 'react'
import { Search, Copy, FolderOpen, ExternalLink } from 'lucide-react'
import { discoveryApi } from '../api/client'
import { PageSpinner, EmptyState, PageHeader, ErrorBanner } from '../components/UI'

export default function MetaPage() {
  const [query, setQuery] = useState('')
  const [mediaType, setMediaType] = useState('movie')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const doSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    discoveryApi.meta(query.trim(), mediaType)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  const copyText = (text) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const meta = data?.meta

  return (
    <>
      <PageHeader title="元数据查询" description="TMDB 影视信息 + 搜索关键词 + 保存路径建议" />

      <form onSubmit={doSearch} className="flex gap-3 mb-8">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="输入影视名称，如 '流浪地球2'..."
            className="input w-full pl-10"
            autoFocus
          />
        </div>
        <select
          value={mediaType}
          onChange={e => setMediaType(e.target.value)}
          className="input w-24 text-sm"
        >
          <option value="movie">电影</option>
          <option value="tv">剧集</option>
        </select>
        <button type="submit" className="btn-primary" disabled={loading}>查询</button>
      </form>

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

                <div className="flex flex-wrap gap-3 mt-4">
                  <span className="badge-yellow">★ {meta.rating} ({meta.vote_count} 票)</span>
                  <span className="badge-blue">{meta.year}</span>
                  {meta.runtime > 0 && <span className="badge-blue">{meta.runtime} 分钟</span>}
                  {meta.genres?.map((g, i) => <span key={i} className="badge-green">{g}</span>)}
                </div>

                <div className="flex gap-4 mt-3 text-xs text-gray-500">
                  <span>TMDB: {meta.tmdb_id}</span>
                  {meta.imdb_id && <span>IMDb: {meta.imdb_id}</span>}
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

          {/* Search keywords */}
          {data.search_keywords?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <Search size={18} /> 搜索关键词建议
              </h3>
              <div className="space-y-2">
                {data.search_keywords.map((kw, i) => (
                  <div key={i} className="flex items-center justify-between bg-surface-2 rounded-lg px-4 py-2.5">
                    <code className="text-sm text-brand-300">{kw}</code>
                    <button
                      onClick={() => copyText(kw)}
                      className="btn-ghost p-1.5 text-gray-500 hover:text-white"
                      title="复制"
                    >
                      <Copy size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Save paths */}
          {data.save_paths?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <FolderOpen size={18} /> 保存路径建议
              </h3>
              <div className="space-y-2">
                {data.save_paths.map((p, i) => (
                  <div key={i} className="flex items-center justify-between bg-surface-2 rounded-lg px-4 py-2.5">
                    <div>
                      <code className="text-sm text-emerald-300">{p.path}</code>
                      <span className="text-xs text-gray-500 ml-2">{p.description}</span>
                    </div>
                    <button
                      onClick={() => copyText(p.path)}
                      className="btn-ghost p-1.5 text-gray-500 hover:text-white"
                      title="复制"
                    >
                      <Copy size={14} />
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
                  <div key={i} className="flex items-center justify-between text-sm py-1.5">
                    <span className="text-gray-300">{r.title} ({r.year})</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-500">★ {r.rating}</span>
                      <span className="text-xs text-gray-600">TMDB:{r.tmdb_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={Search}
          title="查询影视元数据"
          description="输入影视名称，获取 TMDB 详情、搜索关键词建议和保存路径建议"
        />
      )}
    </>
  )
}
