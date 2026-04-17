"""Web 层依赖注入 — 从配置创建 Service 实例"""

from functools import lru_cache
from quark_cli.config import ConfigManager


_config_path = None


def set_config_path(path):
    global _config_path
    _config_path = path
    get_config.cache_clear()


@lru_cache()
def get_config():
    return ConfigManager(config_path=_config_path)


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
    )


def get_discovery_service():
    from quark_cli.services.discovery_service import DiscoveryService
    source = get_tmdb_source()
    if not source:
        return None
    return DiscoveryService(source)
