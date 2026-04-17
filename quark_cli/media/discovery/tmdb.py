"""
TMDB (The Movie Database) 数据源实现
API v3 文档: https://developer.themoviedb.org/reference
"""

import requests

from quark_cli.media.discovery.base import (
    DiscoveryItem,
    DiscoveryResult,
    DiscoverySource,
)

# TMDB API v3 base
_API_BASE = "https://api.themoviedb.org/3"
_IMG_BASE = "https://image.tmdb.org/t/p"


class TmdbError(Exception):
    """TMDB API 错误"""

    def __init__(self, code=0, message=""):
        self.code = code
        self.message = message
        super().__init__("[TMDB-{}] {}".format(code, message))


def _parse_item(raw, media_type="movie"):
    # type: (dict, str) -> DiscoveryItem
    """将 TMDB API 返回的 dict 转为 DiscoveryItem"""
    if media_type == "tv":
        title = raw.get("name", "")
        original_title = raw.get("original_name", "")
        date_str = raw.get("first_air_date", "") or ""
    else:
        title = raw.get("title", "")
        original_title = raw.get("original_title", "")
        date_str = raw.get("release_date", "") or ""

    year = date_str.split("-", 1)[0] if date_str else ""

    genres = []
    if "genres" in raw:
        genres = [g.get("name", "") for g in raw["genres"]]
    elif "genre_ids" in raw:
        genres = raw["genre_ids"]  # 列表页只有 id, 后续可转名称

    credits = {}
    if "credits" in raw:
        cast_list = raw["credits"].get("cast", [])
        crew_list = raw["credits"].get("crew", [])
        credits = {
            "cast": [
                {
                    "name": c.get("name", ""),
                    "character": c.get("character", ""),
                    "order": c.get("order", 0),
                }
                for c in cast_list[:20]
            ],
            "crew": [
                {
                    "name": c.get("name", ""),
                    "job": c.get("job", ""),
                    "department": c.get("department", ""),
                }
                for c in crew_list
                if c.get("job") in ("Director", "Screenplay", "Writer", "Producer")
            ],
        }

    return DiscoveryItem(
        source_id=str(raw.get("id", "")),
        title=title,
        original_title=original_title,
        year=year,
        media_type=media_type,
        rating=float(raw.get("vote_average", 0) or 0),
        vote_count=int(raw.get("vote_count", 0) or 0),
        overview=raw.get("overview", "") or "",
        poster_path=raw.get("poster_path", "") or "",
        backdrop_path=raw.get("backdrop_path", "") or "",
        genres=genres,
        original_language=raw.get("original_language", ""),
        origin_country=raw.get("origin_country", []),
        imdb_id=raw.get("imdb_id", "") or "",
        runtime=int(raw.get("runtime", 0) or 0),
        status=raw.get("status", ""),
        tagline=raw.get("tagline", "") or "",
        budget=int(raw.get("budget", 0) or 0),
        revenue=int(raw.get("revenue", 0) or 0),
        homepage=raw.get("homepage", "") or "",
        credits=credits,
        extra=raw,
    )


class TmdbSource(DiscoverySource):
    """TMDB 数据源"""

    def __init__(self, api_key, language="zh-CN", region="CN", timeout=15):
        # type: (str, str, str, int) -> None
        if not api_key:
            raise TmdbError(0, "TMDB API Key 未配置。请运行: quark-cli media config --tmdb-key <your_key>")
        self._api_key = api_key
        self._language = language
        self._region = region
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"
        # 缓存 genres
        self._genre_cache = {}

    @property
    def source_name(self):
        return "tmdb"

    # ── HTTP ──

    def _get(self, path, params=None):
        # type: (str, dict) -> dict
        if params is None:
            params = {}
        params.setdefault("api_key", self._api_key)
        params.setdefault("language", self._language)

        url = "{}{}".format(_API_BASE, path)
        resp = self._session.get(url, params=params, timeout=self._timeout)

        if resp.status_code == 401:
            raise TmdbError(401, "API Key 无效，请检查 TMDB API Key 配置")
        if resp.status_code == 404:
            raise TmdbError(404, "资源不存在")
        if resp.status_code == 429:
            raise TmdbError(429, "请求频率过高，请稍后再试")
        if resp.status_code >= 400:
            body = {}
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    body = resp.json()
                except Exception:
                    pass
            raise TmdbError(resp.status_code, body.get("status_message", resp.text[:200]))

        return resp.json()

    def _parse_list_response(self, data, media_type="movie"):
        # type: (dict, str) -> DiscoveryResult
        items = [_parse_item(r, media_type) for r in data.get("results", [])]
        return DiscoveryResult(
            items=items,
            total=int(data.get("total_results", 0)),
            page=int(data.get("page", 1)),
            total_pages=int(data.get("total_pages", 1)),
        )

    # ── 搜索 ──

    def search(self, query, media_type="movie", page=1, year=None):
        params = {"query": query, "page": page}
        if year:
            if media_type == "tv":
                params["first_air_date_year"] = year
            else:
                params["year"] = year

        path = "/search/{}".format(media_type)
        data = self._get(path, params)
        return self._parse_list_response(data, media_type)

    # ── 详情 ──

    def get_detail(self, source_id, media_type="movie"):
        path = "/{}/{}".format(media_type, source_id)
        params = {"append_to_response": "credits,external_ids"}
        data = self._get(path, params)

        # 合并 external_ids 里的 imdb_id
        ext = data.get("external_ids", {})
        if ext.get("imdb_id") and not data.get("imdb_id"):
            data["imdb_id"] = ext["imdb_id"]

        return _parse_item(data, media_type)

    # ── 通过外部 ID 查找 ──

    def find_by_external_id(self, external_id, external_source="imdb_id"):
        data = self._get(
            "/find/{}".format(external_id),
            {"external_source": external_source},
        )
        # 检查 movie_results 和 tv_results
        movies = data.get("movie_results", [])
        tvs = data.get("tv_results", [])
        if movies:
            item = _parse_item(movies[0], "movie")
            # 再取详情补全
            return self.get_detail(item.source_id, "movie")
        if tvs:
            item = _parse_item(tvs[0], "tv")
            return self.get_detail(item.source_id, "tv")
        raise TmdbError(404, "未找到匹配 {} 的影视作品".format(external_id))

    # ── 发现/推荐 ──

    def get_popular(self, media_type="movie", page=1):
        data = self._get("/{}/popular".format(media_type), {"page": page, "region": self._region})
        return self._parse_list_response(data, media_type)

    def get_top_rated(self, media_type="movie", page=1):
        data = self._get("/{}/top_rated".format(media_type), {"page": page, "region": self._region})
        return self._parse_list_response(data, media_type)

    def get_trending(self, media_type="movie", time_window="week"):
        data = self._get("/trending/{}/{}".format(media_type, time_window))
        return self._parse_list_response(data, media_type)

    def discover(self, media_type="movie", page=1, **filters):
        """
        高级筛选。支持的 filters:
          - min_rating: float  (vote_average.gte)
          - max_rating: float  (vote_average.lte)
          - year: int          (primary_release_year / first_air_date_year)
          - genre: str         (genre ids, 逗号分隔)
          - country: str       (with_origin_country)
          - sort_by: str       (默认 vote_average.desc)
          - min_votes: int     (vote_count.gte, 默认 50)
        """
        params = {"page": page, "region": self._region}

        min_rating = filters.get("min_rating")
        max_rating = filters.get("max_rating")
        year = filters.get("year")
        genre = filters.get("genre")
        country = filters.get("country")
        sort_by = filters.get("sort_by", "vote_average.desc")
        min_votes = filters.get("min_votes", 50)

        params["sort_by"] = sort_by
        params["vote_count.gte"] = min_votes

        if min_rating is not None:
            params["vote_average.gte"] = min_rating
        if max_rating is not None:
            params["vote_average.lte"] = max_rating
        if genre:
            params["with_genres"] = genre
        if country:
            params["with_origin_country"] = country

        if year:
            if media_type == "tv":
                params["first_air_date_year"] = year
            else:
                params["primary_release_year"] = year

        data = self._get("/discover/{}".format(media_type), params)
        return self._parse_list_response(data, media_type)

    # ── 类型列表 ──

    def get_genres(self, media_type="movie"):
        cache_key = media_type
        if cache_key in self._genre_cache:
            return self._genre_cache[cache_key]

        data = self._get("/genre/{}/list".format(media_type))
        mapping = {}
        for g in data.get("genres", []):
            mapping[g["id"]] = g["name"]
        self._genre_cache[cache_key] = mapping
        return mapping

    def resolve_genre_names(self, genre_ids, media_type="movie"):
        # type: (list, str) -> list
        """将 genre_id 列表转为名称列表"""
        mapping = self.get_genres(media_type)
        return [mapping.get(gid, str(gid)) for gid in genre_ids]

    def resolve_genre_ids(self, genre_names, media_type="movie"):
        # type: (list, str) -> str
        """将类型名称列表转为逗号分隔的 id 字符串（用于 discover API）"""
        mapping = self.get_genres(media_type)
        name_to_id = {v: k for k, v in mapping.items()}
        ids = []
        for name in genre_names:
            name = name.strip()
            # 直接是数字则保留
            if name.isdigit():
                ids.append(name)
            else:
                gid = name_to_id.get(name)
                if gid is not None:
                    ids.append(str(gid))
        return ",".join(ids)

    # ── 图片 URL ──

    def get_poster_url(self, path, size="w500"):
        if not path:
            return ""
        return "{}/{}/{}".format(_IMG_BASE, size, path.lstrip("/"))
