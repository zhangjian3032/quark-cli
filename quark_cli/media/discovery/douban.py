"""
豆瓣 (Douban) 数据源实现

使用两套 API:
  - Web JSON 接口 (无需认证): 搜索、分类浏览
  - Frodo 小程序接口: 详情、榜单/合集

Frodo 接口需要:
  - User-Agent: MicroMessenger/...
  - Referer: https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html
  - apiKey=0ac44ae016490db2204ce0a042db2916
"""

import logging
import time
import requests

from quark_cli.media.discovery.base import (
    DiscoveryItem,
    DiscoveryResult,
    DiscoverySource,
    PersonItem,
    PersonResult,
)

logger = logging.getLogger("quark_cli.discovery.douban")

# ── 常量 ──

_FRODO_BASE = "https://frodo.douban.com/api/v2"
_FRODO_API_KEY = "0ac44ae016490db2204ce0a042db2916"
_FRODO_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Mobile/15E148 MicroMessenger/8.0.38(0x18002627) "
    "NetType/WIFI Language/zh_CN"
)
_FRODO_REFERER = "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html"

_WEB_BASE = "https://movie.douban.com"

# ── 合集映射 ──

_COLLECTION_MAP = {
    # get_popular
    "movie_popular": "movie_real_time_hotest",
    "tv_popular": "tv_real_time_hotest",
    # get_top_rated
    "movie_top": "movie_top250",
    "tv_top": "tv_real_time_hotest",
    # get_trending
    "movie_trending": "movie_weekly_best",
    "tv_trending": "tv_real_time_hotest",
}

# Web 标签 (用于 discover)
_WEB_TAGS = {
    "movie": [
        "热门", "最新", "经典", "豆瓣高分", "冷门佳片",
        "华语", "欧美", "日本", "韩国",
        "喜剧", "动作", "爱情", "科幻", "悬疑", "恐怖",
        "动画", "纪录片", "剧情", "犯罪",
    ],
    "tv": [
        "热门", "国产剧", "美剧", "英剧", "韩剧", "日剧",
        "日本动画", "综艺", "纪录片",
    ],
}

# 类型映射 (豆瓣中文 genre → 统一 id)
_GENRE_MAP_MOVIE = {
    "剧情": "1", "喜剧": "2", "动作": "3", "爱情": "4",
    "科幻": "5", "悬疑": "6", "惊悚": "7", "恐怖": "8",
    "犯罪": "9", "动画": "10", "奇幻": "11", "冒险": "12",
    "战争": "13", "传记": "14", "历史": "15", "音乐": "16",
    "歌舞": "17", "家庭": "18", "儿童": "19", "纪录片": "20",
    "短片": "21", "古装": "22", "武侠": "23", "西部": "24",
    "灾难": "25", "情色": "26", "运动": "27", "黑色电影": "28",
}

_GENRE_MAP_TV = {
    "剧情": "1", "喜剧": "2", "动作": "3", "爱情": "4",
    "科幻": "5", "悬疑": "6", "惊悚": "7", "恐怖": "8",
    "犯罪": "9", "动画": "10", "奇幻": "11", "冒险": "12",
    "战争": "13", "传记": "14", "历史": "15", "音乐": "16",
    "家庭": "18", "儿童": "19", "纪录片": "20", "古装": "22",
    "武侠": "23", "真人秀": "29", "脱口秀": "30",
}


class DoubanError(Exception):
    """豆瓣 API 错误"""

    def __init__(self, code=0, message=""):
        self.code = code
        self.message = message
        super().__init__("[Douban-{}] {}".format(code, message))


def _parse_frodo_detail(raw, media_type="movie"):
    """将 Frodo 详情 API 返回的 dict 转为 DiscoveryItem"""
    title = raw.get("title", "")
    original_title = raw.get("original_title", "") or raw.get("title", "")
    year_str = str(raw.get("year", ""))

    # 评分
    rating_obj = raw.get("rating", {}) or {}
    rating = float(rating_obj.get("value", 0) or 0)
    vote_count = int(rating_obj.get("count", 0) or 0)

    # 类型
    genres = raw.get("genres", [])

    # 海报
    poster = ""
    pic_obj = raw.get("pic", {}) or {}
    if pic_obj.get("large"):
        poster = pic_obj["large"]
    elif pic_obj.get("normal"):
        poster = pic_obj["normal"]
    elif raw.get("cover_url"):
        poster = raw["cover_url"]
    elif raw.get("cover", {}).get("url"):
        poster = raw["cover"]["url"]

    # 背景图
    backdrop = ""
    if raw.get("extra", {}).get("backdrop_url"):
        backdrop = raw["extra"]["backdrop_url"]

    # 简介
    overview = raw.get("intro", "") or raw.get("card_subtitle", "")

    # 演职员
    credits = {}
    directors = raw.get("directors", [])
    actors = raw.get("actors", [])
    if directors or actors:
        credits["crew"] = [
            {"name": d.get("name", ""), "job": "Director", "department": "Directing"}
            for d in directors[:5]
        ]
        credits["cast"] = [
            {"name": a.get("name", ""), "character": a.get("character", ""), "order": i}
            for i, a in enumerate(actors[:20])
        ]

    # 国家/地区
    countries = raw.get("countries", [])

    # 语言
    languages = raw.get("languages", [])
    original_language = languages[0] if languages else ""

    # 时长
    durations = raw.get("durations", [])
    runtime = 0
    if durations:
        dur_str = durations[0]
        digits = "".join(c for c in dur_str if c.isdigit())
        if digits:
            runtime = int(digits)

    return DiscoveryItem(
        source_id=str(raw.get("id", "")),
        title=title,
        original_title=original_title,
        year=year_str,
        media_type=media_type,
        rating=rating,
        vote_count=vote_count,
        overview=overview,
        poster_path=poster,
        backdrop_path=backdrop,
        genres=genres,
        original_language=original_language,
        origin_country=countries,
        imdb_id="",
        runtime=runtime,
        status="",
        tagline=raw.get("card_subtitle", ""),
        credits=credits,
        extra={
            "douban_url": "https://movie.douban.com/subject/{}/".format(raw.get("id", "")),
            "douban_id": str(raw.get("id", "")),
            "subtype": raw.get("subtype", ""),
        },
    )


def _parse_collection_item(raw, media_type="movie"):
    """将合集列表项转为 DiscoveryItem"""
    title = raw.get("title", "")
    year_str = str(raw.get("year", ""))

    rating_obj = raw.get("rating", {}) or {}
    rating = float(rating_obj.get("value", 0) or 0)
    vote_count = int(rating_obj.get("count", 0) or 0)

    poster = ""
    pic_obj = raw.get("pic", {}) or {}
    if pic_obj.get("large"):
        poster = pic_obj["large"]
    elif pic_obj.get("normal"):
        poster = pic_obj["normal"]
    elif raw.get("cover_url"):
        poster = raw["cover_url"]
    elif raw.get("cover", {}).get("url"):
        poster = raw["cover"]["url"]

    if not poster and isinstance(raw.get("cover"), str):
        poster = raw["cover"]

    return DiscoveryItem(
        source_id=str(raw.get("id", "")),
        title=title,
        original_title=raw.get("original_title", "") or title,
        year=year_str,
        media_type=media_type,
        rating=rating,
        vote_count=vote_count,
        overview=raw.get("card_subtitle", "") or raw.get("intro", ""),
        poster_path=poster,
        genres=raw.get("genres", []),
        extra={
            "douban_url": "https://movie.douban.com/subject/{}/".format(raw.get("id", "")),
            "douban_id": str(raw.get("id", "")),
        },
    )


def _parse_web_search_item(raw, media_type="movie"):
    """将 /j/subject_suggest 返回的项转为 DiscoveryItem"""
    return DiscoveryItem(
        source_id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        original_title=raw.get("sub_title", "") or raw.get("title", ""),
        year=str(raw.get("year", "")),
        media_type=media_type,
        poster_path=raw.get("img", ""),
        extra={
            "douban_url": "https://movie.douban.com/subject/{}/".format(raw.get("id", "")),
            "douban_id": str(raw.get("id", "")),
        },
    )


def _parse_web_browse_item(raw, media_type="movie"):
    """将 /j/search_subjects 返回的项转为 DiscoveryItem"""
    rate_val = 0.0
    try:
        rate_val = float(raw.get("rate", 0) or 0)
    except (ValueError, TypeError):
        pass

    return DiscoveryItem(
        source_id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        media_type=media_type,
        rating=rate_val,
        poster_path=raw.get("cover", ""),
        extra={
            "douban_url": raw.get("url", ""),
            "douban_id": str(raw.get("id", "")),
        },
    )


class DoubanSource(DiscoverySource):
    """豆瓣数据源"""

    def __init__(self, timeout=15):
        self._timeout = timeout
        self._session = requests.Session()
        self._frodo_headers = {
            "User-Agent": _FRODO_UA,
            "Referer": _FRODO_REFERER,
            "Accept": "application/json",
        }
        self._web_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": "https://movie.douban.com/",
        }
        self._last_request_time = 0

    @property
    def source_name(self):
        return "douban"

    # ── 限速 ──

    def _throttle(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < 0.3:
            time.sleep(0.3 - elapsed)
        self._last_request_time = time.time()

    # ── HTTP ──

    def _frodo_get(self, path, params=None):
        self._throttle()
        if params is None:
            params = {}
        params.setdefault("apiKey", _FRODO_API_KEY)

        url = "{}{}".format(_FRODO_BASE, path)
        try:
            resp = self._session.get(
                url, params=params, headers=self._frodo_headers, timeout=self._timeout
            )
        except requests.RequestException as e:
            raise DoubanError(0, "网络请求失败: {}".format(e))

        if resp.status_code == 404:
            raise DoubanError(404, "资源不存在")
        if resp.status_code >= 400:
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            msg = body.get("msg", "") or body.get("localized_message", "") or resp.text[:200]
            raise DoubanError(resp.status_code, msg)

        return resp.json()

    def _web_get(self, path, params=None):
        self._throttle()
        if params is None:
            params = {}

        url = "{}{}".format(_WEB_BASE, path)
        try:
            resp = self._session.get(
                url, params=params, headers=self._web_headers, timeout=self._timeout
            )
        except requests.RequestException as e:
            raise DoubanError(0, "网络请求失败: {}".format(e))

        if resp.status_code >= 400:
            raise DoubanError(resp.status_code, "Web API 错误: {}".format(resp.status_code))

        return resp.json()

    # ── 搜索 ──

    def search(self, query, media_type="movie", page=1, year=None):
        data = self._web_get("/j/subject_suggest", {"q": query})

        if not isinstance(data, list):
            return DiscoveryResult(items=[], total=0, page=1, total_pages=1)

        items = []
        for raw in data:
            item = _parse_web_search_item(raw, media_type)
            if year and item.year and str(year) != item.year:
                continue
            items.append(item)

        return DiscoveryResult(
            items=items,
            total=len(items),
            page=1,
            total_pages=1,
        )

    # ── 详情 ──

    def get_detail(self, source_id, media_type="movie"):
        path = "/{}/{}".format(media_type, source_id)
        data = self._frodo_get(path)
        return _parse_frodo_detail(data, media_type)

    # ── 通过外部 ID 查找 ──

    def find_by_external_id(self, external_id, external_source="imdb_id"):
        if external_source == "imdb_id":
            result = self.search(external_id)
            if result.items:
                first = result.items[0]
                return self.get_detail(first.source_id, first.media_type)
        raise DoubanError(404, "豆瓣暂不支持通过 {} 查找".format(external_source))

    # ── 热门 ──

    def get_popular(self, media_type="movie", page=1):
        coll_key = "{}_popular".format(media_type)
        collection = _COLLECTION_MAP.get(coll_key, "movie_real_time_hotest")
        return self._get_collection(collection, media_type, page)

    # ── 高分 ──

    def get_top_rated(self, media_type="movie", page=1):
        coll_key = "{}_top".format(media_type)
        collection = _COLLECTION_MAP.get(coll_key, "movie_top250")
        return self._get_collection(collection, media_type, page)

    # ── 趋势 ──

    def get_trending(self, media_type="movie", time_window="week"):
        coll_key = "{}_trending".format(media_type)
        collection = _COLLECTION_MAP.get(coll_key, "movie_weekly_best")
        return self._get_collection(collection, media_type, page=1)

    # ── 高级发现 ──

    def discover(self, media_type="movie", page=1, **filters):
        """
        高级筛选 — 使用 Web /j/search_subjects

        filters:
          - tag: str        (标签名, 如 "热门"/"科幻"/"美剧")
          - sort: str       (排序: "recommend"/"time"/"rank")
          - min_rating: float
          - genre: str      (类型名, 映射为 tag)
          - country: str    (国家, 映射为 tag)
        """
        page_limit = 20
        page_start = (page - 1) * page_limit

        tag = filters.get("tag", "")
        if not tag:
            genre = filters.get("genre", "")
            country = filters.get("country", "")
            if genre:
                genre_map = _GENRE_MAP_MOVIE if media_type == "movie" else _GENRE_MAP_TV
                id_to_name = {v: k for k, v in genre_map.items()}
                if genre in id_to_name:
                    tag = id_to_name[genre]
                else:
                    first_genre = genre.split(",")[0].strip()
                    if first_genre in id_to_name:
                        tag = id_to_name[first_genre]
                    elif first_genre in genre_map:
                        tag = first_genre
                    else:
                        tag = first_genre
            elif country:
                country_tag_map = {
                    "CN": "华语", "US": "欧美", "JP": "日本", "KR": "韩国",
                    "GB": "欧美", "FR": "欧美", "DE": "欧美",
                }
                tag = country_tag_map.get(country.upper(), country)

        if not tag:
            tag = "热门"

        sort = filters.get("sort", "recommend")

        params = {
            "type": media_type,
            "tag": tag,
            "page_limit": page_limit,
            "page_start": page_start,
            "sort": sort,
        }

        data = self._web_get("/j/search_subjects", params)
        subjects = data.get("subjects", [])

        items = [_parse_web_browse_item(s, media_type) for s in subjects]

        min_rating = filters.get("min_rating")
        if min_rating:
            min_r = float(min_rating)
            items = [it for it in items if it.rating >= min_r]

        has_more = len(subjects) >= page_limit
        estimated_total = page_start + len(subjects) + (page_limit if has_more else 0)

        return DiscoveryResult(
            items=items,
            total=estimated_total,
            page=page,
            total_pages=page + (1 if has_more else 0),
        )

    # ── 类型列表 ──

    def get_genres(self, media_type="movie"):
        genre_map = _GENRE_MAP_MOVIE if media_type == "movie" else _GENRE_MAP_TV
        return {v: k for v, k in sorted(genre_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)}

    # ── 海报 URL ──

    def get_poster_url(self, path, size="w500"):
        return path or ""

    # ── 辅助 ──

    def get_available_tags(self, media_type="movie"):
        return _WEB_TAGS.get(media_type, _WEB_TAGS["movie"])

    def get_available_collections(self, media_type="movie"):
        if media_type == "tv":
            return [
                "tv_hot", "tv_real_time_hotest", "tv_domestic",
                "tv_american", "tv_korean", "tv_japanese",
            ]
        return [
            "movie_showing", "movie_real_time_hotest",
            "movie_weekly_best", "movie_top250", "movie_soon",
            "movie_scifi", "movie_comedy", "movie_action",
        ]

    def _get_collection(self, collection_name, media_type="movie", page=1):
        count = 20
        start = (page - 1) * count

        path = "/subject_collection/{}/items".format(collection_name)
        data = self._frodo_get(path, {"start": start, "count": count})

        raw_items = data.get("subject_collection_items", [])
        total = int(data.get("total", 0))

        items = []
        for raw in raw_items:
            item_data = raw
            if "subject" in raw and isinstance(raw["subject"], dict):
                item_data = raw["subject"]
            items.append(_parse_collection_item(item_data, media_type))

        total_pages = max(1, (total + count - 1) // count)

        return DiscoveryResult(
            items=items,
            total=total,
            page=page,
            total_pages=total_pages,
        )


    # ── 演员/人物 ──

    def search_person(self, query, page=1):
        # type: (str, int) -> PersonResult
        """搜索演员 (豆瓣 Frodo 微信搜索接口)"""
        count = 20
        start = (page - 1) * count
        try:
            data = self._frodo_get(
                "/search/weixin",
                {"q": query, "type": "celebrity", "start": start, "count": count},
            )
        except DoubanError:
            return PersonResult()

        raw_items = data.get("items", [])
        total = int(data.get("total", 0))
        items = []
        for raw in raw_items:
            target = raw.get("target", {})
            if not target:
                continue
            # 头像
            avatar = ""
            cover = target.get("cover_url", "") or ""
            if not cover:
                av_obj = target.get("avatar", {}) or {}
                cover = av_obj.get("large", "") or av_obj.get("normal", "") or ""
            avatar = cover

            items.append(PersonItem(
                person_id=str(target.get("id", "")),
                name=target.get("title", "") or target.get("name", ""),
                original_name=target.get("latin_name", "") or target.get("title", ""),
                gender=0,
                profile_path=avatar,
                known_for_department=target.get("abstract", ""),
                popularity=0.0,
                extra={
                    "douban_url": "https://movie.douban.com/celebrity/{}/".format(target.get("id", "")),
                    "abstract": target.get("abstract", ""),
                },
            ))
        total_pages = max(1, (total + count - 1) // count)
        return PersonResult(items=items, total=total, page=page, total_pages=total_pages)

    def get_person_credits(self, person_id, media_type=None):
        # type: (str, str) -> list
        """获取演员参演作品 (豆瓣影人作品, 按评分排序)"""
        items = []
        start = 0
        count = 50
        while True:
            try:
                data = self._frodo_get(
                    "/celebrity/{}/works".format(person_id),
                    {"start": start, "count": count, "sort": "vote"},
                )
            except DoubanError:
                break

            raw_items = data.get("works", [])
            total = int(data.get("total", 0))
            for raw in raw_items:
                subject = raw.get("subject", {})
                if not subject:
                    continue
                mt = "tv" if subject.get("subtype") == "tv" else "movie"
                if media_type and mt != media_type:
                    continue
                item = _parse_collection_item(subject, mt)
                # 附加角色信息
                roles = raw.get("roles", [])
                if roles:
                    item.extra["character"] = " / ".join(roles)
                items.append(item)
            start += count
            if start >= total or not raw_items:
                break
        return items

    def get_collection(self, collection_name, media_type="movie", page=1):
        return self._get_collection(collection_name, media_type, page)
