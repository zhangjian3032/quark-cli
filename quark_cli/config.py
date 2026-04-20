"""
配置管理模块 - Cookie 和配置文件管理
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List


DEFAULT_CONFIG_DIR = Path.home() / ".quark-cli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "cookie": [],
    "push_config": {},
    "search_sources": {
        "pansou": "https://www.pansou.com",
    },
    "magic_regex": {
        "$TV": {
            "pattern": r".*?([Ss]\d{1,2})?(?:[第EePpXx\.\-\_\( ]{1,2}|^)(\d{1,3})(?!\d).*?\.(mp4|mkv)",
            "replace": r"\1E\2.\3",
        },
        "$BLACK_WORD": {
            "pattern": r"^(?!.*纯享)(?!.*加更)(?!.*超前企划)(?!.*训练室)(?!.*蒸蒸日上).*",
            "replace": "",
        },
        "$TV_MAGIC": {
            "pattern": r".*\.(mp4|mkv|mov|m4v|avi|mpeg|ts)$",
            "replace": "{TASKNAME}.{SXX}E{E}.{EXT}",
        },
    },
    "tasklist": [],
    "torrent_clients": {
        "default": "",
        "qbittorrent": [],
        "_reserved": {
            "transmission": "Transmission RPC — 如有需求请反馈开发",
            "aria2": "aria2 JSON-RPC — 如有需求请反馈开发",
        },
    },
}


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE
        self._data: Dict[str, Any] = {}
        self._ensure_dir()

    def _ensure_dir(self):
        """确保配置目录存在"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """加载配置"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()
        return self._data

    def save(self):
        """保存配置"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @property
    def data(self) -> Dict[str, Any]:
        if not self._data:
            self.load()
        return self._data

    def get_cookies(self) -> List[str]:
        """获取 cookie 列表"""
        cookie_val = self.data.get("cookie", [])
        if isinstance(cookie_val, list):
            return [c for c in cookie_val if c and not c.startswith("Your ")]
        elif cookie_val:
            return cookie_val.split("\n") if "\n" in cookie_val else [cookie_val]
        return []

    def set_cookie(self, cookie: str, index: int = 0):
        """设置 cookie"""
        cookies = self.data.get("cookie", [])
        if not isinstance(cookies, list):
            cookies = [cookies] if cookies else []
        # 扩展列表
        while len(cookies) <= index:
            cookies.append("")
        cookies[index] = cookie.strip()
        self._data["cookie"] = cookies
        self.save()

    def remove_cookie(self, index: int = 0):
        """移除 cookie"""
        cookies = self.data.get("cookie", [])
        if isinstance(cookies, list) and 0 <= index < len(cookies):
            cookies.pop(index)
            self._data["cookie"] = cookies
            self.save()

    def get_tasklist(self) -> List[dict]:
        """获取任务列表"""
        return self.data.get("tasklist", [])

    def add_task(self, task: dict):
        """添加任务"""
        if "tasklist" not in self._data:
            self._data["tasklist"] = []
        self._data["tasklist"].append(task)
        self.save()

    def remove_task(self, index: int):
        """移除任务"""
        tasks = self._data.get("tasklist", [])
        if 0 <= index < len(tasks):
            tasks.pop(index)
            self.save()

    def update_task(self, index: int, task: dict):
        """更新任务"""
        tasks = self._data.get("tasklist", [])
        if 0 <= index < len(tasks):
            tasks[index] = task
            self.save()

    def get_config_path(self) -> str:
        return str(self.config_path)

    def show_config(self) -> str:
        """显示当前配置（隐藏敏感信息）"""
        data = self.data.copy()
        # 隐藏 cookie
        cookies = data.get("cookie", [])
        if isinstance(cookies, list):
            data["cookie"] = [
                f"{c[:20]}...{c[-10:]}" if len(c) > 30 else "***"
                for c in cookies
            ]
        return json.dumps(data, ensure_ascii=False, indent=2)


# ── Proxy 工具函数 ──

def get_proxy_for(cfg_data: dict, target: str):
    """
    通用 proxy 查询: 根据配置 dict 获取指定目标的代理 URL。

    Args:
        cfg_data: config.json 的完整 data dict
        target: 代理目标名称, 如 "tmdb", "douban", "rss"

    Returns:
        proxy URL 字符串, 若未配置或目标不在列表中返回 None
    """
    proxy_cfg = cfg_data.get("proxy", {})
    proxy_url = proxy_cfg.get("url", "").strip()
    if not proxy_url:
        return None
    targets = proxy_cfg.get("targets", [])
    if target in targets:
        return proxy_url
    return None
