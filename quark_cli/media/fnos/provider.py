"""
fnOS Media Provider - 实现 MediaProvider 抽象接口
"""

import os
from typing import Any, Dict, List, Optional

from quark_cli.media.base import (
    ItemListResult,
    MediaEpisode,
    MediaItem,
    MediaLibrary,
    MediaPerson,
    MediaProvider,
    MediaProviderError,
    MediaSeason,
    PlayRecord,
)
from quark_cli.media.fnos.client import FnosClient, FnosApiError
from quark_cli.media.fnos.config import FnosConfig


def _to_media_item(raw):
    # type: (Dict) -> MediaItem
    """将 fnOS API 返回的 dict 转换为统一 MediaItem"""
    release_date = raw.get("release_date", "") or ""
    year = release_date.split("-", 1)[0] if release_date else ""
    return MediaItem(
        guid=raw.get("guid", ""),
        title=raw.get("title", ""),
        original_title=raw.get("name", "") or "",
        media_type=raw.get("type", ""),
        year=year,
        rating=float(raw.get("vote_average", 0) or 0),
        overview=raw.get("overview", "") or "",
        poster_url=raw.get("posters", "") or raw.get("poster", "") or "",
        played=bool(raw.get("played", False)),
        parent_guid=raw.get("parent_guid", "") or "",
        extra=raw,
    )


def _get_ext(path):
    # type: (str) -> str
    """从图片路径中提取扩展名"""
    if not path:
        return "jpg"
    base = path.rsplit("/", 1)[-1] if "/" in path else path
    if "." in base:
        return base.rsplit(".", 1)[-1].lower()
    return "jpg"


def _sanitize_filename(name):
    # type: (str) -> str
    """清理文件名中不合法的字符"""
    bad = '<>:"/\\|?*'
    for c in bad:
        name = name.replace(c, "_")
    return name.strip().rstrip(".")


class FnosMediaProvider(MediaProvider):
    """fnOS 飞牛影视 Provider"""

    def __init__(self, config):
        # type: (FnosConfig) -> None
        self._config = config
        self._client = FnosClient(config)

    @property
    def provider_name(self):
        return "fnos"

    @property
    def base_url(self):
        return self._config.base_url

    @property
    def client(self):
        return self._client

    @property
    def config(self):
        return self._config

    def _wrap_error(self, e):
        return MediaProviderError(code=e.code, message=e.msg)

    # ── 认证 ──

    def login(self, username, password):
        try:
            return self._client.login(username, password)
        except FnosApiError as e:
            raise self._wrap_error(e)

    def get_user_info(self):
        try:
            user = self._client.get_user_info()
            sys_cfg = self._client.get_system_config()
            return {
                "username": user.get("nick_name") or user.get("username", ""),
                "device": sys_cfg.get("device_name") or sys_cfg.get("server_name", ""),
            }
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 媒体库 ──

    def get_libraries(self):
        try:
            raw_list = self._client.get_mediadb_list()
            return [
                MediaLibrary(
                    guid=d.get("guid", ""),
                    title=d.get("title", ""),
                    category=d.get("category", ""),
                    count=int(d.get("count", 0) or 0),
                    extra=d,
                )
                for d in raw_list
            ]
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 影片 ──

    def get_items(
        self,
        library_guid="",
        page=1,
        page_size=50,
        sort_by="add_time",
        sort_order="desc",
    ):
        try:
            resp = self._client.get_item_list(
                ancestor_guid=library_guid,
                page_size=page_size,
                page_num=page,
            )
            items = [_to_media_item(d) for d in resp.get("list", [])]
            return ItemListResult(items=items, total=int(resp.get("total", 0) or 0))
        except FnosApiError as e:
            raise self._wrap_error(e)

    def search_items(
        self,
        keyword="",
        page=1,
        page_size=20,
        library_guid="",
    ):
        try:
            resp = self._client.search_items(
                keyword=keyword,
                page_size=page_size,
                page_num=page,
                ancestor_guid=library_guid,
            )
            items = [_to_media_item(d) for d in resp.get("list", [])]
            return ItemListResult(items=items, total=int(resp.get("total", 0) or 0))
        except FnosApiError as e:
            raise self._wrap_error(e)

    def get_item_detail(self, guid):
        try:
            raw = self._client.get_item_detail(guid)
            return _to_media_item(raw)
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 季 & 剧集 ──

    def get_seasons(self, guid):
        try:
            raw_list = self._client.get_season_list(guid)
            return [
                MediaSeason(
                    guid=d.get("guid", ""),
                    title=d.get("title", ""),
                    season_number=int(d.get("season_number", 0) or 0),
                    episode_count=int(d.get("episode_count", 0) or 0),
                    poster_url=d.get("poster", "") or "",
                )
                for d in raw_list
            ]
        except FnosApiError as e:
            raise self._wrap_error(e)

    def get_episodes(self, season_guid):
        try:
            raw_list = self._client.get_episode_list(season_guid)
            return [
                MediaEpisode(
                    guid=d.get("guid", ""),
                    title=d.get("title", ""),
                    episode_number=int(d.get("episode_number", 0) or 0),
                    season_number=int(d.get("season_number", 0) or 0),
                    duration=float(d.get("duration", 0) or 0),
                    poster_url=d.get("poster", "") or "",
                )
                for d in raw_list
            ]
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 演职人员 ──

    def get_persons(self, guid):
        try:
            resp = self._client.get_person_list(guid)
            persons = resp.get("list", []) if isinstance(resp, dict) else []
            return [
                MediaPerson(
                    name=p.get("name", ""),
                    role=p.get("role", ""),
                    profile_url=p.get("profile_path", ""),
                )
                for p in persons
            ]
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 播放记录 ──

    def get_play_records(self):
        try:
            raw_list = self._client.get_play_list()
            return [
                PlayRecord(
                    guid=d.get("guid", ""),
                    title=d.get("title", ""),
                    tv_title=d.get("tv_title", ""),
                    media_type=d.get("type", ""),
                    poster_url=d.get("poster", ""),
                    season_number=int(d.get("season_number", 0) or 0),
                    episode_number=int(d.get("episode_number", 0) or 0),
                    duration=float(d.get("duration", 0) or 0),
                    timestamp=float(d.get("ts", 0) or 0),
                )
                for d in raw_list
            ]
        except FnosApiError as e:
            raise self._wrap_error(e)

    def delete_play_record(self, guid):
        try:
            self._client.delete_play_record(guid)
        except FnosApiError as e:
            raise self._wrap_error(e)

    # ── 图片 ──

    def get_poster_url(self, guid, thumb=False):
        """通过 item detail 获取海报真实 URL"""
        raw = self._client.get_item_detail(guid)
        posters_path = raw.get("posters", "") or ""
        if not posters_path:
            return ""
        return self._client.get_image_url(posters_path)

    def download_poster(self, guid, output_dir=".", thumb=False):
        # type: (str, str, bool) -> List[str]
        """
        下载影片海报和背景图。
        从 item detail 中读取 posters / backdrops 路径，使用 title 作为文件名。
        返回保存的文件路径列表。
        """
        try:
            raw = self._client.get_item_detail(guid)
        except FnosApiError as e:
            raise self._wrap_error(e)

        title = raw.get("title", "") or guid
        title_safe = _sanitize_filename(title)
        posters_path = raw.get("posters", "") or ""
        backdrops_path = raw.get("backdrops", "") or ""

        saved = []

        if posters_path:
            ext = _get_ext(posters_path)
            url = self._client.get_image_url(posters_path)
            out = os.path.join(output_dir, "{}-poster.{}".format(title_safe, ext))
            self._client.download_image(url, output_path=out)
            saved.append(out)

        if backdrops_path:
            ext = _get_ext(backdrops_path)
            url = self._client.get_image_url(backdrops_path)
            out = os.path.join(output_dir, "{}-backdrop.{}".format(title_safe, ext))
            self._client.download_image(url, output_path=out)
            saved.append(out)

        if not saved:
            raise MediaProviderError(-6, "该影片没有可用的海报或背景图")

        return saved
