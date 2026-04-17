"""Service 层 - 影视媒体中心业务逻辑 (三端共用)"""


class MediaService:
    """影视媒体中心 Service — CLI / API / Web 共享"""

    def __init__(self, provider):
        self._provider = provider

    # ── 媒体库 ──

    def list_libraries(self):
        libs = self._provider.get_libraries()
        return [
            {"guid": l.guid, "title": l.title, "category": l.category, "count": l.count}
            for l in libs
        ]

    def get_library_items(self, lib_name_or_guid, page=1, page_size=20):
        libs = self._provider.get_libraries()
        target = None
        for lib in libs:
            if lib.title == lib_name_or_guid or lib.guid.startswith(lib_name_or_guid):
                target = lib
                break
        if not target:
            return {"error": "未找到媒体库: {}".format(lib_name_or_guid)}

        result = self._provider.get_items(library_guid=target.guid, page=page, page_size=page_size)
        return {
            "library": {"guid": target.guid, "title": target.title, "category": target.category},
            "total": result.total,
            "page": page,
            "items": [self._item_dict(it) for it in result.items],
        }

    # ── 搜索 ──

    def search(self, keyword, page=1, page_size=20):
        result = self._provider.search_items(keyword=keyword, page=page, page_size=page_size)
        return {
            "keyword": keyword,
            "total": result.total,
            "page": page,
            "items": [self._item_dict(it) for it in result.items],
        }

    # ── 详情 ──

    def get_detail(self, guid):
        detail = self._provider.get_item_detail(guid)
        d = self._item_dict(detail)
        if detail.overview:
            d["overview"] = detail.overview
        return d

    def get_detail_full(self, guid, include_seasons=False, include_cast=False):
        detail = self._provider.get_item_detail(guid)
        d = self._item_dict(detail)
        if detail.overview:
            d["overview"] = detail.overview

        if include_seasons:
            try:
                seasons = self._provider.get_seasons(guid)
                d["seasons"] = [
                    {"guid": s.guid, "title": s.title,
                     "season_number": s.season_number, "episode_count": s.episode_count}
                    for s in seasons
                ]
            except Exception:
                d["seasons"] = []

        if include_cast:
            try:
                persons = self._provider.get_persons(guid)
                d["cast"] = [{"name": p.name, "role": p.role} for p in persons]
            except Exception:
                d["cast"] = []

        return d

    # ── 海报 ──

    def download_poster(self, guid, output_dir="."):
        saved = self._provider.download_poster(guid, output_dir=output_dir)
        return {"files": saved, "guid": guid}

    def get_poster_url(self, guid):
        """获取海报 URL (不下载, 用于 Web 展示)"""
        raw = self._provider._client.get_item_detail(guid)
        posters_path = raw.get("posters", "") or ""
        backdrops_path = raw.get("backdrops", "") or ""
        result = {"guid": guid}
        if posters_path:
            result["poster_url"] = self._provider._client.get_image_url(posters_path)
        if backdrops_path:
            result["backdrop_url"] = self._provider._client.get_image_url(backdrops_path)
        return result

    # ── 播放记录 ──

    def get_play_records(self):
        records = self._provider.get_play_records()
        items = []
        for r in records:
            title = r.tv_title or r.title
            if r.season_number or r.episode_number:
                title += " S{:02d}E{:02d}".format(r.season_number or 0, r.episode_number or 0)
            items.append({
                "guid": r.guid,
                "title": title,
                "media_type": r.media_type or "",
                "duration": r.duration,
            })
        return items

    # ── 导出 ──

    def export_items(self, library_name="", fmt="json", output_path="export.json"):
        return self._provider.export_items(
            library_name=library_name, fmt=fmt, output_path=output_path
        )

    # ── 状态 ──

    def get_status(self):
        user_info = self._provider.get_user_info()
        return {
            "provider": self._provider.provider_name,
            "base_url": self._provider.base_url,
            "user": user_info,
        }

    # ── 工具方法 ──

    @staticmethod
    def _item_dict(item):
        return {
            "guid": item.guid,
            "title": item.title,
            "year": item.year or "",
            "rating": item.rating,
            "media_type": item.media_type or "",
            "original_title": getattr(item, "original_title", ""),
            "overview": getattr(item, "overview", ""),
        }
