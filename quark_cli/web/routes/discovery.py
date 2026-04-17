"""TMDB 影视发现 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(tags=["discovery"])


def _get_svc():
    from quark_cli.web.deps import get_discovery_service
    svc = get_discovery_service()
    if not svc:
        raise HTTPException(
            status_code=503,
            detail="TMDB 未配置。请运行: quark-cli media config --tmdb-key <key>"
        )
    return svc


@router.get("/discovery/meta")
def discovery_meta(
    query: str = Query(..., min_length=1),
    media_type: str = Query("movie"),
    year: Optional[int] = Query(None),
    base_path: str = Query("/媒体"),
):
    try:
        svc = _get_svc()
        return svc.meta_search(query, media_type=media_type, year=year, base_path=base_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/meta/{tmdb_id}")
def discovery_meta_by_id(
    tmdb_id: str,
    media_type: str = Query("movie"),
    base_path: str = Query("/媒体"),
):
    try:
        svc = _get_svc()
        return svc.meta_by_tmdb_id(tmdb_id, media_type=media_type, base_path=base_path)
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
):
    try:
        svc = _get_svc()
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
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/genres")
def discovery_genres(media_type: str = Query("movie")):
    try:
        svc = _get_svc()
        return svc.get_genres(media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
