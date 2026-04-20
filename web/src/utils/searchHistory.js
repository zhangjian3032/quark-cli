/**
 * 搜索历史工具 — 使用 localStorage 持久化最近搜索记录
 *
 * 按 namespace 隔离不同搜索框的历史, 每个命名空间最多保留 10 条。
 */

const MAX_ITEMS = 10
const STORAGE_PREFIX = 'quark_search_history_'

/**
 * 获取搜索历史
 * @param {string} ns - 命名空间, 如 'person', 'meta', 'resource'
 * @returns {string[]}
 */
export function getSearchHistory(ns) {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + ns)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/**
 * 添加一条搜索记录 (自动去重 + 限制条数)
 * @param {string} ns
 * @param {string} query
 */
export function addSearchHistory(ns, query) {
  if (!query || !query.trim()) return
  const trimmed = query.trim()
  try {
    let list = getSearchHistory(ns)
    // 去重: 如果已存在则移到最前
    list = list.filter(item => item !== trimmed)
    list.unshift(trimmed)
    if (list.length > MAX_ITEMS) list = list.slice(0, MAX_ITEMS)
    localStorage.setItem(STORAGE_PREFIX + ns, JSON.stringify(list))
  } catch {
    // ignore
  }
}

/**
 * 删除单条搜索记录
 * @param {string} ns
 * @param {string} query
 */
export function removeSearchHistory(ns, query) {
  try {
    let list = getSearchHistory(ns)
    list = list.filter(item => item !== query)
    localStorage.setItem(STORAGE_PREFIX + ns, JSON.stringify(list))
  } catch {
    // ignore
  }
}

/**
 * 清空搜索历史
 * @param {string} ns
 */
export function clearSearchHistory(ns) {
  try {
    localStorage.removeItem(STORAGE_PREFIX + ns)
  } catch {
    // ignore
  }
}
