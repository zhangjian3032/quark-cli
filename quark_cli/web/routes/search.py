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
    Body: {url, save_path, password?,
           fid_list?, fid_token_list?,
           rename_pattern?, rename_replace?}
    """
    from quark_cli.web.deps import get_search_service
    url = data.get("url", "")
    save_path = data.get("save_path", "")
    password = data.get("password", "")
    fid_list = data.get("fid_list")
    fid_token_list = data.get("fid_token_list")
    rename_pattern = data.get("rename_pattern", "")
    rename_replace = data.get("rename_replace", "")

    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    if not save_path:
        raise HTTPException(status_code=400, detail="缺少 save_path 参数")

    try:
        svc = get_search_service()
        result = svc.share_save(
            url, save_path, password=password,
            fid_list=fid_list, fid_token_list=fid_token_list,
            rename_pattern=rename_pattern, rename_replace=rename_replace,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 正则重命名 ──

@router.get("/rename/presets")
def rename_presets():
    """获取可用的正则预设和魔法变量"""
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        return svc.rename_presets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename/preview")
def rename_preview(data: dict = Body(...)):
    """预览正则替换效果 (不实际操作)

    Body: {url, pattern, replace}
    """
    from quark_cli.web.deps import get_search_service
    url = data.get("url", "")
    pattern = data.get("pattern", "")
    replace = data.get("replace", "")

    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    if not pattern and not replace:
        raise HTTPException(status_code=400, detail="缺少 pattern 或 replace 参数")

    try:
        svc = get_search_service()
        result = svc.rename_preview(url, pattern, replace)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
