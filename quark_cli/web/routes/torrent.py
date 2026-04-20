"""
qBittorrent 管理 API 路由

支持:
  - 多实例配置管理 (增/删/改/查/设默认)
  - 任务列表 (排序/过滤)
  - 任务操作 (添加/暂停/恢复/删除)
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger("quark_cli.web.routes.torrent")

router = APIRouter(tags=["torrent"])


# ─────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────

def _load_cfg():
    from quark_cli.web.deps import get_config_path
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path=get_config_path())
    cfg.load()
    return cfg


def _get_tc(cfg):
    """返回 torrent_clients 配置 (dict), 不存在则初始化"""
    tc = cfg.data.get("torrent_clients")
    if not tc:
        tc = {
            "default": "",
            "qbittorrent": [],
            "_reserved": {
                "transmission": "Transmission RPC — 如有需求请反馈",
                "aria2": "aria2 JSON-RPC — 如有需求请反馈",
            },
        }
        cfg._data["torrent_clients"] = tc
    return tc


def _safe_client(qb):
    """返回前端安全的客户端配置 (隐藏密码)"""
    return {
        "id": qb.get("id", ""),
        "name": qb.get("name", "qBittorrent"),
        "host": qb.get("host", ""),
        "port": qb.get("port", 8080),
        "username": qb.get("username", "admin"),
        "has_password": bool(qb.get("password")),
        "use_https": qb.get("use_https", False),
        "default_save_path": qb.get("default_save_path", ""),
        "default_category": qb.get("default_category", ""),
        "default_tags": qb.get("default_tags", []),
    }


def _build_client(qb_cfg):
    """从配置 dict 构建 QBittorrentClient 实例"""
    from quark_cli.rss.torrent_client import QBittorrentClient
    return QBittorrentClient(
        host=qb_cfg.get("host", "127.0.0.1"),
        port=int(qb_cfg.get("port", 8080)),
        username=qb_cfg.get("username", "admin"),
        password=qb_cfg.get("password", ""),
        use_https=qb_cfg.get("use_https", False),
    )


def _find_client_cfg(tc, client_id):
    """在 qbittorrent 列表中查找指定 id 的配置"""
    for qb in tc.get("qbittorrent", []):
        if qb.get("id") == client_id:
            return qb
    return None


def _resolve_client(tc, client_id=None):
    """解析客户端配置 — 未指定则使用默认, 仅一个则直接返回"""
    qb_list = tc.get("qbittorrent", [])
    if not qb_list:
        raise HTTPException(404, "未配置任何 qBittorrent 实例")

    if client_id:
        qb = _find_client_cfg(tc, client_id)
        if not qb:
            raise HTTPException(404, "客户端 {} 不存在".format(client_id))
        return qb

    default_id = tc.get("default", "")
    if default_id:
        qb = _find_client_cfg(tc, default_id)
        if qb:
            return qb

    if len(qb_list) == 1:
        return qb_list[0]

    raise HTTPException(400, "存在多个实例, 请指定 client_id")


# ═════════════════════════════════════════════
# 兼容旧 API (保留)
# ═════════════════════════════════════════════

@router.get("/torrent/config")
def get_torrent_config():
    """获取 qBittorrent 配置 (隐藏密码)"""
    cfg = _load_cfg()
    tc = cfg.data.get("torrent_clients", {})
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
    """更新 qBittorrent 配置 (兼容旧格式)"""
    cfg = _load_cfg()
    cfg.load()
    tc = cfg.data.setdefault("torrent_clients", {})

    if "default" in data:
        tc["default"] = data["default"]

    if "qbittorrent" in data:
        new_list = []
        old_list = tc.get("qbittorrent", [])
        for item in data["qbittorrent"]:
            if item.get("password") == "******":
                old = next((o for o in old_list if o.get("id") == item.get("id")), None)
                if old:
                    item["password"] = old.get("password", "")
            new_list.append(item)
        tc["qbittorrent"] = new_list

    cfg.save()
    return {"status": "updated"}


@router.get("/torrent/version")
def get_version(client_id: str = Query(None)):
    """获取 qBittorrent 版本"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)
    try:
        client.login()
        version = client.get_version()
        return {"version": version}
    except Exception as e:
        raise HTTPException(500, str(e))


# ═════════════════════════════════════════════
# 多实例管理 API
# ═════════════════════════════════════════════

@router.get("/torrent/clients")
def list_clients():
    """列出所有已配置的 qBittorrent 实例"""
    cfg = _load_cfg()
    tc = cfg.data.get("torrent_clients", {})
    qb_list = tc.get("qbittorrent", [])
    default_id = tc.get("default", "")

    return {
        "default": default_id,
        "clients": [_safe_client(qb) for qb in qb_list],
    }


@router.post("/torrent/clients")
def add_client(data: dict = Body(...)):
    """添加新的 qBittorrent 实例"""
    host = data.get("host", "").strip()
    if not host:
        raise HTTPException(400, "host 不能为空")

    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_list = tc.setdefault("qbittorrent", [])

    client_id = data.get("id", "").strip() or "qb_" + uuid.uuid4().hex[:6]

    for qb in qb_list:
        if qb.get("id") == client_id:
            raise HTTPException(409, "客户端 ID {} 已存在".format(client_id))

    new_cfg = {
        "id": client_id,
        "name": data.get("name", "").strip() or "qBittorrent",
        "host": host,
        "port": int(data.get("port", 8080)),
        "username": data.get("username", "").strip() or "admin",
        "password": data.get("password", ""),
        "use_https": bool(data.get("use_https", False)),
        "default_save_path": data.get("default_save_path", "").strip(),
        "default_category": data.get("default_category", "").strip(),
        "default_tags": data.get("default_tags", ["quark-cli", "rss"]),
    }

    qb_list.append(new_cfg)

    if not tc.get("default"):
        tc["default"] = client_id

    cfg._data["torrent_clients"] = tc
    cfg.save()

    return {"status": "created", "client": _safe_client(new_cfg)}


@router.put("/torrent/clients/default")
def set_default_client(data: dict = Body(...)):
    """设置默认客户端"""
    client_id = data.get("client_id", "").strip()
    if not client_id:
        raise HTTPException(400, "client_id 不能为空")

    cfg = _load_cfg()
    tc = _get_tc(cfg)

    qb = _find_client_cfg(tc, client_id)
    if not qb:
        raise HTTPException(404, "客户端 {} 不存在".format(client_id))

    tc["default"] = client_id
    cfg._data["torrent_clients"] = tc
    cfg.save()

    return {"status": "ok", "default": client_id}


@router.put("/torrent/clients/{client_id}")
def update_client(client_id: str, data: dict = Body(...)):
    """更新已有的 qBittorrent 实例配置"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)

    qb = _find_client_cfg(tc, client_id)
    if not qb:
        raise HTTPException(404, "客户端 {} 不存在".format(client_id))

    for key in ("name", "host", "username", "password", "default_save_path", "default_category"):
        if key in data:
            val = data[key]
            qb[key] = val.strip() if isinstance(val, str) else val
    if "port" in data:
        qb["port"] = int(data["port"])
    if "use_https" in data:
        qb["use_https"] = bool(data["use_https"])
    if "default_tags" in data:
        tags = data["default_tags"]
        qb["default_tags"] = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",") if t.strip()]

    cfg._data["torrent_clients"] = tc
    cfg.save()

    return {"status": "updated", "client": _safe_client(qb)}


@router.delete("/torrent/clients/{client_id}")
def delete_client(client_id: str):
    """删除 qBittorrent 实例配置"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_list = tc.get("qbittorrent", [])

    idx = None
    for i, qb in enumerate(qb_list):
        if qb.get("id") == client_id:
            idx = i
            break

    if idx is None:
        raise HTTPException(404, "客户端 {} 不存在".format(client_id))

    qb_list.pop(idx)

    if tc.get("default") == client_id:
        tc["default"] = qb_list[0]["id"] if qb_list else ""

    cfg._data["torrent_clients"] = tc
    cfg.save()

    return {"status": "deleted", "client_id": client_id}


@router.post("/torrent/clients/{client_id}/test")
def test_client(client_id: str):
    """测试指定客户端连接"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)

    qb_cfg = _find_client_cfg(tc, client_id)
    if not qb_cfg:
        raise HTTPException(404, "客户端 {} 不存在".format(client_id))

    client = _build_client(qb_cfg)
    result = client.test_connection()
    return result


# ═════════════════════════════════════════════
# 兼容旧测试 API
# ═════════════════════════════════════════════

@router.post("/torrent/test")
def test_connection(data: dict = Body(default={})):
    """测试 qBittorrent 连接 (兼容旧 API)"""
    client_id = data.get("client_id")
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    try:
        qb_cfg = _resolve_client(tc, client_id)
    except HTTPException:
        return {"success": False, "error": "未配置 qBittorrent"}
    client = _build_client(qb_cfg)
    return client.test_connection()


# ═════════════════════════════════════════════
# 任务管理
# ═════════════════════════════════════════════

@router.get("/torrent/list")
def list_torrents(
    filter: str = Query("all"),
    category: str = Query(""),
    sort: str = Query("added_on"),
    reverse: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    client_id: str = Query(None),
):
    """获取种子列表 (支持排序)"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)

    try:
        client.login()
        torrents = client.get_torrent_list(
            filter=filter, category=category,
            sort=sort, reverse=reverse, limit=limit,
        )
        return {
            "torrents": torrents,
            "total": len(torrents),
            "client_id": qb_cfg.get("id", ""),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/torrent/add")
def add_torrent(data: dict = Body(...)):
    """添加种子/磁力"""
    url = data.get("url", "").strip()
    if not url:
        raise HTTPException(400, "缺少 url 参数")

    client_id = data.get("client_id")
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)

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
        from quark_cli.rss.torrent_client import is_magnet_url, is_torrent_url, download_torrent_file
        if is_magnet_url(url):
            result = client.add_magnet(url, **kwargs)
        elif is_torrent_url(url) or url.startswith("http"):
            try:
                torrent_bytes, filename = download_torrent_file(url)
                result = client.add_torrent_file(torrent_bytes, filename, **kwargs)
            except Exception:
                result = client.add_torrent_url(url, **kwargs)
        else:
            result = client.add_torrent_url(url, **kwargs)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/torrent/tasks/{info_hash}/pause")
def pause_task(info_hash: str, client_id: str = Query(None)):
    """暂停任务"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)

    try:
        client.login()
        client.pause_torrents([info_hash])
    except Exception as e:
        raise HTTPException(502, "暂停失败: {}".format(e))

    return {"status": "ok"}


@router.post("/torrent/tasks/{info_hash}/resume")
def resume_task(info_hash: str, client_id: str = Query(None)):
    """恢复任务"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)

    try:
        client.login()
        client.resume_torrents([info_hash])
    except Exception as e:
        raise HTTPException(502, "恢复失败: {}".format(e))

    return {"status": "ok"}


@router.delete("/torrent/tasks/{info_hash}")
def delete_task(info_hash: str, client_id: str = Query(None), delete_files: bool = Query(False)):
    """删除任务"""
    cfg = _load_cfg()
    tc = _get_tc(cfg)
    qb_cfg = _resolve_client(tc, client_id)
    client = _build_client(qb_cfg)

    try:
        client.login()
        client.delete_torrents([info_hash], delete_files=delete_files)
    except Exception as e:
        raise HTTPException(502, "删除失败: {}".format(e))

    return {"status": "ok"}
