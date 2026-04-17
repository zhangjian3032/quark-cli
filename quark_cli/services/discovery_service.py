"""Service 层 - TMDB 影视发现业务逻辑 (三端共用)"""


class DiscoveryService:
    """TMDB 元数据查询 + 高分推荐 Service"""

    def __init__(self, tmdb_source):
        self._source = tmdb_source

    def meta_search(self, query, media_type="movie", year=None, base_path="/媒体"):
        """按关键词搜索 TMDB 元数据，返回完整详情 + 建议"""
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

        # resolve genre ids
        if item.genres and isinstance(item.genres[0], int):
            try:
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

        other_results = []
        for it in result.items[1:6]:
            other_results.append({
                "tmdb_id": it.source_id,
                "title": it.title,
                "year": it.year,
                "rating": it.rating,
            })

        return {
            "meta": summary,
            "media_type": actual_type,
            "search_keywords": keywords,
            "save_paths": paths,
            "other_results": other_results,
        }

    def meta_by_tmdb_id(self, tmdb_id, media_type="movie", base_path="/媒体"):
        from quark_cli.media.discovery.naming import (
            suggest_search_keywords, suggest_save_path, format_meta_summary,
        )

        item = self._source.get_detail(tmdb_id, media_type)
        if item.genres and isinstance(item.genres[0], int):
            try:
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

        return {
            "meta": summary,
            "media_type": media_type,
            "search_keywords": keywords,
            "save_paths": paths,
        }

    def discover(self, list_type="top_rated", media_type="movie", page=1,
                 min_rating=None, genre=None, year=None, country=None,
                 sort_by="vote_average.desc", min_votes=50, window="week"):
        """高分影视推荐列表"""
        # genre 中文 → id
        genre_ids = None
        if genre:
            parts = [g.strip() for g in genre.split(",")]
            if all(p.isdigit() for p in parts):
                genre_ids = genre
            else:
                genre_ids = self._source.resolve_genre_ids(parts, media_type)

        if list_type == "popular":
            result = self._source.get_popular(media_type, page)
        elif list_type == "top_rated":
            result = self._source.get_top_rated(media_type, page)
        elif list_type == "trending":
            result = self._source.get_trending(media_type, window)
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
            result = self._source.discover(media_type, page, **filters)

        # resolve genres
        for it in result.items:
            if it.genres and isinstance(it.genres[0], int):
                try:
                    it.genres = self._source.resolve_genre_names(it.genres, media_type)
                except Exception:
                    pass

        items = []
        for it in result.items:
            items.append({
                "tmdb_id": it.source_id,
                "title": it.title,
                "original_title": it.original_title,
                "year": it.year,
                "rating": it.rating,
                "vote_count": it.vote_count,
                "genres": it.genres,
                "overview": (it.overview or "")[:200],
                "poster_url": self._source.get_poster_url(it.poster_path) if it.poster_path else "",
            })

        return {
            "list_type": list_type,
            "media_type": media_type,
            "page": result.page,
            "total_pages": result.total_pages,
            "total": result.total,
            "items": items,
        }

    def get_genres(self, media_type="movie"):
        genres_map = self._source.get_genres(media_type)
        return [{"id": k, "name": v} for k, v in sorted(genres_map.items())]
