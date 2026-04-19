"""影视发现 API 路由 (支持多数据源: tmdb / douban)"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(tags=["discovery"])


def _get_svc(source=None):
    from quark_cli.web.deps import get_discovery_service
    svc = get_discovery_service(source_name=source)
    if not svc:
        if source == "tmdb" or source is None:
            raise HTTPException(
                status_code=503,
                detail="TMDB 未配置。请运行: quark-cli media config --tmdb-key <key>，或使用 source=douban"
            )
        raise HTTPException(status_code=503, detail="数据源 '{}' 不可用".format(source))
    return svc


@router.get("/discovery/meta")
def discovery_meta(
    query: str = Query(..., min_length=1),
    media_type: str = Query("movie"),
    year: Optional[int] = Query(None),
    base_path: str = Query("/媒体"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    try:
        svc = _get_svc(source)
        return svc.meta_search(query, media_type=media_type, year=year, base_path=base_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/meta/{item_id}")
def discovery_meta_by_id(
    item_id: str,
    media_type: str = Query("movie"),
    base_path: str = Query("/媒体"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    try:
        svc = _get_svc(source)
        return svc.meta_by_id(item_id, media_type=media_type, base_path=base_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/list")
def discovery_list(
    list_type: str = Query("top_rated"),
    media_type: str = Query("movie"),
    page: int = Query(1, ge=1),
    min_rating: Optional[float] = Query(None),
    genre: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    country: Optional[str] = Query(None),
    sort_by: str = Query("vote_average.desc"),
    min_votes: int = Query(50),
    window: str = Query("week"),
    tag: Optional[str] = Query(None, description="豆瓣标签 (如 热门/科幻/美剧)"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    try:
        svc = _get_svc(source)
        return svc.discover(
            list_type=list_type,
            media_type=media_type,
            page=page,
            min_rating=min_rating,
            genre=genre,
            year=year,
            country=country,
            sort_by=sort_by,
            min_votes=min_votes,
            window=window,
            tag=tag,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/genres")
def discovery_genres(
    media_type: str = Query("movie"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    try:
        svc = _get_svc(source)
        return svc.get_genres(media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/tags")
def discovery_tags(
    media_type: str = Query("movie"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    """获取可用标签列表 (主要用于豆瓣)"""
    try:
        svc = _get_svc(source)
        tags = svc.get_available_tags(media_type)
        return {"source": svc.source_name, "media_type": media_type, "tags": tags}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/discovery/person/search")
def discovery_person_search(
    q: str = Query(..., min_length=1, description="演员名称"),
    page: int = Query(1, ge=1),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    """搜索演员/人物"""
    try:
        svc = _get_svc(source)
        return svc.person_search(q, page=page)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/person/{person_id}/credits")
def discovery_person_credits(
    person_id: str,
    media_type: Optional[str] = Query(None, description="过滤: movie / tv (不传=全部)"),
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    """获取演员参演作品列表"""
    try:
        svc = _get_svc(source)
        return svc.person_credits(person_id, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/sources")
def discovery_sources():
    """获取可用的数据源列表 (含缓存统计)"""
    from quark_cli.web.deps import get_tmdb_source, _cached_sources
    sources = []
    tmdb = get_tmdb_source()
    if tmdb:
        entry = {"name": "tmdb", "label": "TMDB", "available": True}
    else:
        entry = {"name": "tmdb", "label": "TMDB", "available": False, "hint": "需配置 API Key"}
    cached_tmdb = _cached_sources.get("tmdb")
    if cached_tmdb and hasattr(cached_tmdb, "cache_stats"):
        entry["cache"] = cached_tmdb.cache_stats()
    sources.append(entry)

    entry_db = {"name": "douban", "label": "豆瓣", "available": True}
    cached_db = _cached_sources.get("douban")
    if cached_db and hasattr(cached_db, "cache_stats"):
        entry_db["cache"] = cached_db.cache_stats()
    sources.append(entry_db)
    return {"sources": sources}


@router.get("/discovery/cache/stats")
def discovery_cache_stats(
    source: Optional[str] = Query(None, description="数据源: tmdb / douban"),
):
    """获取缓存统计信息"""
    from quark_cli.web.deps import get_discovery_source
    src = get_discovery_source(source)
    if not src:
        return {"error": "数据源不可用"}
    if hasattr(src, "cache_stats"):
        return src.cache_stats()
    return {"message": "缓存未启用"}


@router.post("/discovery/cache/clear")
def discovery_cache_clear(
    source: Optional[str] = Query(None, description="数据源: tmdb / douban (空=清除全部)"),
):
    """清空缓存"""
    from quark_cli.web.deps import _cached_sources
    if source:
        src = _cached_sources.get(source)
        if src and hasattr(src, "cache_clear"):
            src.cache_clear()
            return {"message": "已清空 {} 缓存".format(source)}
        return {"message": "未找到 {} 的缓存实例".format(source)}
    else:
        cleared = []
        for name, src in _cached_sources.items():
            if hasattr(src, "cache_clear"):
                src.cache_clear()
                cleared.append(name)
        return {"message": "已清空全部缓存", "sources": cleared}
