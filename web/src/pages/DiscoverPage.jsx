import { useState, useEffect } from 'react'
import { Star, TrendingUp, Flame, SlidersHorizontal, RotateCcw, Shuffle, Database } from 'lucide-react'
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

const SOURCE_TYPES = [
  { key: 'tmdb',   label: 'TMDB' },
  { key: 'douban', label: '豆瓣' },
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

// 豆瓣排序
const DOUBAN_SORT_OPTIONS = [
  { key: 'recommend', label: '综合推荐' },
  { key: 'time',      label: '最新' },
  { key: 'rank',      label: '评分' },
]

/** 生成年份选项 */
function getYearOptions() {
  const current = new Date().getFullYear()
  const opts = [{ key: '', label: '全部' }]
  opts.push({ key: String(current), label: '今年' })
  for (let y = current - 1; y >= current - 5; y--) {
    opts.push({ key: String(y), label: String(y) })
  }
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
  const [source, setSource] = useState('tmdb')
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
  const [doubanTag, setDoubanTag] = useState('')

  // 类型列表 & 豆瓣标签列表
  const [genreOptions, setGenreOptions] = useState([])
  const [doubanTags, setDoubanTags] = useState([])
  const [availableSources, setAvailableSources] = useState([])

  // 初始加载可用数据源
  useEffect(() => {
    discoveryApi.sources()
      .then(d => {
        setAvailableSources(d.sources || [])
        // 如果 TMDB 不可用，自动切换到豆瓣
        const tmdbAvail = (d.sources || []).find(s => s.name === 'tmdb')
        if (!tmdbAvail || !tmdbAvail.available) {
          setSource('douban')
        }
      })
      .catch(() => {})
  }, [])

  // 加载类型
  useEffect(() => {
    discoveryApi.genres(mediaType, source)
      .then(list => setGenreOptions(list.map(g => ({ key: String(g.id), label: g.name }))))
      .catch(() => setGenreOptions([]))
  }, [mediaType, source])

  // 加载豆瓣标签
  useEffect(() => {
    if (source === 'douban') {
      discoveryApi.tags(mediaType, 'douban')
        .then(d => setDoubanTags(d.tags || []))
        .catch(() => setDoubanTags([]))
    } else {
      setDoubanTags([])
    }
  }, [source, mediaType])

  const isDouban = source === 'douban'

  const doFetch = (p = 1) => {
    setLoading(true)
    setError(null)
    setPage(p)

    // 随机模式
    if (listType === 'random') {
      const randomPage = Math.floor(Math.random() * 20) + 1
      const params = {
        listType: 'discover',
        mediaType,
        page: randomPage,
        source,
        sortBy: isDouban ? 'recommend' : 'popularity.desc',
      }
      if (minRating) params.minRating = parseFloat(minRating)
      if (genres.length > 0) params.genre = genres.join(',')
      if (country) params.country = country
      if (isDouban && doubanTag) params.tag = doubanTag
      if (year) {
        params.year = year.startsWith('decade_') ? parseInt(year.replace('decade_', '')) : parseInt(year)
      }
      discoveryApi.list(params)
        .then(d => { setData(d); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
      return
    }

    const params = { listType, mediaType, page: p, source }

    if (listType === 'discover') {
      if (minRating) params.minRating = parseFloat(minRating)
      if (genres.length > 0) params.genre = genres.join(',')
      if (country) params.country = country
      if (isDouban) {
        if (doubanTag) params.tag = doubanTag
        if (sortBy) params.sortBy = sortBy
      } else {
        if (sortBy) params.sortBy = sortBy
        if (year) {
          if (year.startsWith('decade_')) {
            params.year = parseInt(year.replace('decade_', ''))
          } else {
            params.year = parseInt(year)
          }
        }
      }
    }

    discoveryApi.list(params)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  // 非 discover 模式切换时自动刷新
  useEffect(() => {
    if (listType !== 'discover') {
      doFetch(1)
    }
  }, [listType, mediaType, source])

  // discover 模式: 初次进入时触发
  useEffect(() => {
    if (listType === 'discover') {
      doFetch(1)
    }
  }, [listType])

  const handleSourceChange = (s) => {
    setSource(s)
    setGenres([])
    setDoubanTag('')
    setCountry('')
    setYear('')
    setSortBy(s === 'douban' ? 'recommend' : 'vote_average.desc')
  }

  const handleReset = () => {
    setMinRating('')
    setGenres([])
    setCountry('')
    setYear('')
    setDoubanTag('')
    setSortBy(isDouban ? 'recommend' : 'vote_average.desc')
  }

  const hasFilters = minRating || genres.length > 0 || country || year || doubanTag
    || sortBy !== (isDouban ? 'recommend' : 'vote_average.desc')

  const sourceLabel = isDouban ? '豆瓣' : 'TMDB'

  return (
    <>
      <PageHeader
        title="影视发现"
        description={`${sourceLabel} 高分推荐与趋势`}
      />

      {/* ── 筛选面板 ── */}
      <div className="card mb-6 overflow-hidden">
        {/* 数据源 */}
        <TagRow
          label="数据源"
          options={SOURCE_TYPES.map(s => {
            const info = availableSources.find(a => a.name === s.key)
            const avail = !info || info.available
            return { key: s.key, label: avail ? s.label : `${s.label} (未配置)` }
          })}
          value={source}
          onChange={handleSourceChange}
        />

        {/* 影视类型 */}
        <TagRow
          label="影视类型"
          options={MEDIA_TYPES}
          value={mediaType}
          onChange={(v) => { setMediaType(v); setGenres([]); setDoubanTag('') }}
        />

        {/* 列表类型 */}
        <TagRow
          label="榜单"
          options={LIST_TYPES.map(t => ({ key: t.key, label: t.label }))}
          value={listType}
          onChange={setListType}
        />

        {/* ── discover / random 模式才显示以下筛选项 ── */}
        {(listType === 'discover' || listType === 'random') && (
          <>
            {/* 豆瓣标签 (仅豆瓣) */}
            {isDouban && doubanTags.length > 0 && (
              <TagRow
                label="标签"
                options={[{ key: '', label: '全部' }, ...doubanTags.map(t => ({ key: t, label: t }))]}
                value={doubanTag}
                onChange={setDoubanTag}
              />
            )}

            {/* 类型 (多选) */}
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

            {/* 国家地区 (TMDB 模式) */}
            {!isDouban && (
              <TagRow
                label="国家和地区"
                options={COUNTRY_OPTIONS}
                value={country}
                onChange={setCountry}
              />
            )}

            {/* 发行年份 (TMDB 模式) */}
            {!isDouban && (
              <TagRow
                label="发行年份"
                options={YEAR_OPTIONS}
                value={year}
                onChange={setYear}
              />
            )}

            {/* 排序 */}
            <TagRow
              label="排序"
              options={isDouban ? DOUBAN_SORT_OPTIONS : SORT_OPTIONS}
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
                key={item.source_id || item.tmdb_id || item.douban_id}
                item={item}
                posterUrl={item.poster_url}
                showType
                tmdbMode
                source={data.source || source}
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
