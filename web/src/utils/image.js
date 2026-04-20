/**
 * 图片 URL 工具 — 将需要防盗链代理的外部图片 URL 转为后端代理 URL
 *
 * 豆瓣 doubanio.com 有 Referer 防盗链, 前端直接请求会 403。
 * 通过后端 /api/discovery/img?url=xxx 中转解决。
 */

// 需要走代理的域名
const PROXY_HOSTS = [
  'doubanio.com',
  'douban.com',
]

/**
 * 判断 URL 是否需要走图片代理
 */
function needsProxy(url) {
  if (!url) return false
  try {
    const hostname = new URL(url).hostname
    return PROXY_HOSTS.some(h => hostname.endsWith(h))
  } catch {
    return false
  }
}

/**
 * 将外部图片 URL 转为代理 URL
 * 非豆瓣的图片原样返回, 无需代理
 */
export function proxyImageUrl(url) {
  if (!url) return ''
  if (!needsProxy(url)) return url
  return `/api/discovery/img?url=${encodeURIComponent(url)}`
}
