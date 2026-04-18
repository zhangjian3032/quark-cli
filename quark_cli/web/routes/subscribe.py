"""订阅追剧 API 路由"""

from fastapi import APIRouter, HTTPException, Body

router = APIRouter(tags=["subscribe"])


def _get_config():
    from quark_cli.web.deps import get_config
    return get_config()


# ── 列表 ──

@router.get("/subscriptions")
def list_subscriptions():
    """获取所有订阅 + 调度器运行状态"""
    from quark_cli.subscribe import get_subscribe_scheduler
    scheduler = get_subscribe_scheduler()
    return scheduler.get_status()


# ── 新增 ──

@router.post("/subscriptions")
def create_subscription(data: dict = Body(...)):
    """新增订阅"""
    cfg = _get_config()
    cfg.load()

    if "subscriptions" not in cfg._data:
        cfg._data["subscriptions"] = []

    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="订阅名称不能为空")

    existing = {s["name"] for s in cfg._data["subscriptions"]}
    if name in existing:
        raise HTTPException(status_code=400, detail="订阅名称已存在: {}".format(name))

    sub = {
        "name": name,
        "keyword": data.get("keyword", "").strip() or name,
        "season": int(data.get("season", 1)),
        "next_episode": int(data.get("next_episode", 1)),
        "max_episode": data.get("max_episode"),
        "quality": data.get("quality", ""),
        "save_path": data.get("save_path", "/追剧/{}".format(name)),
        "interval_minutes": int(data.get("interval_minutes", 240)),
        "cron": data.get("cron", ""),
        "enabled": data.get("enabled", True),
        "finished": False,
        "miss_count": 0,
        "last_check": None,
        "last_episode": int(data.get("next_episode", 1)) - 1,
        "episodes_found": [],
        "bot_notify": data.get("bot_notify", True),
    }

    if sub["max_episode"] is not None:
        sub["max_episode"] = int(sub["max_episode"])

    cfg._data["subscriptions"].append(sub)
    cfg.save()

    # 启动调度器 (如果还没启动)
    try:
        from quark_cli.subscribe import try_start_subscribe_scheduler
        try_start_subscribe_scheduler(str(cfg.config_path))
    except Exception:
        pass

    return {"status": "created", "subscription": sub}


# ── 编辑 ──

@router.put("/subscriptions/{name}")
def update_subscription(name: str, data: dict = Body(...)):
    """编辑订阅"""
    cfg = _get_config()
    cfg.load()

    subs = cfg._data.get("subscriptions", [])
    target = None
    for s in subs:
        if s.get("name") == name:
            target = s
            break

    if target is None:
        raise HTTPException(status_code=404, detail="订阅不存在: {}".format(name))

    # 可更新字段
    for key in ["keyword", "season", "next_episode", "max_episode", "quality",
                "save_path", "interval_minutes", "cron", "enabled",
                "bot_notify", "finished"]:
        if key in data:
            val = data[key]
            if key in ("season", "next_episode", "interval_minutes"):
                val = int(val)
            elif key == "max_episode":
                val = int(val) if val is not None else None
            elif key in ("enabled", "bot_notify", "finished"):
                val = bool(val)
            target[key] = val

    # 如果改了 name
    if "new_name" in data and data["new_name"].strip():
        new_name = data["new_name"].strip()
        existing = {s["name"] for s in subs if s is not target}
        if new_name in existing:
            raise HTTPException(status_code=400, detail="名称已存在: {}".format(new_name))
        target["name"] = new_name

    cfg.save()
    return {"status": "updated", "subscription": target}


# ── 删除 ──

@router.delete("/subscriptions/{name}")
def delete_subscription(name: str):
    """删除订阅"""
    cfg = _get_config()
    cfg.load()

    subs = cfg._data.get("subscriptions", [])
    before = len(subs)
    cfg._data["subscriptions"] = [s for s in subs if s.get("name") != name]

    if len(cfg._data["subscriptions"]) == before:
        raise HTTPException(status_code=404, detail="订阅不存在: {}".format(name))

    cfg.save()
    return {"status": "deleted", "name": name}


# ── 手动检查 ──

@router.post("/subscriptions/{name}/check")
def trigger_check(name: str):
    """立即检查指定订阅"""
    from quark_cli.subscribe import get_subscribe_scheduler
    scheduler = get_subscribe_scheduler()
    result = scheduler.trigger_check(name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── 暂停/恢复 ──

@router.post("/subscriptions/{name}/toggle")
def toggle_subscription(name: str):
    """启用/禁用订阅"""
    cfg = _get_config()
    cfg.load()

    subs = cfg._data.get("subscriptions", [])
    for s in subs:
        if s.get("name") == name:
            s["enabled"] = not s.get("enabled", True)
            cfg.save()
            return {"status": "toggled", "name": name, "enabled": s["enabled"]}

    raise HTTPException(status_code=404, detail="订阅不存在")


# ── 重新追更 (finished → false, 继续 next_episode) ──

@router.post("/subscriptions/{name}/resume")
def resume_subscription(name: str, data: dict = Body(default={})):
    """将已完结的订阅重新激活 (可选: 新 season / 起始集数)"""
    cfg = _get_config()
    cfg.load()

    subs = cfg._data.get("subscriptions", [])
    for s in subs:
        if s.get("name") == name:
            s["finished"] = False
            s["enabled"] = True
            s["miss_count"] = 0
            if "season" in data:
                s["season"] = int(data["season"])
                s["next_episode"] = int(data.get("next_episode", 1))
                s["episodes_found"] = []
                s["last_episode"] = 0
            if "next_episode" in data and "season" not in data:
                s["next_episode"] = int(data["next_episode"])
            cfg.save()
            return {"status": "resumed", "subscription": s}

    raise HTTPException(status_code=404, detail="订阅不存在")


# ── 已追集数列表 ──

@router.get("/subscriptions/{name}/episodes")
def list_episodes(name: str):
    """获取指定订阅已追到的集数"""
    cfg = _get_config()
    cfg.load()

    subs = cfg._data.get("subscriptions", [])
    for s in subs:
        if s.get("name") == name:
            return {
                "name": name,
                "season": s.get("season", 1),
                "episodes_found": s.get("episodes_found", []),
                "next_episode": s.get("next_episode", 1),
                "max_episode": s.get("max_episode"),
                "finished": s.get("finished", False),
            }
    raise HTTPException(status_code=404, detail="订阅不存在")


# ── 调度器控制 ──

@router.post("/subscriptions/scheduler/start")
def start_scheduler():
    from quark_cli.subscribe import get_subscribe_scheduler
    scheduler = get_subscribe_scheduler()
    if scheduler._running:
        return {"status": "already_running"}
    scheduler.start()
    return {"status": "started"}


@router.post("/subscriptions/scheduler/stop")
def stop_scheduler():
    from quark_cli.subscribe import get_subscribe_scheduler
    scheduler = get_subscribe_scheduler()
    scheduler.stop()
    return {"status": "stopped"}
