"""Service 层 - 影视发现业务逻辑 (支持多数据源: TMDB / 豆瓣)"""


class DiscoveryService:
    """元数据查询 + 高分推荐 Service"""

    def __init__(self, source):
        self._source = source

    @property
    def source_name(self):
        return self._source.source_name

    def meta_search(self, query, media_type="movie", year=None, base_path="/媒体"):
        """按关键词搜索元数据，返回完整详情 + 建议"""
        from quark_cli.media.discovery.naming import (
            suggest_search_keywords, suggest_save_path, format_meta_summary,
        )

        # 搜索 + fallback
        result = self._source.search(query, media_type=media_type, page=1, year=year)
        actual_type = media_type
        if not result.items:
            alt = "tv" if media_type == "movie" else "movie"
            result = self._source.search(query, media_type=alt, page=1, year=year)
            if result.items:
                actual_type = alt

        if not result.items:
            return {"error": "未找到匹配 '{}' 的影视作品".format(query), "results": []}

        first = result.items[0]
        item = self._source.get_detail(first.source_id, actual_type)

        # resolve genre ids (TMDB 列表页只返回 genre_ids)
        if item.genres and isinstance(item.genres[0], int):
            try:
                if hasattr(self._source, "resolve_genre_names"):
                    item.genres = self._source.resolve_genre_names(item.genres, actual_type)
            except Exception:
                pass

        keywords = suggest_search_keywords(item)
        paths = suggest_save_path(item, base_path=base_path)
        summary = format_meta_summary(item)

        if item.poster_path:
            summary["poster_url"] = self._source.get_poster_url(item.poster_path)
        if item.backdrop_path:
            summary["backdrop_url"] = self._source.get_poster_url(item.backdrop_path, "w1280")

        # 来源信息
        summary["source"] = self._source.source_name
        summary["source_id"] = item.source_id

        other_results = []
        for it in result.items[1:6]:
            other_results.append({
                "source_id": it.source_id,
                "title": it.title,
                "year": it.year,
                "rating": it.rating,
            })

        return {
            "source": self._source.source_name,
            "meta": summary,
            "media_type": actual_type,
            "search_keywords": keywords,
            "save_paths": paths,
            "other_results": other_results,
        }

    def meta_by_id(self, source_id, media_type="movie", base_path="/媒体"):
        """通过 source_id 获取详情 (兼容 tmdb_id / douban_id)"""
        from quark_cli.media.discovery.naming import (
            suggest_search_keywords, suggest_save_path, format_meta_summary,
        )

        item = self._source.get_detail(source_id, media_type)
        if item.genres and isinstance(item.genres[0], int):
            try:
                if hasattr(self._source, "resolve_genre_names"):
                    item.genres = self._source.resolve_genre_names(item.genres, media_type)
            except Exception:
                pass

        keywords = suggest_search_keywords(item)
        paths = suggest_save_path(item, base_path=base_path)
        summary = format_meta_summary(item)

        if item.poster_path:
            summary["poster_url"] = self._source.get_poster_url(item.poster_path)
        if item.backdrop_path:
            summary["backdrop_url"] = self._source.get_poster_url(item.backdrop_path, "w1280")

        summary["source"] = self._source.source_name
        summary["source_id"] = item.source_id

        return {
            "source": self._source.source_name,
            "meta": summary,
            "media_type": media_type,
            "search_keywords": keywords,
            "save_paths": paths,
        }

    # 保持向后兼容
    def meta_by_tmdb_id(self, tmdb_id, media_type="movie", base_path="/媒体"):
        return self.meta_by_id(tmdb_id, media_type, base_path)

    def discover(self, list_type="top_rated", media_type="movie", page=1,
                 min_rating=None, genre=None, year=None, country=None,
                 sort_by="vote_average.desc", min_votes=50, window="week",
                 tag=None):
        """高分影视推荐列表"""

        # genre 中文 → id (仅 TMDB 需要)
        genre_ids = None
        if genre and hasattr(self._source, "resolve_genre_ids"):
            parts = [g.strip() for g in genre.split(",")]
            if all(p.isdigit() for p in parts):
                genre_ids = genre
            else:
                genre_ids = self._source.resolve_genre_ids(parts, media_type)
        elif genre:
            genre_ids = genre

        if list_type == "popular":
            result = self._source.get_popular(media_type, page)
        elif list_type == "top_rated":
            result = self._source.get_top_rated(media_type, page)
        elif list_type == "trending":
            result = self._source.get_trending(media_type, window)
        elif list_type == "collection" and hasattr(self._source, "get_collection"):
            # 豆瓣合集直接访问
            coll_name = tag or "movie_real_time_hotest"
            result = self._source.get_collection(coll_name, media_type, page)
        else:
            filters = {"sort_by": sort_by, "min_votes": min_votes}
            if min_rating is not None:
                filters["min_rating"] = min_rating
            if genre_ids:
                filters["genre"] = genre_ids
            if year:
                filters["year"] = year
            if country:
                filters["country"] = country
            # 豆瓣特有: tag
            if tag:
                filters["tag"] = tag
            result = self._source.discover(media_type, page, **filters)

        # resolve genres
        for it in result.items:
            if it.genres and isinstance(it.genres[0], int):
                try:
                    if hasattr(self._source, "resolve_genre_names"):
                        it.genres = self._source.resolve_genre_names(it.genres, media_type)
                except Exception:
                    pass

        items = []
        for it in result.items:
            item_dict = {
                "source_id": it.source_id,
                "title": it.title,
                "original_title": it.original_title,
                "year": it.year,
                "rating": it.rating,
                "vote_count": it.vote_count,
                "genres": it.genres,
                "overview": (it.overview or "")[:200],
                "poster_url": self._source.get_poster_url(it.poster_path) if it.poster_path else "",
            }
            # 向后兼容: TMDB 时同时输出 tmdb_id
            if self._source.source_name == "tmdb":
                item_dict["tmdb_id"] = it.source_id
            elif self._source.source_name == "douban":
                item_dict["douban_id"] = it.source_id
            items.append(item_dict)

        return {
            "source": self._source.source_name,
            "list_type": list_type,
            "media_type": media_type,
            "page": result.page,
            "total_pages": result.total_pages,
            "total": result.total,
            "items": items,
        }


    # ── 演员/人物 ──

    def person_search(self, query, page=1):
        """搜索演员, 返回 dict"""
        result = self._source.search_person(query, page=page)
        items = []
        for p in result.items:
            entry = {
                "person_id": p.person_id,
                "name": p.name,
                "original_name": p.original_name,
                "known_for_department": p.known_for_department,
                "popularity": p.popularity,
            }
            if p.profile_path:
                entry["profile_url"] = self._source.get_poster_url(p.profile_path)
            if p.known_for:
                entry["known_for"] = [
                    {
                        "source_id": kf.source_id,
                        "title": kf.title,
                        "year": kf.year,
                        "rating": kf.rating,
                        "media_type": kf.media_type,
                    }
                    for kf in p.known_for[:3]
                ]
            items.append(entry)
        return {
            "source": self._source.source_name,
            "results": items,
            "total": result.total,
            "page": result.page,
            "total_pages": result.total_pages,
        }

    def person_credits(self, person_id, media_type=None):
        """获取演员参演作品, 返回 dict"""
        credits_list = self._source.get_person_credits(person_id, media_type=media_type)

        # resolve genres
        for it in credits_list:
            if it.genres and isinstance(it.genres[0], int):
                try:
                    if hasattr(self._source, "resolve_genre_names"):
                        it.genres = self._source.resolve_genre_names(it.genres, it.media_type)
                except Exception:
                    pass

        items = []
        for it in credits_list:
            entry = {
                "source_id": it.source_id,
                "title": it.title,
                "original_title": it.original_title,
                "year": it.year,
                "media_type": it.media_type,
                "rating": it.rating,
                "vote_count": it.vote_count,
                "genres": it.genres if isinstance(it.genres, list) and it.genres and isinstance(it.genres[0], str) else [],
                "poster_url": self._source.get_poster_url(it.poster_path) if it.poster_path else "",
            }
            if it.extra.get("character"):
                entry["character"] = it.extra["character"]
            if it.extra.get("job"):
                entry["job"] = it.extra["job"]
            items.append(entry)

        return {
            "source": self._source.source_name,
            "person_id": person_id,
            "total": len(items),
            "credits": items,
        }

    def get_genres(self, media_type="movie"):
        genres_map = self._source.get_genres(media_type)
        return [{"id": k, "name": v} for k, v in sorted(genres_map.items())]

    def get_available_tags(self, media_type="movie"):
        """获取可用标签 (豆瓣特有)"""
        if hasattr(self._source, "get_available_tags"):
            return self._source.get_available_tags(media_type)
        return []
