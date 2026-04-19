"""
发现数据源缓存层

使用内存 TTL 缓存包装 DiscoverySource，减少外部 API 调用频率。
缓存策略:
  - 列表数据 (popular/top_rated/trending/discover): 30 分钟
  - 详情数据 (get_detail): 2 小时
  - 搜索数据 (search): 15 分钟
  - 类型列表 (get_genres): 24 小时
  - 标签/合集列表: 24 小时

配置 (config.json → media.discovery.cache):
  {
    "enabled": true,
    "list_ttl": 1800,       # 列表缓存 TTL (秒)
    "detail_ttl": 7200,     # 详情缓存 TTL (秒)
    "search_ttl": 900,      # 搜索缓存 TTL (秒)
    "max_entries": 500       # 最大缓存条目数
  }
"""

import hashlib
import logging
import threading
import time
from collections import OrderedDict

logger = logging.getLogger("quark_cli.discovery.cache")


class TTLCache:
    """线程安全的 LRU + TTL 内存缓存"""

    def __init__(self, max_entries=500, default_ttl=1800):
        self._max = max_entries
        self._default_ttl = default_ttl
        self._store = OrderedDict()   # key → (value, expire_time)
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key):
        """获取缓存值，过期或不存在返回 None"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            value, expire_at = entry
            if time.time() > expire_at:
                # 过期
                del self._store[key]
                self._misses += 1
                return None

            # LRU: 移到末尾
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key, value, ttl=None):
        """设置缓存值"""
        if ttl is None:
            ttl = self._default_ttl

        expire_at = time.time() + ttl
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expire_at)

            # 淘汰溢出条目
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def invalidate(self, key):
        """删除指定缓存"""
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        """清空全部缓存"""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self):
        """缓存统计"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            # 统计未过期条目
            now = time.time()
            active = sum(1 for _, (_, exp) in self._store.items() if exp > now)
            return {
                "entries": len(self._store),
                "active": active,
                "max_entries": self._max,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 1),
            }


def _cache_key(*parts):
    """生成缓存 key"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


class CachedDiscoverySource:
    """
    缓存包装器 — 代理所有 DiscoverySource 方法，透明缓存结果。

    不继承 DiscoverySource ABC，而是通过 delegation + __getattr__ 透传，
    确保 hasattr/getattr 对额外方法 (如 get_available_tags) 正常工作。
    """

    def __init__(self, source, list_ttl=1800, detail_ttl=7200,
                 search_ttl=900, max_entries=500):
        self._source = source
        self._list_ttl = list_ttl
        self._detail_ttl = detail_ttl
        self._search_ttl = search_ttl
        self._cache = TTLCache(max_entries=max_entries, default_ttl=list_ttl)
        # 静态数据用更长 TTL
        self._static_ttl = 86400  # 24h

    def __getattr__(self, name):
        """未定义的方法/属性透传给底层 source"""
        return getattr(self._source, name)

    @property
    def source_name(self):
        return self._source.source_name

    # ── 搜索 (TTL: search_ttl) ──

    def search(self, query, media_type="movie", page=1, year=None):
        key = _cache_key("search", self.source_name, query, media_type, page, year)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.search(query, media_type, page, year)
        self._cache.set(key, result, self._search_ttl)
        return result

    # ── 详情 (TTL: detail_ttl) ──

    def get_detail(self, source_id, media_type="movie"):
        key = _cache_key("detail", self.source_name, source_id, media_type)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_detail(source_id, media_type)
        self._cache.set(key, result, self._detail_ttl)
        return result

    # ── 外部 ID 查找 (TTL: detail_ttl) ──

    def find_by_external_id(self, external_id, external_source="imdb_id"):
        key = _cache_key("ext", self.source_name, external_id, external_source)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.find_by_external_id(external_id, external_source)
        self._cache.set(key, result, self._detail_ttl)
        return result

    # ── 热门 (TTL: list_ttl) ──

    def get_popular(self, media_type="movie", page=1):
        key = _cache_key("popular", self.source_name, media_type, page)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_popular(media_type, page)
        self._cache.set(key, result, self._list_ttl)
        return result

    # ── 高分 (TTL: list_ttl) ──

    def get_top_rated(self, media_type="movie", page=1):
        key = _cache_key("top", self.source_name, media_type, page)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_top_rated(media_type, page)
        self._cache.set(key, result, self._list_ttl)
        return result

    # ── 趋势 (TTL: list_ttl) ──

    def get_trending(self, media_type="movie", time_window="week"):
        key = _cache_key("trend", self.source_name, media_type, time_window)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_trending(media_type, time_window)
        self._cache.set(key, result, self._list_ttl)
        return result

    # ── 发现 (TTL: list_ttl) ──

    def discover(self, media_type="movie", page=1, **filters):
        # filters 排序后作为 key 的一部分
        sorted_filters = tuple(sorted(filters.items()))
        key = _cache_key("discover", self.source_name, media_type, page, sorted_filters)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.discover(media_type, page, **filters)
        self._cache.set(key, result, self._list_ttl)
        return result

    # ── 类型列表 (TTL: 24h) ──

    def get_genres(self, media_type="movie"):
        key = _cache_key("genres", self.source_name, media_type)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_genres(media_type)
        self._cache.set(key, result, self._static_ttl)
        return result

    # ── 海报 URL (不缓存, 直接透传) ──

    def get_poster_url(self, path, size="w500"):
        return self._source.get_poster_url(path, size)

    # ── 合集 (豆瓣, TTL: list_ttl) ──

    def get_collection(self, collection_name, media_type="movie", page=1):
        if not hasattr(self._source, "get_collection"):
            raise AttributeError("数据源不支持 get_collection")
        key = _cache_key("coll", self.source_name, collection_name, media_type, page)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._source.get_collection(collection_name, media_type, page)
        self._cache.set(key, result, self._list_ttl)
        return result

    # ── 缓存管理 ──

    def cache_stats(self):
        """获取缓存统计信息"""
        stats = self._cache.stats()
        stats["source"] = self.source_name
        stats["ttl"] = {
            "list": self._list_ttl,
            "detail": self._detail_ttl,
            "search": self._search_ttl,
            "static": self._static_ttl,
        }
        return stats

    def cache_clear(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("缓存已清空: source=%s", self.source_name)


def wrap_with_cache(source, cache_config=None):
    """
    根据配置为数据源添加缓存包装。

    Args:
        source: DiscoverySource 实例
        cache_config: dict, 缓存配置:
            enabled: bool (默认 True)
            list_ttl: int (默认 1800)
            detail_ttl: int (默认 7200)
            search_ttl: int (默认 900)
            max_entries: int (默认 500)

    Returns:
        CachedDiscoverySource 或原始 source (缓存禁用时)
    """
    if cache_config is None:
        cache_config = {}

    if not cache_config.get("enabled", True):
        return source

    return CachedDiscoverySource(
        source,
        list_ttl=cache_config.get("list_ttl", 1800),
        detail_ttl=cache_config.get("detail_ttl", 7200),
        search_ttl=cache_config.get("search_ttl", 900),
        max_entries=cache_config.get("max_entries", 500),
    )
