"""
Media Provider 注册表
管理所有可用的 Provider 类型和实例创建
"""

from typing import Dict, Type, Optional, Any
from quark_cli.media.base import MediaProvider


# 已注册的 Provider 类
_REGISTRY: Dict[str, Type[MediaProvider]] = {}


def register_provider(name: str, cls: Type[MediaProvider]):
    """注册一个 Provider 类型"""
    _REGISTRY[name.lower()] = cls


def get_provider_class(name: str) -> Optional[Type[MediaProvider]]:
    """获取已注册的 Provider 类"""
    return _REGISTRY.get(name.lower())


def list_providers() -> Dict[str, Type[MediaProvider]]:
    """列出所有已注册的 Provider"""
    return dict(_REGISTRY)


def create_provider(name: str, config: Any) -> MediaProvider:
    """
    根据 Provider 名称和配置创建实例

    Args:
        name: Provider 名称 (fnos / emby / jellyfin)
        config: Provider 对应的配置对象
    """
    cls = get_provider_class(name)
    if cls is None:
        available = ", ".join(_REGISTRY.keys()) or "(无)"
        raise ValueError(
            f"未知的 media provider: '{name}'。可用: {available}"
        )
    return cls(config)


# ── 内置注册 ──

def _register_builtins():
    """注册内置 Provider"""
    # fnOS
    from quark_cli.media.fnos.provider import FnosMediaProvider
    register_provider("fnos", FnosMediaProvider)


_register_builtins()
