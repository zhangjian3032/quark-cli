"""同步 API 路由 — WebDAV → NAS 本地同步

提供:
  GET  /sync/status          所有同步任务状态
  GET  /sync/status/{name}   单个任务进度
  POST /sync/start           启动同步
  POST /sync/cancel/{name}   取消同步
  GET  /sync/config          获取同步配置
  PUT  /sync/config          更新同步配置
  GET  /sync/progress/{name} SSE 实时进度流
"""

import json
import asyncio
import threading
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["sync"])


def _get_config():
    from quark_cli.web.deps import get_config
    return get_config()


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
        "task_name": "my-sync",              # 可选，默认 "manual"
        "source_dir": "/mnt/alist/夸克/媒体",  # 可选，优先使用
        "dest_dir": "/mnt/nas/media",          # 可选，优先使用
        "delete_after_sync": false,            # 可选
        "scheduler_task": "每日随机电影",       # 可选，使用该调度任务的 sync 配置
      }
    """
    from quark_cli.media.sync import get_sync_manager, sync_from_config, DEFAULT_BUFFER_SIZE

    cfg = _get_config()
    cfg.load()

    task_name = data.get("task_name", "manual")
    source = data.get("source_dir", "")
    dest = data.get("dest_dir", "")
    delete = data.get("delete_after_sync", False)
    sched_task_name = data.get("scheduler_task", "")

    mgr = get_sync_manager()

    try:
        if source and dest:
            # 手动指定源/目标
            mgr.start_sync(
                task_name=task_name,
                source_dir=source,
                dest_dir=dest,
                delete_after_sync=delete,
            )
        elif sched_task_name:
            # 使用调度任务的配置
            tasks = cfg.data.get("scheduler", {}).get("tasks", [])
            task_config = None
            for t in tasks:
                if t.get("name") == sched_task_name:
                    task_config = t
                    break
            if not task_config:
                raise HTTPException(status_code=404, detail="调度任务不存在: {}".format(sched_task_name))

            # 读取 sync 配置
            global_sync = cfg.data.get("sync", {})
            task_sync = task_config.get("sync", {})

            webdav = task_sync.get("webdav_mount") or global_sync.get("webdav_mount", "")
            local = task_sync.get("local_dest") or global_sync.get("local_dest", "")

            if not webdav or not local:
                raise HTTPException(status_code=400, detail="未配置同步路径 (sync.webdav_mount / sync.local_dest)")

            save_base = task_config.get("save_base_path", "")
            if save_base:
                import os
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
            # 从全局配置读取
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

        return {"status": "started", "task_name": task_name}

    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
                "buffer_size", "exclude_patterns"]:
        if key in data:
            cfg._data["sync"][key] = data[key]

    cfg.save()
    return {"status": "updated", "sync": cfg._data["sync"]}


# ── SSE 实时进度 ──

@router.get("/sync/progress/{task_name}")
async def sync_progress_stream(task_name: str):
    """
    SSE (Server-Sent Events) 实时进度流

    前端通过 EventSource 连接:
      const es = new EventSource('/api/sync/progress/manual');
      es.onmessage = (e) => { const data = JSON.parse(e.data); ... };
    """
    from quark_cli.media.sync import get_sync_manager

    mgr = get_sync_manager()

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _on_progress(progress):
            """线程安全地将进度推入 asyncio queue"""
            try:
                loop.call_soon_threadsafe(queue.put_nowait, progress.to_dict())
            except Exception:
                pass

        mgr.add_listener(task_name, _on_progress)

        try:
            # 先发一次当前状态
            current = mgr.get_progress(task_name)
            if current:
                yield "data: {}\n\n".format(json.dumps(current.to_dict(), ensure_ascii=False))

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield "data: {}\n\n".format(json.dumps(data, ensure_ascii=False))

                    # 如果已完成/出错，发送最终状态后关闭
                    if data.get("status") in ("done", "error", "cancelled"):
                        break

                except asyncio.TimeoutError:
                    # 心跳 keep-alive
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
