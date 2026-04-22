"""Web 层依赖注入 — 从配置创建 Service 实例"""

from functools import lru_cache
from quark_cli.config import ConfigManager


_config_path = None

# 缓存的数据源实例 (避免每次请求重建缓存)
_cached_sources = {}


def set_config_path(path):
    global _config_path, _cached_sources
    _config_path = path
    _cached_sources = {}
    get_config.cache_clear()


@lru_cache()
def get_config():
    return ConfigManager(config_path=_config_path)


def get_config_path():
    """返回当前配置文件路径 (供 RssManager / history 等使用)"""
    return _config_path


def get_proxy_for(target):
    """获取指定目标的代理 URL, 若未配置或未启用则返回 None"""
    from quark_cli.config import get_proxy_for as _proxy_for
    cfg = get_config()
    cfg.load()
    return _proxy_for(cfg.data, target)


def _get_cache_config():
    """读取缓存配置"""
    cfg = get_config()
    return cfg.data.get("media", {}).get("discovery", {}).get("cache", {})


# ── 夸克网盘 ──

def get_quark_client():
    from quark_cli.api import QuarkAPI
    cfg = get_config()
    cookies = cfg.get_cookies()
    if not cookies:
        raise ValueError("未配置 Cookie，请先执行: quark-cli config set-cookie <cookie>")
    return QuarkAPI(cookies[0])


def get_drive_service():
    from quark_cli.services.drive_service import DriveService
    return DriveService(get_quark_client())


def get_search_service():
    from quark_cli.services.search_service import SearchService
    from quark_cli.search import PanSearch
    cfg = get_config()
    cfg.load()
    return SearchService(get_quark_client(), PanSearch(cfg))


def get_account_service():
    from quark_cli.services.account_service import AccountService
    return AccountService(get_quark_client())


# ── 影视媒体中心 ──

def get_media_provider():
    from quark_cli.media.registry import create_provider
    from quark_cli.media.fnos.config import FnosConfig
    cfg = get_config()
    media_cfg = cfg.data.get("media", {})
    provider_name = media_cfg.get("provider", "fnos")
    if provider_name == "fnos":
        fnos_data = media_cfg.get("fnos", {})
        config = FnosConfig.from_dict(fnos_data)
        config = FnosConfig.from_env(config)
        config.validate()
        return create_provider("fnos", config)
    raise ValueError("未知 provider: {}".format(provider_name))


def get_media_service():
    from quark_cli.services.media_service import MediaService
    return MediaService(get_media_provider())


# ── TMDB 发现 ──

def get_tmdb_source():
    from quark_cli.media.discovery.tmdb import TmdbSource
    cfg = get_config()
    media_cfg = cfg.data.get("media", {})
    disc = media_cfg.get("discovery", {})
    api_key = disc.get("tmdb_api_key", "")
    if not api_key:
        return None
    return TmdbSource(
        api_key=api_key,
        language=disc.get("language", "zh-CN"),
        region=disc.get("region", "CN"),
        proxy=get_proxy_for("tmdb"),
    )


# ── 豆瓣发现 ──

def get_douban_source():
    from quark_cli.media.discovery.douban import DoubanSource
    return DoubanSource(proxy=get_proxy_for("douban"))


# ── 统一发现服务 (带缓存) ──

def get_discovery_source(source_name=None):
    """
    根据 source 名称返回对应的数据源实例 (带缓存包装)。
    source_name: "tmdb" / "douban" / None (自动选择)
    """
    from quark_cli.media.discovery.cache import wrap_with_cache

    # 确定实际 source_name
    actual_name = source_name
    if actual_name == "douban":
        raw = get_douban_source()
    elif actual_name == "tmdb":
        raw = get_tmdb_source()
        if not raw:
            return None
    else:
        raw = get_tmdb_source()
        if raw:
            actual_name = "tmdb"
        else:
            raw = get_douban_source()
            actual_name = "douban"

    if raw is None:
        return None

    # 复用已缓存的包装实例 (同一 source_name 共享缓存)
    if actual_name in _cached_sources:
        return _cached_sources[actual_name]

    cache_cfg = _get_cache_config()
    wrapped = wrap_with_cache(raw, cache_cfg)
    _cached_sources[actual_name] = wrapped
    return wrapped


def get_discovery_service(source_name=None):
    from quark_cli.services.discovery_service import DiscoveryService
    source = get_discovery_source(source_name)
    if not source:
        return None
    return DiscoveryService(source)


# ── 光鸭云盘 ──

_guangya_client_cache = None


def _clear_guangya_cache():
    global _guangya_client_cache
    _guangya_client_cache = None


def get_guangya_client():
    global _guangya_client_cache
    if _guangya_client_cache is not None:
        return _guangya_client_cache

    from quark_cli.guangya_api import GuangyaAPI
    cfg = get_config()
    cfg.load()
    gy = cfg.data.get("guangya", {})
    refresh_token = gy.get("refresh_token", "")
    if not refresh_token:
        return None
    client = GuangyaAPI(refresh_token=refresh_token)
    _guangya_client_cache = client
    return client


def get_guangya_drive_service():
    from quark_cli.services.guangya_drive_service import GuangyaDriveService
    return GuangyaDriveService(get_guangya_client())
