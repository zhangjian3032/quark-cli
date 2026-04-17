"""资源搜索 + 分享转存 API 路由"""

from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(tags=["search"])


@router.get("/search/query")
def search_query(
    keyword: str = Query(..., min_length=1),
    source: str = Query(None, description="搜索源名称，不传则搜索全部"),
):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.search(keyword, source=source)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/sources")
def search_sources():
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        return svc.list_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/check")
def share_check(url: str = Query(..., min_length=5)):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_check(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/list")
def share_list(url: str = Query(..., min_length=5)):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_list(url)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/share/subdir")
def share_subdir(
    url: str = Query(..., min_length=5),
    pdir_fid: str = Query(..., min_length=1),
):
    """列出分享链接中某个子目录的文件"""
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_subdir(url, pdir_fid)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/share/save")
def share_save(data: dict = Body(...)):
    """
    转存分享链接
    Body: {url, save_path, password?, fid_list?, fid_token_list?}
    fid_list + fid_token_list: 可选，仅转存选中的文件
    """
    from quark_cli.web.deps import get_search_service
    url = data.get("url", "")
    save_path = data.get("save_path", "")
    password = data.get("password", "")
    fid_list = data.get("fid_list")
    fid_token_list = data.get("fid_token_list")

    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    if not save_path:
        raise HTTPException(status_code=400, detail="缺少 save_path 参数")

    try:
        svc = get_search_service()
        result = svc.share_save(
            url, save_path, password=password,
            fid_list=fid_list, fid_token_list=fid_token_list,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
