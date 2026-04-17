"""网盘文件管理 API 路由"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List

router = APIRouter(tags=["drive"])


@router.get("/drive/ls")
def drive_list_dir(path: str = Query("/", description="目录路径")):
    from quark_cli.web.deps import get_drive_service
    try:
        svc = get_drive_service()
        result = svc.list_dir(path)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drive/mkdir")
def drive_mkdir(data: dict = Body(...)):
    from quark_cli.web.deps import get_drive_service
    path = data.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path 参数")
    try:
        svc = get_drive_service()
        result = svc.mkdir(path)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drive/rename")
def drive_rename(data: dict = Body(...)):
    from quark_cli.web.deps import get_drive_service
    fid = data.get("fid", "")
    new_name = data.get("new_name", "")
    if not fid or not new_name:
        raise HTTPException(status_code=400, detail="缺少 fid 或 new_name 参数")
    try:
        svc = get_drive_service()
        result = svc.rename(fid, new_name)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drive/delete")
def drive_delete(data: dict = Body(...)):
    from quark_cli.web.deps import get_drive_service
    fids = data.get("fids", [])
    if not fids:
        raise HTTPException(status_code=400, detail="缺少 fids 参数")
    try:
        svc = get_drive_service()
        result = svc.delete(fids)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drive/download")
def drive_download(fid: str = Query(..., description="文件 FID，多个用逗号分隔")):
    from quark_cli.web.deps import get_drive_service
    fids = [f.strip() for f in fid.split(",") if f.strip()]
    if not fids:
        raise HTTPException(status_code=400, detail="缺少 fid 参数")
    try:
        svc = get_drive_service()
        result = svc.get_download_url(fids)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drive/search")
def drive_search(
    keyword: str = Query(..., min_length=1),
    path: str = Query("/"),
):
    from quark_cli.web.deps import get_drive_service
    try:
        svc = get_drive_service()
        result = svc.search(keyword, path=path)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drive/space")
def drive_space():
    from quark_cli.web.deps import get_drive_service
    try:
        svc = get_drive_service()
        result = svc.get_space_info()
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
