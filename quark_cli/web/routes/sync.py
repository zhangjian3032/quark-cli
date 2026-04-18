"""同步 API 路由 — 多任务并行同步

提供:
  GET  /sync/status              所有同步任务状态
  GET  /sync/status/{name}       单个任务进度
  POST /sync/start               启动同步 (单个 / 全部)
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


def _normalize_sync_config(sync_cfg: dict) -> dict:
    """
    兼容旧配置: 如果没有 tasks[] 但有 webdav_mount/local_dest,
    自动包装成单任务列表。
    """
    if "tasks" in sync_cfg and isinstance(sync_cfg["tasks"], list):
        return sync_cfg

    # 旧格式 → 新格式
    webdav = sync_cfg.get("webdav_mount", "")
    local = sync_cfg.get("local_dest", "")
    if webdav and local:
        sync_cfg["tasks"] = [{
            "name": "default",
            "source": webdav,
            "dest": local,
            "delete_after_sync": sync_cfg.get("delete_after_sync", False),
            "enabled": True,
        }]
    else:
        sync_cfg.setdefault("tasks", [])

    return sync_cfg


# ── 服务器本地目录浏览 ──

@router.get("/sync/browse")
def sync_browse_dir(path: str = Query("/", description="要浏览的目录路径")):
    """
    浏览服务器本地文件系统目录

    用途: 前端路径选择器，用户可以逐级浏览并选择目录。
    只返回目录，不返回文件。
    """
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
            dirs.append({"name": name, "path": full})

    parent = os.path.dirname(real_path)
    if parent == real_path:
        parent = None

    return {"path": real_path, "parent": parent, "dirs": dirs}


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
        "task_name": "my-sync",       // 可选, 指定单个任务名
        "run_all": true,              // 为 true 时启动所有 enabled 任务
        "source_dir": "/mnt/...",     // 手动指定 (优先级最高)
        "dest_dir": "/mnt/...",
        "delete_after_sync": false,
        "bot_notify": false,
      }
    """
    from quark_cli.media.sync import get_sync_manager, DEFAULT_BUFFER_SIZE

    cfg = _get_config()
    cfg.load()
    sync_cfg = _normalize_sync_config(cfg.data.get("sync", {}))
    tasks_list = sync_cfg.get("tasks", [])
    bot_notify = data.get("bot_notify", sync_cfg.get("bot_notify", False))

    mgr = get_sync_manager()
    started = []

    try:
        # 模式 1: 手动指定 source/dest
        source = data.get("source_dir", "")
        dest = data.get("dest_dir", "")
        if source and dest:
            task_name = data.get("task_name", "manual")
            mgr.start_sync(
                task_name=task_name,
                source_dir=source,
                dest_dir=dest,
                delete_after_sync=data.get("delete_after_sync", False),
            )
            started.append(task_name)

        # 模式 2: run_all — 启动所有 enabled 任务
        elif data.get("run_all"):
            for t in tasks_list:
                if not t.get("enabled", True):
                    continue
                src = t.get("source", "")
                dst = t.get("dest", "")
                if not src or not dst:
                    continue
                tname = t.get("name", "sync-{}".format(len(started)))
                try:
                    mgr.start_sync(
                        task_name=tname,
                        source_dir=src,
                        dest_dir=dst,
                        delete_after_sync=t.get("delete_after_sync", False),
                        exclude_patterns=t.get("exclude_patterns",
                                               sync_cfg.get("exclude_patterns", [])),
                    )
                    started.append(tname)
                except RuntimeError:
                    # 该任务正在运行，跳过
                    pass

            if not started:
                raise HTTPException(status_code=400,
                                    detail="没有可启动的同步任务 (请先配置)")

        # 模式 3: 按 task_name 启动单个
        else:
            task_name = data.get("task_name", "")
            matched = None
            for t in tasks_list:
                if t.get("name") == task_name:
                    matched = t
                    break

            if matched:
                src = matched.get("source", "")
                dst = matched.get("dest", "")
                if not src or not dst:
                    raise HTTPException(status_code=400,
                                        detail="任务 {} 未配置路径".format(task_name))
                mgr.start_sync(
                    task_name=task_name,
                    source_dir=src,
                    dest_dir=dst,
                    delete_after_sync=matched.get("delete_after_sync", False),
                    exclude_patterns=matched.get("exclude_patterns",
                                                 sync_cfg.get("exclude_patterns", [])),
                )
                started.append(task_name)
            else:
                # 回退到旧的全局配置
                webdav = sync_cfg.get("webdav_mount", "")
                local = sync_cfg.get("local_dest", "")
                if not webdav or not local:
                    raise HTTPException(status_code=400,
                                        detail="未找到任务且未配置全局同步路径")
                tname = task_name or "default"
                mgr.start_sync(
                    task_name=tname,
                    source_dir=webdav,
                    dest_dir=local,
                    delete_after_sync=sync_cfg.get("delete_after_sync", False),
                    exclude_patterns=sync_cfg.get("exclude_patterns", []),
                )
                started.append(tname)

        # Bot 通知
        if bot_notify:
            for tname in started:
                _schedule_bot_notify_after_sync(cfg, tname)

        return {"status": "started", "tasks": started}

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

        p = progress.to_dict()

        # 写入历史记录
        try:
            from quark_cli.history import record as history_record
            h_status = "success" if progress.status == "done" else "error"
            history_record(
                record_type="sync",
                name=task_name,
                status=h_status,
                summary="拷贝 {} / 跳过 {} ({})".format(
                    p.get("copied_files", 0), p.get("skipped_files", 0),
                    p.get("speed_human", "")),
                detail=p,
                duration=p.get("elapsed", 0),
            )
        except Exception:
            pass

        result = {
            "task_name": "文件同步: {}".format(task_name),
            "saved": [],
            "failed": [],
        }
        if progress.status == "done":
            result["saved"] = [{"title": "文件同步完成", "year": "",
                                "save_path": p.get("dest_dir", ""),
                                "saved_count": p.get("copied_files", 0)}]
        elif progress.status == "error":
            result["failed"] = [{"title": "文件同步失败", "year": "",
                                 "error": "; ".join(p.get("errors", [])[:3])}]

        try:
            from quark_cli.scheduler import send_bot_notify
            config_path = cfg.config_path if hasattr(cfg, 'config_path') else None
            send_bot_notify(str(config_path) if config_path else None, result)
        except Exception:
            pass

    t = threading.Thread(target=_wait_and_notify, daemon=True,
                         name="sync-notify-{}".format(task_name))
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
    """获取同步配置 (已归一化为 tasks[])"""
    cfg = _get_config()
    cfg.load()
    sync_cfg = _normalize_sync_config(cfg.data.get("sync", {}))
    return sync_cfg


@router.put("/sync/config")
def sync_config_update(data: dict = Body(...)):
    """
    更新同步配置

    支持:
      - tasks: [{name, source, dest, delete_after_sync, enabled, exclude_patterns}, ...]
      - schedule_enabled, schedule_interval_minutes, bot_notify
      - 旧字段 webdav_mount / local_dest (向后兼容)
    """
    cfg = _get_config()
    cfg.load()

    if "sync" not in cfg._data:
        cfg._data["sync"] = {}

    sc = cfg._data["sync"]

    # 更新 tasks 列表
    if "tasks" in data:
        sc["tasks"] = data["tasks"]

    # 更新全局选项
    for key in ["schedule_enabled", "schedule_interval_minutes", "schedule_cron",
                "bot_notify", "exclude_patterns",
                "webdav_mount", "local_dest", "delete_after_sync", "buffer_size"]:
        if key in data:
            sc[key] = data[key]

    cfg.save()

    # 如果定时配置变更，通知调度器重载
    if any(k in data for k in ("schedule_enabled", "schedule_interval_minutes",
                                "schedule_cron", "tasks")):
        _reload_sync_scheduler(cfg)

    return {"status": "updated", "sync": _normalize_sync_config(sc)}


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
                yield "data: {}\n\n".format(json.dumps(current.to_dict(),
                                                        ensure_ascii=False))

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
