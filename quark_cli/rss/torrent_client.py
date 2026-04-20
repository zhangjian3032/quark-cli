"""
Torrent 客户端封装

支持的客户端:
  - qBittorrent (Web API v2)
  - (预留) Transmission
  - (预留) aria2 (JSON-RPC)

RSS 匹配到 torrent/magnet 资源后, 通过本模块推送给下载客户端。
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("quark_cli.rss.torrent_client")


# ═══════════════════════════════════════════════════
#  基类
# ═══════════════════════════════════════════════════

class BaseTorrentClient:
    """Torrent 客户端抽象基类"""

    client_type = "base"

    def login(self) -> bool:
        raise NotImplementedError

    def add_torrent_url(self, url, **kwargs) -> dict:
        raise NotImplementedError

    def add_torrent_file(self, torrent_bytes, filename="file.torrent", **kwargs) -> dict:
        raise NotImplementedError

    def add_magnet(self, magnet_uri, **kwargs) -> dict:
        raise NotImplementedError

    def get_torrent_list(self, **kwargs) -> list:
        raise NotImplementedError

    def get_version(self) -> str:
        raise NotImplementedError

    def test_connection(self) -> dict:
        """测试连接, 返回 {success, version, error}"""
        try:
            if not self.login():
                return {"success": False, "error": "登录失败: 请检查用户名/密码"}
            ver = self.get_version()
            return {"success": True, "version": ver, "error": ""}
        except Exception as e:
            return {"success": False, "version": "", "error": str(e)}


# ═══════════════════════════════════════════════════
#  qBittorrent Web API v2
# ═══════════════════════════════════════════════════

class QBittorrentClient(BaseTorrentClient):
    """
    qBittorrent Web API v2 客户端

    API 文档: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)
    要求: qBittorrent >= 4.1
    """

    client_type = "qbittorrent"

    def __init__(
        self,
        host="127.0.0.1",
        port=8080,
        username="admin",
        password="",
        use_https=False,
        timeout=15,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_https = use_https
        self.timeout = timeout

        self._session = requests.Session()
        self._logged_in = False

    @property
    def _base_url(self):
        scheme = "https" if self.use_https else "http"
        return "{}://{}:{}".format(scheme, self.host, self.port)

    def _url(self, path):
        return "{}{}".format(self._base_url, path)

    # ── 认证 ──

    def login(self) -> bool:
        """登录 qBittorrent Web UI"""
        if self._logged_in:
            return True

        try:
            resp = self._session.post(
                self._url("/api/v2/auth/login"),
                data={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
            # qB 返回 "Ok." 表示成功, "Fails." 表示失败
            if resp.status_code == 200 and resp.text.strip().lower().startswith("ok"):
                self._logged_in = True
                logger.debug("qBittorrent 登录成功: %s:%s", self.host, self.port)
                return True
            else:
                logger.warning("qBittorrent 登录失败: %s (HTTP %d)", resp.text.strip(), resp.status_code)
                return False
        except requests.RequestException as e:
            logger.error("qBittorrent 连接失败: %s", e)
            raise ConnectionError("无法连接 qBittorrent @ {}:{} — {}".format(
                self.host, self.port, e))

    def _ensure_login(self):
        """确保已登录"""
        if not self._logged_in:
            if not self.login():
                raise ConnectionError("qBittorrent 登录失败")

    # ── 版本 ──

    def get_version(self) -> str:
        """获取 qBittorrent 版本"""
        self._ensure_login()
        resp = self._session.get(self._url("/api/v2/app/version"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.text.strip()

    # ── 添加种子 ──

    def _build_add_params(self, save_path="", category="", tags=None, paused=False):
        """构建 /api/v2/torrents/add 的通用参数"""
        params = {}
        if save_path:
            params["savepath"] = save_path
        if category:
            params["category"] = category
        if tags:
            if isinstance(tags, list):
                params["tags"] = ",".join(tags)
            else:
                params["tags"] = str(tags)
        if paused:
            params["paused"] = "true"
        return params

    def add_magnet(self, magnet_uri, save_path="", category="", tags=None, paused=False) -> dict:
        """
        通过磁力链接添加种子

        Args:
            magnet_uri: magnet:?xt=urn:btih:...
            save_path: 下载保存路径
            category: 分类
            tags: 标签列表
            paused: 是否暂停

        Returns:
            dict: {success: bool, hash: str, error: str}
        """
        self._ensure_login()

        data = self._build_add_params(save_path, category, tags, paused)
        data["urls"] = magnet_uri

        resp = self._session.post(
            self._url("/api/v2/torrents/add"),
            data=data,
            timeout=self.timeout,
        )

        if resp.status_code == 200 and "ok" in resp.text.strip().lower():
            # 尝试提取 info hash
            info_hash = _extract_info_hash(magnet_uri)
            logger.info("qBittorrent 添加磁力成功: %s", info_hash or magnet_uri[:60])
            return {"success": True, "hash": info_hash, "error": ""}
        else:
            error_msg = "添加磁力失败: HTTP {} — {}".format(resp.status_code, resp.text[:200])
            logger.warning(error_msg)
            return {"success": False, "hash": "", "error": error_msg}

    def add_torrent_url(self, url, save_path="", category="", tags=None, paused=False) -> dict:
        """
        通过 URL 添加种子 (qB 自行下载 .torrent 文件)

        适用于公开可访问的 .torrent URL。
        如果是需要认证的 PT 站 .torrent, 应先下载后用 add_torrent_file。
        """
        self._ensure_login()

        data = self._build_add_params(save_path, category, tags, paused)
        data["urls"] = url

        resp = self._session.post(
            self._url("/api/v2/torrents/add"),
            data=data,
            timeout=self.timeout,
        )

        if resp.status_code == 200 and "ok" in resp.text.strip().lower():
            logger.info("qBittorrent 添加 URL 成功: %s", url[:80])
            return {"success": True, "hash": "", "error": ""}
        else:
            error_msg = "添加 URL 失败: HTTP {} — {}".format(resp.status_code, resp.text[:200])
            logger.warning(error_msg)
            return {"success": False, "hash": "", "error": error_msg}

    def add_torrent_file(self, torrent_bytes, filename="file.torrent",
                         save_path="", category="", tags=None, paused=False) -> dict:
        """
        通过上传 .torrent 文件添加种子

        Args:
            torrent_bytes: .torrent 文件的二进制内容
            filename: 文件名 (用于 multipart)
        """
        self._ensure_login()

        data = self._build_add_params(save_path, category, tags, paused)
        files = {
            "torrents": (filename, torrent_bytes, "application/x-bittorrent"),
        }

        resp = self._session.post(
            self._url("/api/v2/torrents/add"),
            data=data,
            files=files,
            timeout=self.timeout,
        )

        if resp.status_code == 200 and "ok" in resp.text.strip().lower():
            logger.info("qBittorrent 上传种子成功: %s", filename)
            return {"success": True, "hash": "", "error": ""}
        else:
            error_msg = "上传种子失败: HTTP {} — {}".format(resp.status_code, resp.text[:200])
            logger.warning(error_msg)
            return {"success": False, "hash": "", "error": error_msg}

    # ── 查询 ──

    def get_torrent_list(self, filter="all", category="", sort="added_on",
                         reverse=True, limit=50) -> list:
        """
        获取种子列表

        Args:
            filter: all / downloading / seeding / completed / paused / active / inactive
            category: 分类过滤
            sort: 排序字段
            reverse: 是否降序
            limit: 最大返回数
        """
        self._ensure_login()

        params = {
            "filter": filter,
            "sort": sort,
            "reverse": str(reverse).lower(),
            "limit": limit,
        }
        if category:
            params["category"] = category

        resp = self._session.get(
            self._url("/api/v2/torrents/info"),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════

# 从磁力链接中提取 info hash (40 位 hex 或 32 位 base32)
_INFO_HASH_RE = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", re.IGNORECASE)


def _extract_info_hash(magnet_uri):
    """从磁力链接中提取 info hash"""
    m = _INFO_HASH_RE.search(magnet_uri)
    if m:
        return m.group(1).lower()
    return ""


# Torrent 文件的 MIME types
TORRENT_MIME_TYPES = {
    "application/x-bittorrent",
    "application/x-torrent",
}


def is_torrent_url(url):
    """判断 URL 是否指向 .torrent 文件"""
    if not url:
        return False
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".torrent")


def is_magnet_url(url):
    """判断是否为磁力链接"""
    return url.strip().startswith("magnet:")


def download_torrent_file(url, auth=None, timeout=30):
    """
    下载 .torrent 文件

    Args:
        url: .torrent 文件的 URL
        auth: dict with optional cookie/headers (用于 PT 站认证)
        timeout: 超时秒数

    Returns:
        tuple: (torrent_bytes, filename)

    Raises:
        Exception: 下载失败
    """
    headers = {
        "User-Agent": "quark-cli/1.0",
    }

    if auth:
        if auth.get("cookie"):
            headers["Cookie"] = auth["cookie"]
        if auth.get("headers") and isinstance(auth["headers"], dict):
            headers.update(auth["headers"])

    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")

    # 验证确实是 torrent 文件
    # 有些服务器 Content-Type 不准确, 检查文件魔术字节
    content = resp.content
    if not content:
        raise ValueError("下载内容为空: {}".format(url))

    # BEncode 格式的 .torrent 文件以 'd' 开头
    if content[0:1] != b'd' and content_type not in TORRENT_MIME_TYPES:
        raise ValueError("下载内容不是有效的 torrent 文件 (Content-Type: {})".format(content_type))

    # 提取文件名
    filename = "downloaded.torrent"
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        # Content-Disposition: attachment; filename="xxx.torrent"
        m = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', cd)
        if m:
            filename = m.group(1).strip()
    else:
        # 从 URL 路径提取
        parsed = urlparse(url)
        path_parts = parsed.path.rsplit("/", 1)
        if len(path_parts) > 1 and path_parts[1]:
            filename = path_parts[1]

    if not filename.endswith(".torrent"):
        filename += ".torrent"

    logger.debug("下载 torrent 文件成功: %s (%d bytes)", filename, len(content))
    return content, filename


# ═══════════════════════════════════════════════════
#  客户端工厂
# ═══════════════════════════════════════════════════

def get_torrent_client(config_path=None, client_id=None):
    """
    从 config.json 读取配置, 构建 Torrent 客户端实例

    Args:
        config_path: 配置文件路径
        client_id: 客户端 ID (不指定则用 default)

    Returns:
        BaseTorrentClient

    Raises:
        ValueError: 配置不存在或无效
    """
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()

    tc = cfg.data.get("torrent_clients", {})
    if not tc:
        raise ValueError(
            "未配置 Torrent 客户端。"
            "请运行: quark-cli torrent config --host <ip> --port <port>"
        )

    # 确定客户端 ID
    target_id = client_id or tc.get("default", "")

    # 查找 qBittorrent 配置
    qb_list = tc.get("qbittorrent", [])
    for qb_cfg in qb_list:
        if qb_cfg.get("id") == target_id or (not target_id and qb_list):
            return QBittorrentClient(
                host=qb_cfg.get("host", "127.0.0.1"),
                port=int(qb_cfg.get("port", 8080)),
                username=qb_cfg.get("username", "admin"),
                password=qb_cfg.get("password", ""),
                use_https=qb_cfg.get("use_https", False),
            )

    # 如果只有一个客户端, 直接使用
    if len(qb_list) == 1:
        qb_cfg = qb_list[0]
        return QBittorrentClient(
            host=qb_cfg.get("host", "127.0.0.1"),
            port=int(qb_cfg.get("port", 8080)),
            username=qb_cfg.get("username", "admin"),
            password=qb_cfg.get("password", ""),
            use_https=qb_cfg.get("use_https", False),
        )

    raise ValueError("找不到 Torrent 客户端配置 (id={})".format(target_id))
