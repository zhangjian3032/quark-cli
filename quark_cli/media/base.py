"""
Media Provider 抽象基类
所有影视媒体中心 Provider 必须实现此接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MediaItem:
    """统一影片数据模型"""

    def __init__(
        self,
        guid: str = "",
        title: str = "",
        original_title: str = "",
        media_type: str = "",
        year: str = "",
        rating: float = 0.0,
        overview: str = "",
        poster_url: str = "",
        played: bool = False,
        parent_guid: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.guid = guid
        self.title = title
        self.original_title = original_title
        self.media_type = media_type  # Movie / TV / Video / Directory
        self.year = year
        self.rating = rating
        self.overview = overview
        self.poster_url = poster_url
        self.played = played
        self.parent_guid = parent_guid
        self.extra = extra or {}

    def __repr__(self):
        return f"<MediaItem {self.title} ({self.guid[:12]})>"


class MediaLibrary:
    """统一媒体库数据模型"""

    def __init__(
        self,
        guid: str = "",
        title: str = "",
        category: str = "",
        count: int = 0,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.guid = guid
        self.title = title
        self.category = category
        self.count = count
        self.extra = extra or {}


class MediaSeason:
    """统一季数据模型"""

    def __init__(
        self,
        guid: str = "",
        title: str = "",
        season_number: int = 0,
        episode_count: int = 0,
        poster_url: str = "",
    ):
        self.guid = guid
        self.title = title
        self.season_number = season_number
        self.episode_count = episode_count
        self.poster_url = poster_url


class MediaEpisode:
    """统一剧集数据模型"""

    def __init__(
        self,
        guid: str = "",
        title: str = "",
        episode_number: int = 0,
        season_number: int = 0,
        duration: float = 0.0,
        poster_url: str = "",
    ):
        self.guid = guid
        self.title = title
        self.episode_number = episode_number
        self.season_number = season_number
        self.duration = duration
        self.poster_url = poster_url


class MediaPerson:
    """统一演职人员数据模型"""

    def __init__(self, name: str = "", role: str = "", profile_url: str = ""):
        self.name = name
        self.role = role
        self.profile_url = profile_url


class ItemListResult:
    """统一分页结果"""

    def __init__(self, items: List[MediaItem] = None, total: int = 0):
        self.items = items or []
        self.total = total


class PlayRecord:
    """统一播放记录"""

    def __init__(
        self,
        guid: str = "",
        title: str = "",
        tv_title: str = "",
        media_type: str = "",
        poster_url: str = "",
        season_number: int = 0,
        episode_number: int = 0,
        duration: float = 0.0,
        timestamp: float = 0.0,
    ):
        self.guid = guid
        self.title = title
        self.tv_title = tv_title
        self.media_type = media_type
        self.poster_url = poster_url
        self.season_number = season_number
        self.episode_number = episode_number
        self.duration = duration
        self.timestamp = timestamp


class MediaProviderError(Exception):
    """Provider 统一异常"""

    def __init__(self, code: int = -1, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class MediaProvider(ABC):
    """
    影视媒体中心抽象基类

    所有 Provider（fnOS / Emby / Jellyfin）都必须实现以下接口。
    CLI 命令层只依赖此基类，不直接依赖任何具体 Provider 实现。
    """

    # ── Provider 元信息 ──

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回 Provider 名称，如 'fnos' / 'emby' / 'jellyfin'"""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """返回服务端地址"""
        ...

    # ── 认证 ──

    @abstractmethod
    def login(self, username: str, password: str) -> str:
        """登录并返回 token"""
        ...

    @abstractmethod
    def get_user_info(self) -> Dict[str, Any]:
        """获取当前用户信息，返回 {'username': ..., 'device': ...}"""
        ...

    # ── 媒体库 ──

    @abstractmethod
    def get_libraries(self) -> List[MediaLibrary]:
        """获取所有媒体库"""
        ...

    # ── 影片 ──

    @abstractmethod
    def get_items(
        self,
        library_guid: str = "",
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "add_time",
        sort_order: str = "desc",
    ) -> ItemListResult:
        """获取影片列表"""
        ...

    @abstractmethod
    def search_items(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        library_guid: str = "",
    ) -> ItemListResult:
        """搜索影片"""
        ...

    @abstractmethod
    def get_item_detail(self, guid: str) -> MediaItem:
        """获取影片详情"""
        ...

    # ── 季 & 剧集 ──

    @abstractmethod
    def get_seasons(self, guid: str) -> List[MediaSeason]:
        """获取剧集的季列表"""
        ...

    @abstractmethod
    def get_episodes(self, season_guid: str) -> List[MediaEpisode]:
        """获取某季的剧集列表"""
        ...

    # ── 演职人员 ──

    @abstractmethod
    def get_persons(self, guid: str) -> List[MediaPerson]:
        """获取影片演职人员"""
        ...

    # ── 播放记录 ──

    @abstractmethod
    def get_play_records(self) -> List[PlayRecord]:
        """获取继续观看列表"""
        ...

    @abstractmethod
    def delete_play_record(self, guid: str) -> None:
        """删除播放记录"""
        ...

    # ── 图片 ──

    @abstractmethod
    def get_poster_url(self, guid: str, thumb: bool = False) -> str:
        """获取海报图片 URL"""
        ...

    @abstractmethod
    def download_poster(self, guid, output_dir=".", thumb=False):
        """下载海报和背景图到本地目录，返回保存的文件路径列表"""
        ...

    # ── 导出 ──

    def export_items(
        self,
        library_name: str = "",
        fmt: str = "json",
        output_path: str = "export.json",
    ) -> str:
        """
        导出影片列表，默认实现基于 get_libraries() + get_items() 遍历。
        子类可覆盖以提供更高效的实现。返回输出文件路径。
        """
        import csv
        import json as json_mod
        from pathlib import Path

        all_items = []
        libs = self.get_libraries()
        for lib in libs:
            if library_name and lib.title != library_name:
                continue
            page = 1
            while True:
                result = self.get_items(library_guid=lib.guid, page=page, page_size=100)
                if not result.items:
                    break
                for item in result.items:
                    all_items.append({
                        "guid": item.guid,
                        "title": item.title,
                        "original_title": item.original_title,
                        "year": item.year,
                        "rating": item.rating,
                        "type": item.media_type,
                        "overview": item.overview,
                        "library": lib.title,
                    })
                if len(result.items) < 100:
                    break
                page += 1

        out = Path(output_path)
        if fmt == "csv":
            out = out.with_suffix(".csv")
            if all_items:
                with open(out, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=all_items[0].keys())
                    writer.writeheader()
                    writer.writerows(all_items)
        else:
            out = out.with_suffix(".json")
            with open(out, "w", encoding="utf-8") as f:
                json_mod.dump(all_items, f, ensure_ascii=False, indent=2)

        return str(out)
