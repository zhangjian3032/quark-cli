const BASE = '/api'

async function request(path, opts = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, opts)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Media ──
export const mediaApi = {
  status:      ()                      => request('/media/status'),
  libraries:   ()                      => request('/media/libraries'),
  libraryItems:(id, page=1, size=20)   => request(`/media/libraries/${id}/items?page=${page}&page_size=${size}`),
  search:      (kw, page=1, size=20)   => request(`/media/search?keyword=${encodeURIComponent(kw)}&page=${page}&page_size=${size}`),
  detail:      (guid, seasons=false, cast=false) =>
    request(`/media/items/${guid}?seasons=${seasons}&cast=${cast}`),
  posterUrl:   (guid)                  => request(`/media/items/${guid}/poster`),
  playing:     ()                      => request('/media/playing'),
}

// ── Discovery (TMDB) ──
export const discoveryApi = {
  meta:    (q, type='movie', year=null) => {
    let url = `/discovery/meta?query=${encodeURIComponent(q)}&media_type=${type}`
    if (year) url += `&year=${year}`
    return request(url)
  },
  metaById: (id, type='movie')         => request(`/discovery/meta/${id}?media_type=${type}`),
  list:    (params = {})               => {
    const qs = new URLSearchParams({
      list_type: params.listType || 'top_rated',
      media_type: params.mediaType || 'movie',
      page: String(params.page || 1),
      ...(params.minRating != null ? { min_rating: String(params.minRating) } : {}),
      ...(params.genre ? { genre: params.genre } : {}),
      ...(params.year ? { year: String(params.year) } : {}),
      ...(params.country ? { country: params.country } : {}),
    })
    return request(`/discovery/list?${qs}`)
  },
  genres:  (type='movie')              => request(`/discovery/genres?media_type=${type}`),
}

// ── Health ──
export const healthApi = {
  check: () => request('/health'),
}
