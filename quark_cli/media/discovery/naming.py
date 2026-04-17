"""
命名与路径建议引擎
根据影视元数据生成:
  1. 网盘搜索关键词建议
  2. 标准化保存路径建议 (Plex / Emby 命名规范)
"""

import re


# ── 常用类型映射 (TMDB 中文名 → 文件夹名) ──
_GENRE_FOLDER_MAP = {
    "动作": "动作",
    "冒险": "冒险",
    "动画": "动画",
    "喜剧": "喜剧",
    "犯罪": "犯罪",
    "纪录": "纪录片",
    "剧情": "剧情",
    "家庭": "家庭",
    "奇幻": "奇幻",
    "历史": "历史",
    "恐怖": "恐怖",
    "音乐": "音乐",
    "悬疑": "悬疑",
    "爱情": "爱情",
    "科幻": "科幻",
    "电视电影": "电视电影",
    "惊悚": "惊悚",
    "战争": "战争",
    "西部": "西部",
}


def _sanitize(name):
    # type: (str) -> str
    """清理文件名中不合法的字符"""
    bad = '<>:"/\\|?*'
    for c in bad:
        name = name.replace(c, " ")
    # 多空格合并
    name = re.sub(r"\s+", " ", name)
    return name.strip().rstrip(".")


def _get_primary_genre(genres):
    # type: (list) -> str
    """从类型列表取第一个作为文件夹名"""
    if not genres:
        return "其他"
    first = genres[0] if isinstance(genres[0], str) else str(genres[0])
    return _GENRE_FOLDER_MAP.get(first, first)


def suggest_search_keywords(item):
    # type: (...) -> list
    """
    根据 DiscoveryItem 生成搜索关键词建议列表。
    返回 list[str]，按推荐优先级排序。

    策略:
    - 中文标题 (最常见的网盘资源命名)
    - 中文标题 + 年份
    - 原始标题 (英文名等)
    - 原始标题 + 年份
    """
    keywords = []
    title = (item.title or "").strip()
    original = (item.original_title or "").strip()
    year = (item.year or "").strip()

    if title:
        keywords.append(title)
        if year:
            keywords.append("{} {}".format(title, year))

    if original and original != title:
        keywords.append(original)
        if year:
            keywords.append("{} {}".format(original, year))

    # 去重保序
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)

    return result


def suggest_save_path(item, base_path="/媒体"):
    # type: (..., str) -> list
    """
    根据 DiscoveryItem 生成标准保存路径建议列表。
    遵循 Plex / Emby 命名规范。

    返回 list[dict]，每个元素:
    {
        "path": "/媒体/电影/科幻/流浪地球2 (2023)",
        "style": "plex",
        "description": "Plex 标准命名"
    }

    路径结构:
      电影: /{base}/电影/{类型}/{标题} ({年份})
      剧集: /{base}/剧集/{类型}/{标题} ({年份})
    """
    title = _sanitize(item.title or item.original_title or "Unknown")
    year = (item.year or "").strip()
    media_type = (item.media_type or "movie").lower()

    genre_names = item.genres or []
    # genre_ids (int 列表) 的场景留给调用方先 resolve
    if genre_names and isinstance(genre_names[0], int):
        primary_genre = "其他"
    else:
        primary_genre = _get_primary_genre(genre_names)

    type_folder = "电影" if media_type == "movie" else "剧集"
    title_folder = "{} ({})".format(title, year) if year else title

    suggestions = []

    # Style 1: 带类型分类
    path1 = "/{}/{}/{}/{}".format(
        base_path.strip("/"), type_folder, primary_genre, title_folder
    )
    suggestions.append({
        "path": path1,
        "style": "categorized",
        "description": "按类型分类: /{}/{}/{}".format(type_folder, primary_genre, title_folder),
    })

    # Style 2: 简洁 (不带类型分类)
    path2 = "/{}/{}/{}".format(
        base_path.strip("/"), type_folder, title_folder
    )
    suggestions.append({
        "path": path2,
        "style": "simple",
        "description": "简洁路径: /{}/{}".format(type_folder, title_folder),
    })

    # Style 3: 英文原名 (如果有)
    original = (item.original_title or "").strip()
    if original and original != item.title:
        original_safe = _sanitize(original)
        title_folder_en = "{} ({})".format(original_safe, year) if year else original_safe
        path3 = "/{}/{}/{}".format(
            base_path.strip("/"), type_folder, title_folder_en
        )
        suggestions.append({
            "path": path3,
            "style": "english",
            "description": "英文命名: /{}/{}".format(type_folder, title_folder_en),
        })

    return suggestions


def format_meta_summary(item):
    # type: (...) -> dict
    """
    将 DiscoveryItem 格式化为结构化摘要，用于 CLI 显示和 JSON 输出。
    """
    genre_names = item.genres or []
    if genre_names and isinstance(genre_names[0], int):
        genre_display = [str(g) for g in genre_names]
    else:
        genre_display = genre_names

    summary = {
        "tmdb_id": item.source_id,
        "imdb_id": item.imdb_id or "",
        "title": item.title,
        "original_title": item.original_title,
        "year": item.year,
        "media_type": item.media_type,
        "rating": item.rating,
        "vote_count": item.vote_count,
        "genres": genre_display,
        "runtime": item.runtime,
        "status": item.status,
        "overview": item.overview,
        "tagline": item.tagline,
        "poster_url": "",
        "backdrop_url": "",
    }

    # 主创
    if item.credits:
        directors = [
            c["name"] for c in item.credits.get("crew", []) if c.get("job") == "Director"
        ]
        cast = [
            "{} ({})".format(c["name"], c.get("character", ""))
            for c in item.credits.get("cast", [])[:6]
        ]
        summary["directors"] = directors
        summary["cast"] = cast

    return summary
