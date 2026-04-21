"""光鸭云盘 API 路由"""

import logging
from fastapi import APIRouter, HTTPException, Query, Body

logger = logging.getLogger("quark_cli.web.routes.guangya")

router = APIRouter(tags=["guangya"])


# ─────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────

def _load_cfg():
    from quark_cli.web.deps import get_config_path
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path=get_config_path())
    cfg.load()
    return cfg


def _get_service():
    from quark_cli.web.deps import get_guangya_drive_service
    return get_guangya_drive_service()


# ═════════════════════════════════════════════
# 凭证配置
# ═════════════════════════════════════════════

@router.get("/guangya/config")
def get_guangya_config():
    """获取光鸭云盘配置 (隐藏敏感信息)"""
    cfg = _load_cfg()
    gy = cfg.data.get("guangya", {})
    did = gy.get("did", "")
    rt = gy.get("refresh_token", "")
    return {
        "did": did,
        "has_refresh_token": bool(rt),
        "refresh_token_preview": "{}...{}".format(rt[:6], rt[-4:]) if len(rt) > 10 else ("***" if rt else ""),
    }


@router.put("/guangya/config")
def set_guangya_config(data: dict = Body(...)):
    """设置光鸭云盘凭证"""
    cfg = _load_cfg()
    cfg.load()
    gy = cfg.data.setdefault("guangya", {})
    if "did" in data:
        gy["did"] = data["did"].strip()
    if "refresh_token" in data:
        gy["refresh_token"] = data["refresh_token"].strip()
    cfg._data["guangya"] = gy
    cfg.save()

    # 清除缓存的客户端实例
    from quark_cli.web.deps import _clear_guangya_cache
    _clear_guangya_cache()

    return {"status": "updated"}


# ═════════════════════════════════════════════
# 账号 & 空间
# ═════════════════════════════════════════════

@router.get("/guangya/space")
def guangya_space():
    """查看空间信息"""
    try:
        svc = _get_service()
        result = svc.get_space_info()
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════
# 文件操作
# ═════════════════════════════════════════════

@router.get("/guangya/drive/ls")
def guangya_list_dir(parent_id: str = Query("", description="父目录 fileId，空=根目录")):
    """列出目录内容"""
    try:
        svc = _get_service()
        result = svc.list_dir(parent_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/drive/mkdir")
def guangya_mkdir(data: dict = Body(...)):
    """创建目录"""
    dir_name = data.get("dir_name", "").strip()
    parent_id = data.get("parent_id", "")
    if not dir_name:
        raise HTTPException(status_code=400, detail="缺少 dir_name 参数")
    try:
        svc = _get_service()
        result = svc.mkdir(dir_name, parent_id=parent_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/drive/rename")
def guangya_rename(data: dict = Body(...)):
    """重命名"""
    file_id = data.get("file_id", "").strip()
    new_name = data.get("new_name", "").strip()
    if not file_id or not new_name:
        raise HTTPException(status_code=400, detail="缺少 file_id 或 new_name 参数")
    try:
        svc = _get_service()
        result = svc.rename(file_id, new_name)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/drive/delete")
def guangya_delete(data: dict = Body(...)):
    """删除文件/目录"""
    file_ids = data.get("file_ids", [])
    if not file_ids:
        raise HTTPException(status_code=400, detail="缺少 file_ids 参数")
    try:
        svc = _get_service()
        result = svc.delete(file_ids)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guangya/drive/download")
def guangya_download(file_id: str = Query(..., description="文件 fileId")):
    """获取下载链接"""
    try:
        svc = _get_service()
        result = svc.get_download_url(file_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════
# 云添加 (磁力 / 种子)
# ═════════════════════════════════════════════

@router.post("/guangya/cloud/resolve-magnet")
def guangya_resolve_magnet(data: dict = Body(...)):
    """解析磁力链接"""
    url = data.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    try:
        svc = _get_service()
        result = svc.resolve_magnet(url)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/cloud/resolve-torrent")
def guangya_resolve_torrent(data: dict = Body(...)):
    """解析种子文件"""
    torrent_path = data.get("torrent_path", "").strip()
    if not torrent_path:
        raise HTTPException(status_code=400, detail="缺少 torrent_path 参数")
    try:
        svc = _get_service()
        result = svc.resolve_torrent(torrent_path)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/cloud/create")
def guangya_create_cloud_task(data: dict = Body(...)):
    """创建云添加任务"""
    url = data.get("url", "").strip()
    parent_id = data.get("parent_id", "")
    file_indexes = data.get("file_indexes")
    new_name = data.get("new_name")
    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    try:
        svc = _get_service()
        result = svc.create_cloud_task(
            url=url, parent_id=parent_id,
            file_indexes=file_indexes, new_name=new_name,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guangya/cloud/tasks")
def guangya_list_cloud_tasks(status: int = Query(None, description="状态过滤: 0=等待 1=下载中 2=完成 3=失败")):
    """查询云添加任务列表"""
    try:
        svc = _get_service()
        result = svc.list_cloud_tasks(status=status)
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"tasks": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guangya/cloud/tasks/delete")
def guangya_delete_cloud_tasks(data: dict = Body(...)):
    """删除云添加任务"""
    task_ids = data.get("task_ids", [])
    if not task_ids:
        raise HTTPException(status_code=400, detail="缺少 task_ids 参数")
    try:
        svc = _get_service()
        result = svc.delete_cloud_tasks(task_ids)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
