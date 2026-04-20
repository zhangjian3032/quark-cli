"""qBittorrent 管理 API 路由"""

from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(tags=["torrent"])


def _get_client(client_id=None):
    """获取 torrent 客户端实例"""
    from quark_cli.web.deps import get_config_path
    from quark_cli.rss.torrent_client import get_torrent_client
    try:
        return get_torrent_client(config_path=get_config_path(), client_id=client_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_config():
    """读取 torrent_clients 配置"""
    from quark_cli.web.deps import get_config_path
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path=get_config_path())
    cfg.load()
    return cfg


# ── 配置 ──

@router.get("/torrent/config")
def get_torrent_config():
    """获取 qBittorrent 配置 (隐藏密码)"""
    cfg = _get_config()
    tc = cfg.data.get("torrent_clients", {})
    # 脱敏
    result = {"default": tc.get("default", "")}
    qb_list = []
    for qb in tc.get("qbittorrent", []):
        item = {**qb}
        if item.get("password"):
            item["password"] = "******"
        qb_list.append(item)
    result["qbittorrent"] = qb_list
    return result


@router.put("/torrent/config")
def update_torrent_config(data: dict = Body(...)):
    """更新 qBittorrent 配置"""
    cfg = _get_config()
    cfg.load()
    tc = cfg.data.setdefault("torrent_clients", {})

    # 更新 default
    if "default" in data:
        tc["default"] = data["default"]

    # 更新 qbittorrent 列表
    if "qbittorrent" in data:
        new_list = []
        old_list = tc.get("qbittorrent", [])
        for item in data["qbittorrent"]:
            # 如果密码是掩码，保留旧密码
            if item.get("password") == "******":
                old = next((o for o in old_list if o.get("id") == item.get("id")), None)
                if old:
                    item["password"] = old.get("password", "")
            new_list.append(item)
        tc["qbittorrent"] = new_list

    cfg.save()
    return {"status": "updated"}


# ── 连接测试 ──

@router.post("/torrent/test")
def test_connection(data: dict = Body(default={})):
    """测试 qBittorrent 连接"""
    client_id = data.get("client_id")
    client = _get_client(client_id)
    result = client.test_connection()
    return result


# ── 种子列表 ──

@router.get("/torrent/list")
def list_torrents(
    filter: str = Query("all"),
    category: str = Query(""),
    sort: str = Query("added_on"),
    reverse: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    client_id: str = Query(None),
):
    """获取种子列表"""
    client = _get_client(client_id)
    try:
        client.login()
        torrents = client.get_torrent_list(
            filter=filter, category=category,
            sort=sort, reverse=reverse, limit=limit,
        )
        return {"torrents": torrents, "total": len(torrents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 添加种子 ──

@router.post("/torrent/add")
def add_torrent(data: dict = Body(...)):
    """添加种子/磁力

    Body:
        url: str — 磁力链接或 .torrent URL
        save_path: str (可选)
        category: str (可选)
        tags: str (可选, 逗号分隔)
        paused: bool (可选)
        client_id: str (可选)
    """
    url = data.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")

    client_id = data.get("client_id")
    client = _get_client(client_id)

    kwargs = {}
    if data.get("save_path"):
        kwargs["save_path"] = data["save_path"]
    if data.get("category"):
        kwargs["category"] = data["category"]
    if data.get("tags"):
        kwargs["tags"] = data["tags"]
    if data.get("paused"):
        kwargs["paused"] = True

    try:
        client.login()
        from quark_cli.rss.torrent_client import is_magnet_url, is_torrent_url
        if is_magnet_url(url):
            result = client.add_magnet(url, **kwargs)
        else:
            result = client.add_torrent_url(url, **kwargs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 版本信息 ──

@router.get("/torrent/version")
def get_version(client_id: str = Query(None)):
    """获取 qBittorrent 版本"""
    client = _get_client(client_id)
    try:
        client.login()
        version = client.get_version()
        return {"version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
