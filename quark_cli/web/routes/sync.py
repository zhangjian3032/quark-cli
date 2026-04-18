"""同步 API 路由 — WebDAV → NAS 本地同步

提供:
  GET  /sync/status              所有同步任务状态
  GET  /sync/status/{name}       单个任务进度
  POST /sync/start               启动同步
  POST /sync/cancel/{name}       取消同步
  GET  /sync/config              获取同步配置
  PUT  /sync/config              更新同步配置
  GET  /sync/progress/{name}     SSE 实时进度流
  GET  /sync/browse              浏览服务器本地目录
"""

import json
import os
import asyncio
import threading
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["sync"])


def _get_config():
    from quark_cli.web.deps import get_config
    return get_config()


# ── 服务器本地目录浏览 ──

@router.get("/sync/browse")
def sync_browse_dir(path: str = Query("/", description="要浏览的目录路径")):
    """
    浏览服务器本地文件系统目录

    用途: 前端路径选择器，用户可以逐级浏览并选择 WebDAV 挂载目录或 NAS 目标目录。
    只返回目录，不返回文件。

    Returns:
      {
        "path": "/mnt",
        "parent": "/",
        "dirs": [
          {"name": "alist", "path": "/mnt/alist"},
          {"name": "nas", "path": "/mnt/nas"},
        ]
      }
    """
    # 安全限制: 规范化路径，防止 .. 穿越
    real_path = os.path.realpath(path)

    if not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail="路径不存在: {}".format(path))
    if not os.path.isdir(real_path):
        raise HTTPException(status_code=400, detail="不是目录: {}".format(path))

    try:
        entries = os.listdir(real_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问: {}".format(path))

    dirs = []
    for name in sorted(entries):
        if name.startswith("."):
            continue
        full = os.path.join(real_path, name)
        if os.path.isdir(full):
            dirs.append({
                "name": name,
                "path": full,
            })

    parent = os.path.dirname(real_path)
    if parent == real_path:
        parent = None  # 已是根目录

    return {
        "path": real_path,
        "parent": parent,
        "dirs": dirs,
    }


# ── 同步状态 ──

@router.get("/sync/status")
def sync_status():
    """获取所有同步任务状态"""
    from quark_cli.media.sync import get_sync_manager
    mgr = get_sync_manager()
    return {"tasks": mgr.get_all_progress()}


@router.get("/sync/status/{task_name}")
def sync_task_status(task_name: str):
    """获取单个同步任务进度"""
    from quark_cli.media.sync import get_sync_manager
    mgr = get_sync_manager()
    progress = mgr.get_progress(task_name)
    if not progress:
        raise HTTPException(status_code=404, detail="任务不存在: {}".format(task_name))
    return progress.to_dict()


# ── 启动同步 ──

@router.post("/sync/start")
def sync_start(data: dict = Body(...)):
    """
    启动同步任务

    Body:
      {
        "task_name": "my-sync",
        "source_dir": "/mnt/alist/夸克/媒体",
        "dest_dir": "/mnt/nas/media",
        "delete_after_sync": false,
        "scheduler_task": "每日随机电影",
        "bot_notify": false,
      }
    """
    from quark_cli.media.sync import get_sync_manager, DEFAULT_BUFFER_SIZE

    cfg = _get_config()
    cfg.load()

    task_name = data.get("task_name", "manual")
    source = data.get("source_dir", "")
    dest = data.get("dest_dir", "")
    delete = data.get("delete_after_sync", False)
    sched_task_name = data.get("scheduler_task", "")
    bot_notify = data.get("bot_notify", False)

    mgr = get_sync_manager()

    try:
        if source and dest:
            mgr.start_sync(
                task_name=task_name,
                source_dir=source,
                dest_dir=dest,
                delete_after_sync=delete,
            )
        elif sched_task_name:
            tasks = cfg.data.get("scheduler", {}).get("tasks", [])
            task_config = None
            for t in tasks:
                if t.get("name") == sched_task_name:
                    task_config = t
                    break
            if not task_config:
                raise HTTPException(status_code=404, detail="调度任务不存在: {}".format(sched_task_name))

            global_sync = cfg.data.get("sync", {})
            task_sync = task_config.get("sync", {})

            webdav = task_sync.get("webdav_mount") or global_sync.get("webdav_mount", "")
            local = task_sync.get("local_dest") or global_sync.get("local_dest", "")

            if not webdav or not local:
                raise HTTPException(status_code=400, detail="未配置同步路径")

            save_base = task_config.get("save_base_path", "")
            if save_base:
                rel = save_base.lstrip("/")
                webdav = os.path.join(webdav, rel)
                local = os.path.join(local, rel)

            del_after = task_sync.get("delete_after_sync", global_sync.get("delete_after_sync", False))
            buf = task_sync.get("buffer_size", global_sync.get("buffer_size", DEFAULT_BUFFER_SIZE))
            exclude = task_sync.get("exclude_patterns", global_sync.get("exclude_patterns", []))

            mgr.start_sync(
                task_name=task_name or sched_task_name,
                source_dir=webdav,
                dest_dir=local,
                delete_after_sync=del_after,
                buffer_size=buf,
                exclude_patterns=exclude,
            )
        else:
            global_sync = cfg.data.get("sync", {})
            webdav = global_sync.get("webdav_mount", "")
            local = global_sync.get("local_dest", "")

            if not webdav or not local:
                raise HTTPException(status_code=400, detail="未配置同步路径")

            mgr.start_sync(
                task_name=task_name,
                source_dir=webdav,
                dest_dir=local,
                delete_after_sync=global_sync.get("delete_after_sync", False),
                buffer_size=global_sync.get("buffer_size", DEFAULT_BUFFER_SIZE),
                exclude_patterns=global_sync.get("exclude_patterns", []),
            )

        # 异步等待完成后发送 Bot 通知 (如果启用)
        if bot_notify:
            _schedule_bot_notify_after_sync(cfg, task_name)

        return {"status": "started", "task_name": task_name}

    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _schedule_bot_notify_after_sync(cfg, task_name):
    """在后台线程等待同步完成后发送飞书通知"""
    import time

    def _wait_and_notify():
        from quark_cli.media.sync import get_sync_manager
        mgr = get_sync_manager()

        # 等待同步完成 (最多 24 小时)
        for _ in range(86400):
            progress = mgr.get_progress(task_name)
            if not progress:
                return
            if progress.status in ("done", "error", "cancelled"):
                break
            time.sleep(1)

        progress = mgr.get_progress(task_name)
        if not progress:
            return

        # 构造通知结果
        result = {
            "task_name": "文件同步: {}".format(task_name),
            "saved": [],
            "failed": [],
        }
        p = progress.to_dict()
        if progress.status == "done":
            result["saved"] = [{"title": "文件同步完成", "year": "",
                                "save_path": p.get("dest_dir", ""),
                                "saved_count": p.get("copied_files", 0)}]
        elif progress.status == "error":
            result["failed"] = [{"title": "文件同步失败", "year": "",
                                 "error": "; ".join(p.get("errors", [])[:3])}]

        # 发送通知
        try:
            from quark_cli.scheduler import send_bot_notify
            config_path = cfg.config_path if hasattr(cfg, 'config_path') else None
            send_bot_notify(str(config_path) if config_path else None, result)
        except Exception:
            pass

    t = threading.Thread(target=_wait_and_notify, daemon=True, name="sync-notify-{}".format(task_name))
    t.start()


# ── 取消同步 ──

@router.post("/sync/cancel/{task_name}")
def sync_cancel(task_name: str):
    """取消同步任务"""
    from quark_cli.media.sync import get_sync_manager
    mgr = get_sync_manager()
    if mgr.cancel_sync(task_name):
        return {"status": "cancelling", "task_name": task_name}
    raise HTTPException(status_code=404, detail="任务不存在: {}".format(task_name))


# ── 同步配置 ──

@router.get("/sync/config")
def sync_config_get():
    """获取同步配置"""
    cfg = _get_config()
    cfg.load()
    return cfg.data.get("sync", {})


@router.put("/sync/config")
def sync_config_update(data: dict = Body(...)):
    """更新同步配置"""
    cfg = _get_config()
    cfg.load()

    if "sync" not in cfg._data:
        cfg._data["sync"] = {}

    for key in ["webdav_mount", "local_dest", "delete_after_sync",
                "buffer_size", "exclude_patterns",
                "schedule_enabled", "schedule_interval_minutes", "schedule_cron",
                "bot_notify"]:
        if key in data:
            cfg._data["sync"][key] = data[key]

    cfg.save()

    # 如果定时配置变更，通知调度器重载
    if any(k in data for k in ("schedule_enabled", "schedule_interval_minutes", "schedule_cron")):
        _reload_sync_scheduler(cfg)

    return {"status": "updated", "sync": cfg._data["sync"]}


def _reload_sync_scheduler(cfg):
    """通知同步调度器重新加载配置"""
    try:
        from quark_cli.media.sync import get_sync_scheduler
        sched = get_sync_scheduler()
        sched.reload(cfg.data.get("sync", {}))
    except Exception:
        pass


# ── SSE 实时进度 ──

@router.get("/sync/progress/{task_name}")
async def sync_progress_stream(task_name: str):
    """SSE 实时进度流"""
    from quark_cli.media.sync import get_sync_manager

    mgr = get_sync_manager()

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _on_progress(progress):
            try:
                loop.call_soon_threadsafe(queue.put_nowait, progress.to_dict())
            except Exception:
                pass

        mgr.add_listener(task_name, _on_progress)

        try:
            current = mgr.get_progress(task_name)
            if current:
                yield "data: {}\n\n".format(json.dumps(current.to_dict(), ensure_ascii=False))

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield "data: {}\n\n".format(json.dumps(data, ensure_ascii=False))

                    if data.get("status") in ("done", "error", "cancelled"):
                        break

                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

        finally:
            mgr.remove_listener(task_name, _on_progress)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
