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

function post(path, data) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── Drive (网盘文件) ──
export const driveApi = {
  ls:       (path = '/')                => request(`/drive/ls?path=${encodeURIComponent(path)}`),
  mkdir:    (path)                      => post('/drive/mkdir', { path }),
  rename:   (fid, newName)              => post('/drive/rename', { fid, new_name: newName }),
  delete:   (fids)                      => post('/drive/delete', { fids }),
  download: (fid)                       => request(`/drive/download?fid=${encodeURIComponent(fid)}`),
  search:   (keyword, path = '/')       => request(`/drive/search?keyword=${encodeURIComponent(keyword)}&path=${encodeURIComponent(path)}`),
  space:    ()                          => request('/drive/space'),
}

// ── Search (资源搜索) ──
export const searchApi = {
  query:    (keyword, source = null)    => {
    let url = `/search/query?keyword=${encodeURIComponent(keyword)}`
    if (source) url += `&source=${encodeURIComponent(source)}`
    return request(url)
  },
  sources:  ()                          => request('/search/sources'),
}

// ── Share (分享链接) ──
export const shareApi = {
  check:    (url)                       => request(`/share/check?url=${encodeURIComponent(url)}`),
  list:     (url)                       => request(`/share/list?url=${encodeURIComponent(url)}`),
  save:     (url, savePath, password)   => post('/share/save', { url, save_path: savePath, password }),
}

// ── Media (影视) ──
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
