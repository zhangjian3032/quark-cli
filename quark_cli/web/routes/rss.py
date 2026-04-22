"""RSS 订阅 API 路由"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(tags=["rss"])


def _get_manager():
    from quark_cli.web.deps import get_config_path
    from quark_cli.rss.manager import RssManager
    return RssManager(get_config_path())


# ── Feed CRUD ──

@router.get("/rss/feeds")
def list_feeds():
    """列出所有 RSS Feed"""
    manager = _get_manager()
    feeds = manager.list_feeds()
    return {"feeds": feeds, "total": len(feeds)}


@router.post("/rss/feeds")
def create_feed(data: dict = Body(...)):
    """添加 RSS Feed"""
    feed_url = data.get("feed_url", "").strip()
    if not feed_url:
        raise HTTPException(status_code=400, detail="缺少 feed_url")

    manager = _get_manager()
    try:
        feed = manager.add_feed(
            feed_url=feed_url,
            name=data.get("name", ""),
            interval_minutes=int(data.get("interval_minutes", 30)),
            auth=data.get("auth"),
            rules=data.get("rules"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 启动调度器
    try:
        from quark_cli.rss.manager import try_start_rss_scheduler
        from quark_cli.web.deps import get_config_path
        try_start_rss_scheduler(get_config_path())
    except Exception:
        pass

    return {"status": "created", "feed": feed}


@router.get("/rss/feeds/{feed_id}")
def get_feed(feed_id: str):
    """获取 Feed 详情"""
    manager = _get_manager()
    feed = manager.get_feed(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed 不存在")
    return feed


@router.put("/rss/feeds/{feed_id}")
def update_feed(feed_id: str, data: dict = Body(...)):
    """更新 Feed"""
    manager = _get_manager()
    try:
        feed = manager.update_feed(feed_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated", "feed": feed}


@router.delete("/rss/feeds/{feed_id}")
def delete_feed(feed_id: str):
    """删除 Feed"""
    manager = _get_manager()
    try:
        manager.remove_feed(feed_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted", "id": feed_id}


@router.post("/rss/feeds/{feed_id}/toggle")
def toggle_feed(feed_id: str):
    """启用/禁用 Feed"""
    manager = _get_manager()
    try:
        enabled = manager.toggle_feed(feed_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "toggled", "id": feed_id, "enabled": enabled}


@router.post("/rss/feeds/{feed_id}/check")
def check_feed(feed_id: str, data: dict = Body(default={})):
    """手动触发检查"""
    manager = _get_manager()
    dry_run = data.get("dry_run", False)
    result = manager.check_feed(feed_id, dry_run=dry_run)
    if result.get("error") and not result.get("new_items"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/rss/feeds/{feed_id}/test")
def test_feed_by_id(feed_id: str):
    """测试已保存的 Feed (拉取但不执行动作)"""
    manager = _get_manager()
    feed = manager.get_feed(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed 不存在")
    return manager.test_feed(feed["feed_url"], auth=feed.get("auth"))


# ── 规则管理 ──

@router.get("/rss/feeds/{feed_id}/rules")
def list_rules(feed_id: str):
    """获取 Feed 规则列表"""
    manager = _get_manager()
    feed = manager.get_feed(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed 不存在")
    return {"rules": feed.get("rules", []), "total": len(feed.get("rules", []))}


@router.post("/rss/feeds/{feed_id}/rules")
def add_rule(feed_id: str, data: dict = Body(...)):
    """添加规则"""
    manager = _get_manager()
    try:
        rules = manager.add_rule(feed_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "added", "rules_count": len(rules)}


@router.delete("/rss/feeds/{feed_id}/rules/{index}")
def remove_rule(feed_id: str, index: int):
    """删除规则"""
    manager = _get_manager()
    try:
        rules = manager.remove_rule(feed_id, index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "removed", "rules_count": len(rules)}




@router.post("/rss/feeds/{feed_id}/match-preview")
def match_preview(feed_id: str, data: dict = Body(default={})):
    """预览规则匹配结果 — 对 Feed 当前条目运行规则，返回匹配/未匹配列表"""
    manager = _get_manager()
    feed = manager.get_feed(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed 不存在")

    # 拉取 feed 条目
    test_result = manager.test_feed(feed["feed_url"], auth=feed.get("auth"), max_items=50)
    if test_result.get("error"):
        raise HTTPException(status_code=400, detail=test_result["error"])

    items_raw = test_result.get("items", [])

    # 构建 FeedItem 对象
    from quark_cli.rss.fetcher import FeedItem
    from quark_cli.rss.matcher import match_item, merge_rule_defaults
    from datetime import datetime

    rule = merge_rule_defaults(data.get("rule", {}))

    matched = []
    unmatched = []
    for item_dict in items_raw:
        fi = FeedItem(
            title=item_dict.get("title", ""),
            link=item_dict.get("link", ""),
            guid=item_dict.get("guid", ""),
            pub_date=None,
            description=item_dict.get("description", ""),
            author=item_dict.get("author", ""),
            categories=item_dict.get("categories", []),
            enclosures=item_dict.get("enclosures", []),
        )
        result = match_item(fi, rule)
        entry = {
            "title": fi.title,
            "link": fi.link,
            "guid": fi.guid,
            "pub_date": item_dict.get("pub_date"),
            "description": (fi.description or "")[:200],
        }
        if result:
            entry["target_links"] = result.get_target_links()
            matched.append(entry)
        else:
            unmatched.append(entry)

    return {
        "total": len(items_raw),
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "matched": matched,
        "unmatched": unmatched[:20],  # 未匹配只返回前20条
    }


# ── 测试任意 URL ──

@router.post("/rss/test")
def test_feed_url(data: dict = Body(...)):
    """测试任意 Feed URL (预览条目)"""
    feed_url = data.get("feed_url", "").strip()
    if not feed_url:
        raise HTTPException(status_code=400, detail="缺少 feed_url")

    manager = _get_manager()
    auth = data.get("auth")
    result = manager.test_feed(feed_url, auth=auth)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── 历史 ──

@router.get("/rss/history")
def rss_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """RSS 匹配/转存历史"""
    from quark_cli.history import query
    from quark_cli.web.deps import get_config_path
    records = query(record_type="rss", limit=limit, offset=offset, config_path=get_config_path())
    return {"records": records, "total": len(records)}


# ── 调度器 ──

@router.get("/rss/scheduler/status")
def rss_scheduler_status():
    """RSS 调度器状态"""
    from quark_cli.rss.manager import get_rss_scheduler
    scheduler = get_rss_scheduler()
    return scheduler.get_status()


@router.post("/rss/scheduler/start")
def start_rss_scheduler():
    """启动 RSS 调度器"""
    from quark_cli.rss.manager import get_rss_scheduler
    scheduler = get_rss_scheduler()
    if scheduler._running:
        return {"status": "already_running"}
    scheduler.start()
    return {"status": "started"}


@router.post("/rss/scheduler/stop")
def stop_rss_scheduler():
    """停止 RSS 调度器"""
    from quark_cli.rss.manager import get_rss_scheduler
    scheduler = get_rss_scheduler()
    scheduler.stop()
    return {"status": "stopped"}
