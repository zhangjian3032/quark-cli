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

function put(path, data) {
  return request(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

function del_(path, data) {
  return request(path, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── Account (账号) ──
export const accountApi = {
  info:     ()  => request('/account/info'),
  verify:   ()  => request('/account/verify'),
  sign:     ()  => post('/account/sign', {}),
}

// ── Config (配置) ──
export const configApi = {
  read:         ()                        => request('/config'),
  setCookie:    (cookie, index = 0)       => put('/config/cookie', { cookie, index }),
  removeCookie: (index = 0)               => del_('/config/cookie', { index }),
  setFnos:      (data)                    => put('/config/fnos', data),
  setTmdb:      (data)                    => put('/config/tmdb', data),
  readBot:      ()                        => request('/config/bot'),
  setBot:       (data)                    => put('/config/bot', data),
  export:       ()                        => request('/config/export'),
  import:       (data)                    => post('/config/import', data),
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
  subdir:   (url, pdirFid)             => request(`/share/subdir?url=${encodeURIComponent(url)}&pdir_fid=${encodeURIComponent(pdirFid)}`),
  save:     (url, savePath, password, fidList, fidTokenList, renamePattern, renameReplace) =>
    post('/share/save', {
      url, save_path: savePath, password,
      fid_list: fidList, fid_token_list: fidTokenList,
      rename_pattern: renamePattern, rename_replace: renameReplace,
    }),
}

// ── Rename (正则重命名) ──
export const renameApi = {
  presets:  ()                          => request('/rename/presets'),
  preview:  (url, pattern, replace)     => post('/rename/preview', { url, pattern, replace }),
}

// ── Scheduler (定时任务) ──
export const schedulerApi = {
  status:   ()             => request('/scheduler/status'),
  tasks:    ()             => request('/scheduler/tasks'),
  create:   (task)         => post('/scheduler/tasks', task),
  update:   (index, task)  => put(`/scheduler/tasks/${index}`, task),
  remove:   (index)        => del_(`/scheduler/tasks/${index}`, {}),
  toggle:   (index)        => post(`/scheduler/tasks/${index}/toggle`, {}),
  trigger:  (index)        => post(`/scheduler/tasks/${index}/trigger`, {}),
  start:    ()             => post('/scheduler/start', {}),
  stop:     ()             => post('/scheduler/stop', {}),
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

// ── Discovery (TMDB / 豆瓣) ──
export const discoveryApi = {
  meta:    (q, type='movie', year=null, source=null) => {
    let url = `/discovery/meta?query=${encodeURIComponent(q)}&media_type=${type}`
    if (year) url += `&year=${year}`
    if (source) url += `&source=${encodeURIComponent(source)}`
    return request(url)
  },
  metaById: (id, type='movie', source=null) => {
    let url = `/discovery/meta/${id}?media_type=${type}`
    if (source) url += `&source=${encodeURIComponent(source)}`
    return request(url)
  },
  list:    (params = {})               => {
    const qs = new URLSearchParams({
      list_type: params.listType || 'top_rated',
      media_type: params.mediaType || 'movie',
      page: String(params.page || 1),
      ...(params.minRating != null ? { min_rating: String(params.minRating) } : {}),
      ...(params.genre ? { genre: params.genre } : {}),
      ...(params.year ? { year: String(params.year) } : {}),
      ...(params.country ? { country: params.country } : {}),
      ...(params.sortBy ? { sort_by: params.sortBy } : {}),
      ...(params.source ? { source: params.source } : {}),
      ...(params.tag ? { tag: params.tag } : {}),
    })
    return request(`/discovery/list?${qs}`)
  },
  genres:  (type='movie', source=null) => {
    let url = `/discovery/genres?media_type=${type}`
    if (source) url += `&source=${encodeURIComponent(source)}`
    return request(url)
  },
  tags:    (type='movie', source=null) => {
    let url = `/discovery/tags?media_type=${type}`
    if (source) url += `&source=${encodeURIComponent(source)}`
    return request(url)
  },
  sources: () => request('/discovery/sources'),
}

// ── Health ──
export const healthApi = {
  check: () => request('/health'),
}
