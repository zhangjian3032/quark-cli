"""定时任务调度器 API 路由"""

from fastapi import APIRouter, HTTPException, Body

router = APIRouter(tags=["scheduler"])


def _get_config():
    from quark_cli.web.deps import get_config
    return get_config()


@router.get("/scheduler/status")
def scheduler_status():
    """获取调度器状态和所有任务"""
    from quark_cli.scheduler import get_scheduler
    scheduler = get_scheduler()
    return scheduler.get_status()


@router.get("/scheduler/tasks")
def scheduler_tasks():
    """获取任务配置列表"""
    cfg = _get_config()
    cfg.load()
    tasks = cfg.data.get("scheduler", {}).get("tasks", [])
    return {"tasks": tasks}


@router.post("/scheduler/tasks")
def scheduler_task_create(data: dict = Body(...)):
    """创建新的定时任务"""
    cfg = _get_config()
    cfg.load()

    if "scheduler" not in cfg._data:
        cfg._data["scheduler"] = {"tasks": []}
    if "tasks" not in cfg._data["scheduler"]:
        cfg._data["scheduler"]["tasks"] = []

    task = {
        "name": data.get("name", "自动发现"),
        "enabled": data.get("enabled", True),
        "interval_minutes": data.get("interval_minutes", 360),
        "cron": data.get("cron", ""),
        "media_type": data.get("media_type", "movie"),
        "count": data.get("count", 3),
        "filters": data.get("filters", {}),
        "save_base_path": data.get("save_base_path", "/媒体"),
        "check_media_lib": data.get("check_media_lib", True),
        "bot_notify": data.get("bot_notify", True),
        "bot_chat_id": data.get("bot_chat_id", ""),
    }

    # 检查名称唯一
    existing_names = {t["name"] for t in cfg._data["scheduler"]["tasks"]}
    if task["name"] in existing_names:
        raise HTTPException(status_code=400, detail="任务名称已存在: {}".format(task["name"]))

    cfg._data["scheduler"]["tasks"].append(task)
    cfg.save()
    return {"status": "created", "task": task}


@router.put("/scheduler/tasks/{index}")
def scheduler_task_update(index: int, data: dict = Body(...)):
    """更新定时任务"""
    cfg = _get_config()
    cfg.load()

    tasks = cfg._data.get("scheduler", {}).get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")

    # 合并更新
    task = tasks[index]
    for key in ["name", "enabled", "interval_minutes", "cron", "media_type",
                "count", "filters", "save_base_path", "check_media_lib",
                "bot_notify", "bot_chat_id"]:
        if key in data:
            task[key] = data[key]

    cfg.save()
    return {"status": "updated", "task": task}


@router.delete("/scheduler/tasks/{index}")
def scheduler_task_delete(index: int):
    """删除定时任务"""
    cfg = _get_config()
    cfg.load()

    tasks = cfg._data.get("scheduler", {}).get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")

    removed = tasks.pop(index)
    cfg.save()
    return {"status": "deleted", "task": removed}


@router.post("/scheduler/tasks/{index}/toggle")
def scheduler_task_toggle(index: int):
    """启用/禁用定时任务"""
    cfg = _get_config()
    cfg.load()

    tasks = cfg._data.get("scheduler", {}).get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")

    tasks[index]["enabled"] = not tasks[index].get("enabled", True)
    cfg.save()
    return {"status": "toggled", "enabled": tasks[index]["enabled"]}


@router.post("/scheduler/tasks/{index}/trigger")
def scheduler_task_trigger(index: int):
    """手动触发执行任务"""
    cfg = _get_config()
    cfg.load()

    tasks = cfg._data.get("scheduler", {}).get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")

    task_name = tasks[index]["name"]

    from quark_cli.scheduler import get_scheduler
    scheduler = get_scheduler()
    result = scheduler.trigger_task(task_name)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/scheduler/start")
def scheduler_start():
    """启动调度器"""
    from quark_cli.scheduler import get_scheduler
    scheduler = get_scheduler()
    if scheduler._running:
        return {"status": "already_running"}
    scheduler.start()
    return {"status": "started"}


@router.post("/scheduler/stop")
def scheduler_stop():
    """停止调度器"""
    from quark_cli.scheduler import get_scheduler
    scheduler = get_scheduler()
    scheduler.stop()
    return {"status": "stopped"}
