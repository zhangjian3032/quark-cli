"""Dashboard API — 全局概览 + 历史记录

提供:
  GET /dashboard              总览数据 (账号/空间/任务/同步/历史统计)
  GET /history                查询历史记录
  GET /history/stats          历史统计
  DELETE /history/cleanup     清理过期历史
"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["dashboard"])


def _get_config():
    from quark_cli.web.deps import get_config
    return get_config()


def _config_path():
    cfg = _get_config()
    return cfg.config_path if hasattr(cfg, 'config_path') else None


@router.get("/dashboard")
def dashboard():
    """
    Dashboard 总览

    返回:
      - account: 账号信息 (昵称/VIP/空间使用)
      - scheduler: 调度器状态 (运行/任务数/上次执行)
      - sync: 同步状态 (任务数/活跃任务)
      - history: 最近 7 天统计
      - disk: 本地磁盘使用 (如果有同步路径)
    """
    result = {}

    # 1. 账号信息
    try:
        from quark_cli.web.deps import get_account_service
        svc = get_account_service()
        info = svc.get_info()
        if "error" not in info:
            result["account"] = {
                "nickname": info.get("nickname", ""),
                "vip_type": info.get("vip_type", ""),
                "vip_status": info.get("is_vip", False),
                "space_used": info.get("use_capacity", 0),
                "space_total": info.get("total_capacity", 0),
                "space_used_human": _human_size(info.get("use_capacity", 0)),
                "space_total_human": _human_size(info.get("total_capacity", 0)),
                "space_percent": round(info.get("use_capacity", 0) / max(info.get("total_capacity", 1), 1) * 100, 1),
            }
        else:
            result["account"] = {"error": info["error"]}
    except Exception as e:
        result["account"] = {"error": str(e)}

    # 2. 调度器状态
    try:
        from quark_cli.scheduler import get_scheduler
        scheduler = get_scheduler()
        status = scheduler.get_status()
        result["scheduler"] = {
            "running": status.get("running", False),
            "task_count": len(status.get("tasks", [])),
            "enabled_count": sum(1 for t in status.get("tasks", []) if t.get("enabled", True)),
            "last_run": status.get("last_run"),
        }
    except Exception:
        result["scheduler"] = {"running": False, "task_count": 0}

    # 3. 同步状态
    try:
        from quark_cli.media.sync import get_sync_manager
        mgr = get_sync_manager()
        all_progress = mgr.get_all_progress()
        active = sum(1 for p in all_progress.values()
                     if p.get("status") in ("scanning", "syncing", "deleting"))

        cfg = _get_config()
        cfg.load()
        sync_cfg = cfg.data.get("sync", {})
        sync_tasks = sync_cfg.get("tasks", [])

        result["sync"] = {
            "configured_tasks": len(sync_tasks),
            "active_tasks": active,
            "schedule_enabled": sync_cfg.get("schedule_enabled", False),
            "recent_progress": all_progress,
        }
    except Exception:
        result["sync"] = {"configured_tasks": 0, "active_tasks": 0}


    # 3.5 订阅追剧状态
    try:
        from quark_cli.subscribe import get_subscribe_scheduler
        sub_scheduler = get_subscribe_scheduler()
        sub_status = sub_scheduler.get_status()
        subs = sub_status.get("subscriptions", [])
        active_subs = [s for s in subs if s.get("enabled") and not s.get("finished")]
        finished_subs = [s for s in subs if s.get("finished")]
        result["subscriptions"] = {
            "running": sub_status.get("running", False),
            "total": len(subs),
            "active": len(active_subs),
            "finished": len(finished_subs),
            "items": subs[:5],  # Dashboard 只展示前5个
        }
    except Exception:
        result["subscriptions"] = {"total": 0, "active": 0}

    # 4. 历史统计
    try:
        from quark_cli.history import stats
        result["history"] = stats(days=7, config_path=_config_path())
    except Exception:
        result["history"] = {"total": 0, "by_type": {}, "by_status": {}, "recent": []}

    # 5. 磁盘使用率 (同步路径)
    try:
        cfg = _get_config()
        cfg.load()
        sync_cfg = cfg.data.get("sync", {})
        disks = {}
        paths_seen = set()
        for t in sync_cfg.get("tasks", []):
            for p in [t.get("source", ""), t.get("dest", "")]:
                if p and os.path.exists(p):
                    # 取挂载点
                    import shutil
                    usage = shutil.disk_usage(p)
                    mount = _get_mount_point(p)
                    if mount not in paths_seen:
                        paths_seen.add(mount)
                        disks[mount] = {
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": round(usage.used / max(usage.total, 1) * 100, 1),
                            "total_human": _human_size(usage.total),
                            "used_human": _human_size(usage.used),
                            "free_human": _human_size(usage.free),
                        }
        result["disks"] = disks
    except Exception:
        result["disks"] = {}

    return result


# ── 历史记录 API ──

@router.get("/history")
def history_list(
    type: str = Query(None, description="类型: task/sync/sign/auto_save"),
    status: str = Query(None, description="状态: success/partial/error"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询历史记录"""
    from quark_cli.history import query
    records = query(
        record_type=type,
        status=status,
        limit=limit,
        offset=offset,
        config_path=_config_path(),
    )
    return {"records": records, "count": len(records)}


@router.get("/history/stats")
def history_stats(days: int = Query(7, ge=1, le=365)):
    """历史统计"""
    from quark_cli.history import stats
    return stats(days=days, config_path=_config_path())


@router.delete("/history/cleanup")
def history_cleanup(keep_days: int = Query(90, ge=1)):
    """清理过期历史"""
    from quark_cli.history import cleanup
    deleted = cleanup(keep_days=keep_days, config_path=_config_path())
    return {"deleted": deleted, "keep_days": keep_days}


# ── 工具 ──

import os


def _human_size(size_bytes):
    if not size_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    k = 1024
    import math
    i = int(math.floor(math.log(size_bytes) / math.log(k))) if size_bytes > 0 else 0
    return "{:.1f} {}".format(size_bytes / (k ** i), units[min(i, len(units) - 1)])


def _get_mount_point(path):
    """获取路径所在的挂载点"""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path
