"""
fnOS 配置管理
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

DEFAULT_API_KEY = "16CCEB3D-AB42-077D-36A1-F355324E4237"


def _normalize_host_port_ssl(host, port, ssl):
    # type: (str, int, bool) -> Tuple[str, int, bool]
    """规范化 host/port/ssl，支持 http(s)://host:port 和 host:port 格式"""
    raw = (host or "").strip()
    if not raw:
        return raw, port, ssl

    if "://" in raw:
        p = urlparse(raw)
        if p.scheme in ("http", "https"):
            ssl = p.scheme == "https"
        if p.hostname:
            raw = p.hostname
        if p.port:
            port = p.port
        return raw, port, ssl

    if raw.startswith("[") or (":" in raw and raw.rsplit(":", 1)[-1].isdigit()):
        p = urlparse("http://" + raw)
        if p.hostname:
            raw = p.hostname
        if p.port:
            port = p.port

    return raw.rstrip("/"), port, ssl


class FnosConfig:
    """fnOS 配置"""

    def __init__(
        self,
        host="",       # type: str
        port=5666,     # type: int
        token="",      # type: str
        api_key=DEFAULT_API_KEY,  # type: str
        ssl=False,     # type: bool
        timeout=30,    # type: int
    ):
        self.host = host
        self.port = port
        self.token = token
        self.api_key = api_key
        self.ssl = ssl
        self.timeout = timeout

    @property
    def base_url(self):
        # type: () -> str
        host, port, ssl = _normalize_host_port_ssl(self.host, self.port, self.ssl)
        scheme = "https" if ssl else "http"
        if host and ":" in host and not host.startswith("["):
            host = "[{}]".format(host)
        return "{}://{}:{}".format(scheme, host, port)

    @property
    def api_base(self):
        # type: () -> str
        return "{}/v".format(self.base_url)

    @property
    def img_base(self):
        # type: () -> str
        return "{}/api/v1/sys/img".format(self.api_base)

    def validate(self):
        if not self.host:
            raise ValueError("host 不能为空，请先配置 fnOS 地址 (quark-cli media login)")
        if not (1 <= self.port <= 65535):
            raise ValueError("port 必须在 1-65535 之间，当前值: {}".format(self.port))

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "host": self.host,
            "port": self.port,
            "token": self.token,
            "ssl": self.ssl,
            "api_key": self.api_key,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data):
        # type: (Dict[str, Any]) -> FnosConfig
        return cls(
            host=data.get("host", ""),
            port=data.get("port", 5666),
            token=data.get("token", ""),
            api_key=data.get("api_key", DEFAULT_API_KEY),
            ssl=data.get("ssl", False),
            timeout=data.get("timeout", 30),
        )

    @classmethod
    def from_env(cls, base=None):
        # type: (Optional[FnosConfig]) -> FnosConfig
        """从环境变量加载覆盖"""
        cfg = base or cls()
        env_host = os.environ.get("FNOS_HOST")
        if env_host:
            cfg.host = env_host
        env_port = os.environ.get("FNOS_PORT")
        if env_port:
            cfg.port = int(env_port)
        env_token = os.environ.get("FNOS_TOKEN")
        if env_token:
            cfg.token = env_token
        env_ssl = os.environ.get("FNOS_SSL")
        if env_ssl:
            cfg.ssl = env_ssl.lower() in ("true", "1", "yes")
        return cfg
