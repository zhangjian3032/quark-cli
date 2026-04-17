"""影视媒体中心 API 路由"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["media"])


@router.get("/media/status")
def media_status():
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.get_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/media/libraries")
def media_libraries():
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.list_libraries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media/libraries/{lib_id}/items")
def media_library_items(
    lib_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        result = svc.get_library_items(lib_id, page=page, page_size=page_size)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media/search")
def media_search(
    keyword: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.search(keyword, page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media/items/{guid}")
def media_item_detail(
    guid: str,
    seasons: bool = Query(False),
    cast: bool = Query(False),
):
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.get_detail_full(guid, include_seasons=seasons, include_cast=cast)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media/items/{guid}/poster")
def media_item_poster_url(guid: str):
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.get_poster_url(guid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media/playing")
def media_playing():
    from quark_cli.web.deps import get_media_service
    try:
        svc = get_media_service()
        return svc.get_play_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
