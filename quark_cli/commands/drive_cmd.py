"""
drive 子命令 - 网盘文件操作（ls/mkdir/rename/download/delete/search）
"""

import re
from quark_cli import display
from quark_cli.display import is_json_mode, json_out
from quark_cli.api import QuarkAPI
from quark_cli.commands.helpers import get_client


def handle(args):
    action = getattr(args, "drive_action", None)

    if action == "ls":
        _ls(args)
    elif action == "mkdir":
        _mkdir(args)
    elif action == "rename":
        _rename(args)
    elif action == "download":
        _download(args)
    elif action == "delete":
        _delete(args)
    elif action == "search":
        _search(args)
    else:
        display.info("用法: quark-cli drive {ls|mkdir|rename|download|delete|search}")


def _ls(args):
    """列出目录内容"""
    client = get_client(args)
    path = args.path

    if path == "/":
        pdir_fid = "0"
    else:
        path_normalized = re.sub(r"/{2,}", "/", "/{}".format(path))
        fids = client.get_fids([path_normalized])
        if not fids:
            display.error("目录不存在: {}".format(path))
            return
        pdir_fid = fids[0]["fid"]

    resp = client.ls_dir(pdir_fid, fetch_full_path=1)
    if resp.get("code") != 0:
        display.error("列出目录失败: {}".format(resp.get("message")))
        return

    file_list = resp["data"]["list"]

    if is_json_mode():
        items = []
        for f in file_list:
            items.append({
                "file_name": f.get("file_name", ""),
                "fid": f.get("fid", ""),
                "size": f.get("size", 0),
                "dir": bool(f.get("dir") or f.get("file_type") == 0),
                "updated_at": f.get("updated_at"),
            })
        json_out({"path": path, "count": len(file_list), "files": items})
        return

    display.header("\U0001f4c2 {}  ({} 项)".format(path, len(file_list)))

    if not file_list:
        display.info("空目录")
        return

    cols = ["", "文件名", "大小", "FID", "修改时间"]
    widths = [4, 38, 12, 36, 18]
    display.table_header(cols, widths)

    for f in file_list:
        icon = display.file_icon(f)
        name = f.get("file_name", "N/A")
        is_dir = f.get("dir") or f.get("file_type") == 0
        size = "<DIR>" if is_dir else display.format_size(f.get("size", 0))
        fid = f.get("fid", "N/A")
        mtime = display.format_time(f.get("updated_at"))
        name_color = display.Color.BLUE if is_dir else display.Color.WHITE
        display.table_row(
            [icon, name, size, fid, mtime],
            widths,
            [None, name_color, display.Color.CYAN, display.Color.DIM, display.Color.DIM],
        )

    total_files = sum(1 for f in file_list if not (f.get("dir") or f.get("file_type") == 0))
    total_dirs = sum(1 for f in file_list if f.get("dir") or f.get("file_type") == 0)
    total_size = sum(
        f.get("size", 0) for f in file_list if not (f.get("dir") or f.get("file_type") == 0)
    )
    print()
    display.info("{} 个文件夹, {} 个文件, 总计 {}".format(
        total_dirs, total_files, QuarkAPI.format_bytes(total_size)))


def _mkdir(args):
    """创建目录"""
    client = get_client(args)
    path = re.sub(r"/{2,}", "/", "/{}".format(args.path))

    info = client.init()
    if not info:
        display.error("账号验证失败")
        return

    resp = client.mkdir(path)
    if resp.get("code") == 0:
        if is_json_mode():
            json_out({"path": path, "fid": resp["data"]["fid"]})
        else:
            display.success("目录已创建: {}".format(path))
            display.kvline("FID", resp["data"]["fid"])
    else:
        display.error("创建失败: {}".format(resp.get("message")))


def _rename(args):
    """重命名文件"""
    client = get_client(args)
    resp = client.rename(args.fid, args.name)
    if resp.get("code") == 0:
        if is_json_mode():
            json_out({"fid": args.fid, "new_name": args.name})
        else:
            display.success("重命名成功 \u2192 {}".format(args.name))
    else:
        display.error("重命名失败: {}".format(resp.get("message")))


def _download(args):
    """获取文件下载链接"""
    client = get_client(args)
    fids = [f.strip() for f in args.fid.split(",")]

    resp, cookie = client.download(fids)
    if resp.get("code") != 0:
        display.error("获取下载链接失败: {}".format(resp.get("message")))
        return

    if is_json_mode():
        items = []
        for item in resp.get("data", []):
            items.append({
                "file_name": item.get("file_name", ""),
                "size": item.get("size", 0),
                "download_url": item.get("download_url", ""),
                "cookie": cookie or "",
            })
        json_out(items)
        return

    display.header("下载链接")
    for item in resp.get("data", []):
        display.kvline("文件名", item.get("file_name", "N/A"))
        display.kvline("大小", QuarkAPI.format_bytes(item.get("size", 0)))
        display.kvline("URL", item.get("download_url", "N/A"))
        if cookie:
            display.kvline("Cookie", cookie)
        display.divider()

    display.info("提示: 下载链接有时效限制，请尽快使用")
    display.info("使用 curl/wget 下载时需携带上方 Cookie")


def _delete(args):
    """删除文件"""
    client = get_client(args)
    fids = args.fid

    if not is_json_mode():
        display.warning("即将删除 {} 个文件/文件夹".format(len(fids)))
        confirm = input("  确认删除? (y/N): ").strip().lower()
        if confirm != "y":
            display.info("操作已取消")
            return

    resp = client.delete(fids)
    if resp.get("code") == 0:
        task_id = resp["data"]["task_id"]
        task_resp = client.query_task(task_id)
        if task_resp.get("code") == 0:
            if is_json_mode():
                json_out({"deleted": len(fids), "fids": fids})
            else:
                display.success("已删除 {} 个文件/文件夹".format(len(fids)))

            if getattr(args, "permanent", False):
                recycle = client.recycle_list()
                records = [
                    r["record_id"] for r in recycle if r.get("fid") in fids
                ]
                if records:
                    client.recycle_remove(records)
                    if not is_json_mode():
                        display.success("已从回收站彻底删除")
        else:
            display.error("删除任务失败: {}".format(task_resp.get("message")))
    else:
        display.error("删除失败: {}".format(resp.get("message")))


def _search(args):
    """搜索网盘文件"""
    client = get_client(args)
    keyword = args.keyword
    search_path = getattr(args, "path", "/")

    if search_path == "/":
        pdir_fid = "0"
    else:
        path_normalized = re.sub(r"/{2,}", "/", "/{}".format(search_path))
        fids = client.get_fids([path_normalized])
        if not fids:
            display.error("目录不存在: {}".format(search_path))
            return
        pdir_fid = fids[0]["fid"]

    resp = client.ls_dir(pdir_fid, fetch_full_path=1)
    if resp.get("code") != 0:
        display.error("搜索失败: {}".format(resp.get("message")))
        return

    file_list = resp["data"]["list"]
    results = [
        f for f in file_list
        if keyword.lower() in f.get("file_name", "").lower()
    ]

    if is_json_mode():
        items = []
        for f in results:
            items.append({
                "file_name": f.get("file_name", ""),
                "fid": f.get("fid", ""),
                "size": f.get("size", 0),
                "dir": bool(f.get("dir") or f.get("file_type") == 0),
            })
        json_out({"keyword": keyword, "path": search_path, "count": len(items), "files": items})
        return

    display.header("搜索: {}".format(keyword))
    display.kvline("搜索范围", search_path)
    print()

    if not results:
        display.warning("未找到匹配文件")
        return

    cols = ["", "文件名", "大小", "FID"]
    widths = [4, 42, 12, 38]
    display.table_header(cols, widths)

    for f in results:
        icon = display.file_icon(f)
        name = f.get("file_name", "N/A")
        is_dir = f.get("dir") or f.get("file_type") == 0
        size = "<DIR>" if is_dir else display.format_size(f.get("size", 0))
        fid = f.get("fid", "N/A")
        display.table_row(
            [icon, name, size, fid],
            widths,
            [None, display.Color.WHITE, display.Color.CYAN, display.Color.DIM],
        )

    print()
    display.info("找到 {} 个匹配结果".format(len(results)))
