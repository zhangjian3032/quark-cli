import { useState, useEffect } from 'react'
import { Star, TrendingUp, Flame, SlidersHorizontal, RotateCcw, Shuffle } from 'lucide-react'
import { discoveryApi } from '../api/client'
import MediaCard from '../components/MediaCard'
import { PageSpinner, EmptyState, ErrorBanner, PageHeader, Pagination } from '../components/UI'

/* ═══════════════════════════════════════════
   筛选维度配置
   ═══════════════════════════════════════════ */
const LIST_TYPES = [
  { key: 'top_rated', label: '高分', icon: Star },
  { key: 'popular',   label: '热门', icon: Flame },
  { key: 'trending',  label: '趋势', icon: TrendingUp },
  { key: 'discover',  label: '筛选', icon: SlidersHorizontal },
  { key: 'random',    label: '随机', icon: Shuffle },
]

const MEDIA_TYPES = [
  { key: 'movie', label: '电影' },
  { key: 'tv',    label: '电视剧' },
]

const RATING_OPTIONS = [
  { key: '',  label: '全部' },
  { key: '9', label: '9分以上' },
  { key: '8', label: '8分以上' },
  { key: '7', label: '7分以上' },
  { key: '6', label: '6分以上' },
]

const COUNTRY_OPTIONS = [
  { key: '',   label: '全部' },
  { key: 'US', label: '美国' },
  { key: 'CN', label: '中国大陆' },
  { key: 'HK', label: '中国香港' },
  { key: 'TW', label: '中国台湾' },
  { key: 'JP', label: '日本' },
  { key: 'KR', label: '韩国' },
  { key: 'GB', label: '英国' },
  { key: 'FR', label: '法国' },
  { key: 'DE', label: '德国' },
  { key: 'IN', label: '印度' },
  { key: 'TH', label: '泰国' },
  { key: 'IT', label: '意大利' },
  { key: 'ES', label: '西班牙' },
  { key: 'CA', label: '加拿大' },
  { key: 'AU', label: '澳大利亚' },
  { key: 'RU', label: '俄罗斯' },
  { key: 'BR', label: '巴西' },
  { key: 'SE', label: '瑞典' },
  { key: 'DK', label: '丹麦' },
  { key: 'NO', label: '挪威' },
]

const SORT_OPTIONS = [
  { key: 'vote_average.desc', label: '评分最高' },
  { key: 'popularity.desc',   label: '最受欢迎' },
  { key: 'primary_release_date.desc', label: '最新上映' },
  { key: 'revenue.desc',      label: '票房最高' },
]

/** 生成年份选项 */
function getYearOptions() {
  const current = new Date().getFullYear()
  const opts = [{ key: '', label: '全部' }]
  // 今年
  opts.push({ key: String(current), label: '今年' })
  // 最近几年
  for (let y = current - 1; y >= current - 5; y--) {
    opts.push({ key: String(y), label: String(y) })
  }
  // 年代
  opts.push({ key: 'decade_2010', label: '2010年代' })
  opts.push({ key: 'decade_2000', label: '2000年代' })
  opts.push({ key: 'decade_1990', label: '1990年代' })
  opts.push({ key: 'decade_1980', label: '1980年代' })
  return opts
}

const YEAR_OPTIONS = getYearOptions()

/* ═══════════════════════════════════════════
   TagRow 标签行组件
   ═══════════════════════════════════════════ */
function TagRow({ label, options, value, onChange, multi = false }) {
  const isSelected = (key) => {
    if (multi) return value.includes(key)
    return value === key
  }

  const handleClick = (key) => {
    if (multi) {
      if (key === '') {
        onChange([])
      } else {
        const next = value.includes(key) ? value.filter(k => k !== key) : [...value, key]
        onChange(next)
      }
    } else {
      onChange(key)
    }
  }

  return (
    <div className="flex items-start gap-4 py-2.5 border-b border-white/[0.03] last:border-b-0">
      <span className="text-xs text-gray-500 w-[72px] flex-shrink-0 pt-1 text-right">{label}</span>
      <div className="flex flex-wrap gap-1.5 flex-1">
        {multi && (
          <button
            onClick={() => onChange([])}
            className={`px-2.5 py-1 rounded text-xs transition-colors
              ${value.length === 0
                ? 'bg-brand-600 text-white font-medium'
                : 'text-gray-400 hover:text-white hover:bg-surface-2'
              }`}
          >
            全部
          </button>
        )}
        {options.map(opt => (
          <button
            key={opt.key}
            onClick={() => handleClick(opt.key)}
            className={`px-2.5 py-1 rounded text-xs transition-colors
              ${isSelected(opt.key)
                ? 'bg-brand-600 text-white font-medium'
                : 'text-gray-400 hover:text-white hover:bg-surface-2'
              }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════
   主页面
   ═══════════════════════════════════════════ */
export default function DiscoverPage() {
  const [listType, setListType] = useState('top_rated')
  const [mediaType, setMediaType] = useState('movie')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 筛选参数
  const [minRating, setMinRating] = useState('')
  const [genres, setGenres] = useState([])
  const [country, setCountry] = useState('')
  const [year, setYear] = useState('')
  const [sortBy, setSortBy] = useState('vote_average.desc')

  // 类型列表
  const [genreOptions, setGenreOptions] = useState([])

  // 加载类型
  useEffect(() => {
    discoveryApi.genres(mediaType)
      .then(list => setGenreOptions(list.map(g => ({ key: String(g.id), label: g.name }))))
      .catch(() => {})
  }, [mediaType])

  const doFetch = (p = 1) => {
    setLoading(true)
    setError(null)
    setPage(p)

    // 随机模式: 用 discover 接口 + 随机页码 + popularity 排序
    if (listType === 'random') {
      const randomPage = Math.floor(Math.random() * 20) + 1
      const params = {
        listType: 'discover',
        mediaType,
        page: randomPage,
        sortBy: 'popularity.desc',
      }
      // 应用筛选条件 (如果有的话)
      if (minRating) params.minRating = parseFloat(minRating)
      if (genres.length > 0) params.genre = genres.join(',')
      if (country) params.country = country
      if (year) {
        params.year = year.startsWith('decade_') ? parseInt(year.replace('decade_', '')) : parseInt(year)
      }
      discoveryApi.list(params)
        .then(d => { setData(d); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
      return
    }

    const params = { listType, mediaType, page: p }

    if (listType === 'discover') {
      if (minRating) params.minRating = parseFloat(minRating)
      if (genres.length > 0) params.genre = genres.join(',')
      if (country) params.country = country
      if (sortBy) params.sortBy = sortBy

      // 年份 / 年代
      if (year) {
        if (year.startsWith('decade_')) {
          const decade = parseInt(year.replace('decade_', ''))
          params.year = decade
        } else {
          params.year = parseInt(year)
        }
      }
    }

    discoveryApi.list(params)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  // 非 discover 模式切换时自动刷新 (包括 random)
  useEffect(() => {
    if (listType !== 'discover') {
      doFetch(1)
    }
  }, [listType, mediaType])

  // discover 模式: 初次进入时触发一次
  useEffect(() => {
    if (listType === 'discover') {
      doFetch(1)
    }
  }, [listType])

  const handleReset = () => {
    setMinRating('')
    setGenres([])
    setCountry('')
    setYear('')
    setSortBy('vote_average.desc')
  }

  const hasFilters = minRating || genres.length > 0 || country || year || sortBy !== 'vote_average.desc'

  return (
    <>
      <PageHeader title="影视发现" description="TMDB 高分推荐与趋势" />

      {/* ── 筛选面板 ── */}
      <div className="card mb-6 overflow-hidden">
        {/* 影视类型 */}
        <TagRow
          label="影视类型"
          options={MEDIA_TYPES}
          value={mediaType}
          onChange={(v) => { setMediaType(v); setGenres([]) }}
        />

        {/* 列表类型 */}
        <TagRow
          label="榜单"
          options={LIST_TYPES.map(t => ({ key: t.key, label: t.label }))}
          value={listType}
          onChange={setListType}
        />

        {/* ── discover 模式才显示以下筛选项 ── */}
        {(listType === 'discover' || listType === 'random') && (
          <>
            {/* 类型 */}
            {genreOptions.length > 0 && (
              <TagRow
                label="类型"
                options={genreOptions}
                value={genres}
                onChange={setGenres}
                multi
              />
            )}

            {/* 评分 */}
            <TagRow
              label="评分"
              options={RATING_OPTIONS}
              value={minRating}
              onChange={setMinRating}
            />

            {/* 国家地区 */}
            <TagRow
              label="国家和地区"
              options={COUNTRY_OPTIONS}
              value={country}
              onChange={setCountry}
            />

            {/* 发行年份 */}
            <TagRow
              label="发行年份"
              options={YEAR_OPTIONS}
              value={year}
              onChange={setYear}
            />

            {/* 排序 */}
            <TagRow
              label="排序"
              options={SORT_OPTIONS}
              value={sortBy}
              onChange={setSortBy}
            />

            {/* 操作按钮 */}
            <div className="flex items-center gap-3 px-4 py-3 border-t border-white/5">
              {listType === 'random' ? (
                <button onClick={() => doFetch(1)}
                  className="btn-primary text-sm flex items-center gap-1.5">
                  <Shuffle size={14} /> 换一批
                </button>
              ) : (
                <button onClick={() => doFetch(1)} className="btn-primary text-sm">
                  筛选
                </button>
              )}
              {hasFilters && (
                <button onClick={handleReset}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors">
                  <RotateCcw size={12} /> 重置
                </button>
              )}
            </div>
          </>
        )}
      </div>

      {error && <ErrorBanner message={error} onRetry={() => doFetch(page)} />}

      {loading ? (
        <PageSpinner />
      ) : data?.items?.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {data.items.map(item => (
              <MediaCard
                key={item.tmdb_id}
                item={{ ...item, guid: item.tmdb_id }}
                posterUrl={item.poster_url}
                showType
                tmdbMode
              />
            ))}
          </div>
          {listType === 'random' ? (
            <div className="flex justify-center mt-8">
              <button onClick={() => doFetch(1)}
                className="btn-primary flex items-center gap-2">
                <Shuffle size={16} /> 换一批
              </button>
            </div>
          ) : (
            <Pagination page={data.page} totalPages={data.total_pages} onChange={p => doFetch(p)} />
          )}
        </>
      ) : (
        <EmptyState icon={Star} title="暂无结果" description="换个条件试试" />
      )}
    </>
  )
}
