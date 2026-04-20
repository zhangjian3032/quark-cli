"""
torrent 子命令处理模块 — Torrent 客户端管理
"""

import json
import sys

from quark_cli.display import (
    Color, colorize, success, error, warning, info,
    header, subheader, kvline, divider, table_header, table_row,
    is_json_mode, json_out,
)


# ──────────────────────────────────────────────
# torrent config
# ──────────────────────────────────────────────

def _handle_config(args):
    """torrent config — 配置 qBittorrent 连接"""
    from quark_cli.config import ConfigManager

    config_path = getattr(args, "config", None)
    cfg = ConfigManager(config_path)
    cfg.load()

    show = getattr(args, "show", False)

    if show:
        tc = cfg.data.get("torrent_clients", {})
        if is_json_mode():
            # 隐藏密码
            safe = json.loads(json.dumps(tc))
            for qb in safe.get("qbittorrent", []):
                if qb.get("password"):
                    qb["password"] = "***"
            json_out(safe)
        else:
            if not tc:
                warning("未配置 Torrent 客户端")
                info("配置: quark-cli torrent config --host <ip> --port <port>")
                return
            header("🔧 Torrent 客户端配置")
            kvline("默认客户端", tc.get("default", "(未设置)"))
            for qb in tc.get("qbittorrent", []):
                print()
                subheader("qBittorrent: {}".format(qb.get("name", qb.get("id", "?"))))
                kvline("  ID", qb.get("id", ""))
                kvline("  地址", "{}://{}:{}".format(
                    "https" if qb.get("use_https") else "http",
                    qb.get("host", "?"), qb.get("port", "?")))
                kvline("  用户名", qb.get("username", "admin"))
                kvline("  密码", "***" if qb.get("password") else "(空)")
                kvline("  默认下载路径", qb.get("default_save_path", "(未设置)"))
                kvline("  默认分类", qb.get("default_category", "(未设置)"))
                kvline("  默认标签", ", ".join(qb.get("default_tags", [])) or "(无)")

            # 预留客户端提示
            reserved = tc.get("_reserved", {})
            if reserved:
                print()
                info("预留客户端 (尚未实现):")
                for name, desc in reserved.items():
                    kvline("  " + name, desc)
        return

    # 设置模式
    host = getattr(args, "host", None)
    port = getattr(args, "port", None)
    username = getattr(args, "username", None)
    password = getattr(args, "password", None)
    use_https = getattr(args, "use_https", False)
    save_path = getattr(args, "save_path", None)
    category = getattr(args, "category", None)
    name = getattr(args, "name", None)
    client_id = getattr(args, "id", None)

    if not host and not port and not username and not password:
        error("请至少指定 --host 或 --port")
        info("用法: quark-cli torrent config --host 192.168.1.100 --port 8080 --username admin --password xxx")
        sys.exit(1)

    tc = cfg.data.get("torrent_clients", {})
    if not tc:
        tc = {
            "default": "",
            "qbittorrent": [],
            "_reserved": {
                "transmission": "Transmission RPC — 如有需求请反馈",
                "aria2": "aria2 JSON-RPC — 如有需求请反馈",
            },
        }

    qb_list = tc.get("qbittorrent", [])

    # 查找已有配置或创建新的
    target = None
    for qb in qb_list:
        if client_id and qb.get("id") == client_id:
            target = qb
            break
        elif host and qb.get("host") == host and (not port or qb.get("port") == port):
            target = qb
            break

    if target is None:
        import uuid
        new_id = client_id or "qb_" + uuid.uuid4().hex[:6]
        target = {
            "id": new_id,
            "name": name or "qBittorrent",
            "host": host or "127.0.0.1",
            "port": port or 8080,
            "username": username or "admin",
            "password": password or "",
            "use_https": use_https,
            "default_save_path": save_path or "",
            "default_category": category or "",
            "default_tags": ["quark-cli", "rss"],
        }
        qb_list.append(target)
    else:
        if host is not None:
            target["host"] = host
        if port is not None:
            target["port"] = port
        if username is not None:
            target["username"] = username
        if password is not None:
            target["password"] = password
        if use_https:
            target["use_https"] = use_https
        if save_path is not None:
            target["default_save_path"] = save_path
        if category is not None:
            target["default_category"] = category
        if name is not None:
            target["name"] = name

    tc["qbittorrent"] = qb_list
    if not tc.get("default") and qb_list:
        tc["default"] = qb_list[0]["id"]

    # 写入预留客户端说明
    if "_reserved" not in tc:
        tc["_reserved"] = {
            "transmission": "Transmission RPC — 如有需求请反馈",
            "aria2": "aria2 JSON-RPC — 如有需求请反馈",
        }

    cfg._data["torrent_clients"] = tc
    cfg.save()

    if is_json_mode():
        json_out({"status": "saved", "client_id": target["id"]})
    else:
        success("qBittorrent 配置已保存")
        kvline("ID", target["id"])
        kvline("地址", "{}://{}:{}".format(
            "https" if target.get("use_https") else "http",
            target["host"], target["port"]))
        print()
        info("测试连接: quark-cli torrent test")


# ──────────────────────────────────────────────
# torrent test
# ──────────────────────────────────────────────

def _handle_test(args):
    """torrent test — 测试 qBittorrent 连接"""
    from quark_cli.rss.torrent_client import get_torrent_client

    config_path = getattr(args, "config", None)
    client_id = getattr(args, "client_id", None)

    if not is_json_mode():
        info("正在连接 qBittorrent...")

    try:
        client = get_torrent_client(config_path, client_id)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    result = client.test_connection()

    if is_json_mode():
        json_out(result)
        return

    if result["success"]:
        success("已连接 qBittorrent {} @ {}:{}".format(
            result.get("version", "?"),
            client.host, client.port,
        ))
    else:
        error("连接失败: {}".format(result.get("error", "未知错误")))
        sys.exit(1)


# ──────────────────────────────────────────────
# torrent list
# ──────────────────────────────────────────────

def _handle_list(args):
    """torrent list — 查看下载列表"""
    from quark_cli.rss.torrent_client import get_torrent_client

    config_path = getattr(args, "config", None)
    client_id = getattr(args, "client_id", None)
    filter_type = getattr(args, "filter", "all")
    category = getattr(args, "category", "") or ""
    limit = getattr(args, "limit", 20) or 20

    try:
        client = get_torrent_client(config_path, client_id)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    try:
        torrents = client.get_torrent_list(
            filter=filter_type, category=category, limit=limit)
    except Exception as e:
        error("获取列表失败: {}".format(e))
        sys.exit(1)

    if is_json_mode():
        json_out(torrents)
        return

    if not torrents:
        warning("下载列表为空")
        return

    header("📥 qBittorrent 下载列表 ({})".format(len(torrents)))
    cols = ["名称", "大小", "进度", "状态", "分类"]
    widths = [40, 10, 8, 12, 10]
    table_header(cols, widths)

    for t in torrents:
        name = t.get("name", "?")[:38]
        size = _format_size(t.get("size", 0))
        progress = "{:.1f}%".format(t.get("progress", 0) * 100)
        state = t.get("state", "?")
        cat = t.get("category", "-")[:8]

        state_color = Color.GREEN if state in ("uploading", "stalledUP") else (
            Color.CYAN if state in ("downloading", "stalledDL") else Color.DIM)

        table_row(
            [name, size, progress, state, cat],
            widths,
            colors=[None, Color.YELLOW, Color.GREEN, state_color, Color.DIM],
        )


# ──────────────────────────────────────────────
# torrent add
# ──────────────────────────────────────────────

def _handle_add(args):
    """torrent add <url_or_magnet> — 手动添加种子"""
    from quark_cli.rss.torrent_client import (
        get_torrent_client, is_magnet_url, is_torrent_url, download_torrent_file,
    )

    config_path = getattr(args, "config", None)
    client_id = getattr(args, "client_id", None)
    url = args.url
    save_path = getattr(args, "save_path", "") or ""
    category = getattr(args, "category", "") or ""
    paused = getattr(args, "paused", False)

    try:
        client = get_torrent_client(config_path, client_id)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    if not is_json_mode():
        info("正在推送到 qBittorrent...")

    try:
        if is_magnet_url(url):
            result = client.add_magnet(url, save_path=save_path, category=category, paused=paused)
        elif is_torrent_url(url) or url.startswith("http"):
            # 先尝试下载 torrent 文件再上传 (更可靠)
            try:
                torrent_bytes, filename = download_torrent_file(url)
                result = client.add_torrent_file(
                    torrent_bytes, filename,
                    save_path=save_path, category=category, paused=paused)
            except Exception:
                # 回退到 URL 模式
                result = client.add_torrent_url(url, save_path=save_path, category=category, paused=paused)
        else:
            error("不支持的链接格式: {}".format(url[:80]))
            sys.exit(1)
    except Exception as e:
        error("推送失败: {}".format(e))
        sys.exit(1)

    if is_json_mode():
        json_out(result)
        return

    if result.get("success"):
        success("已添加到 qBittorrent")
        if result.get("hash"):
            kvline("Hash", result["hash"])
        if save_path:
            kvline("保存路径", save_path)
    else:
        error("添加失败: {}".format(result.get("error", "未知错误")))
        sys.exit(1)


# ──────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────

def _format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes <= 0:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return "{:.1f} {}".format(size_bytes, unit)
        size_bytes /= 1024.0
    return "{:.1f} PB".format(size_bytes)


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def handle(args):
    """torrent 命令分发"""
    action = getattr(args, "torrent_action", None)

    if action == "config":
        _handle_config(args)
    elif action == "test":
        _handle_test(args)
    elif action == "list":
        _handle_list(args)
    elif action == "add":
        _handle_add(args)
    else:
        error("用法: quark-cli torrent {config|test|list|add}")
        print()
        print("  Torrent 客户端管理 — qBittorrent Web API")
        print()
        print("  config    配置 qBittorrent 连接")
        print("  test      测试连接")
        print("  list      查看下载列表")
        print("  add       手动添加种子/磁力链接")
        print()
        print("  示例:")
        print('    quark-cli torrent config --host 192.168.1.100 --port 8080 --username admin --password xxx')
        print('    quark-cli torrent test')
        print('    quark-cli torrent add "magnet:?xt=urn:btih:xxxx"')
        print('    quark-cli torrent add "https://example.com/file.torrent"')
