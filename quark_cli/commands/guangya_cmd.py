"""
guangya 子命令 - 光鸭云盘操作
  guangya config  - 凭证管理
  guangya account - 账号 / 空间
  guangya ls      - 列目录
  guangya mkdir   - 创建目录
  guangya rename  - 重命名
  guangya delete  - 删除
  guangya download - 获取下载链接
  guangya cloud   - 云添加 (磁力 / 种子)
"""

from quark_cli import display
from quark_cli.display import is_json_mode, json_out


def _get_guangya_client(args):
    """从配置中构建 GuangyaAPI 客户端"""
    from quark_cli.config import ConfigManager
    from quark_cli.guangya_api import GuangyaAPI

    cfg = ConfigManager(getattr(args, "config", None))
    cfg.load()
    gy = cfg.data.get("guangya", {})
    refresh_token = gy.get("refresh_token", "")
    if not refresh_token:
        display.error("未配置光鸭云盘凭证，请先执行: quark-cli guangya config set --refresh-token <TOKEN>")
        raise SystemExit(1)
    return GuangyaAPI(refresh_token=refresh_token)


def _get_service(args):
    from quark_cli.services.guangya_drive_service import GuangyaDriveService
    return GuangyaDriveService(_get_guangya_client(args))


# ───── 入口分发 ─────

def handle(args):
    action = getattr(args, "guangya_action", None)

    if action == "config":
        _config(args)
    elif action == "account":
        _account(args)
    elif action == "ls":
        _ls(args)
    elif action == "mkdir":
        _mkdir(args)
    elif action == "rename":
        _rename(args)
    elif action == "delete":
        _delete(args)
    elif action == "download":
        _download(args)
    elif action == "sync":
        _sync(args)
    elif action == "cloud":
        _cloud(args)
    else:
        display.info("用法: quark-cli guangya {config|account|ls|mkdir|rename|delete|download|sync|cloud}")


# ═══════════════════════════════════════
# config
# ═══════════════════════════════════════

def _config(args):
    sub = getattr(args, "guangya_config_action", None)
    if sub == "set":
        _config_set(args)
    elif sub == "show":
        _config_show(args)
    else:
        display.info("用法: quark-cli guangya config {set|show}")


def _config_set(args):
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(getattr(args, "config", None))
    cfg.load()
    gy = cfg.data.setdefault("guangya", {})

    refresh_token = getattr(args, "refresh_token", None)

    if refresh_token is not None:
        gy["refresh_token"] = refresh_token.strip()

    cfg._data["guangya"] = gy
    cfg.save()

    if is_json_mode():
        json_out({"status": "updated"})
    else:
        display.success("光鸭云盘凭证已更新")
        if refresh_token is not None:
            preview = "{}...{}".format(refresh_token[:6], refresh_token[-4:]) if len(refresh_token) > 10 else "***"
            display.kvline("Refresh Token", preview)


def _config_show(args):
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(getattr(args, "config", None))
    cfg.load()
    gy = cfg.data.get("guangya", {})
    rt = gy.get("refresh_token", "")

    if is_json_mode():
        json_out({
            "has_refresh_token": bool(rt),
        })
        return

    display.header("光鸭云盘配置")
    if rt:
        display.kvline("Refresh Token", "{}...{}".format(rt[:6], rt[-4:]))
    else:
        display.kvline("Refresh Token", "(未设置)")
    display.info("")
    display.info("设置凭证: quark-cli guangya config set --did <DID> --refresh-token <TOKEN>")
    display.info("获取方式: 在 guangyapan.com 打开 F12 控制台，粘贴执行:")
    display.info('  JSON.parse(localStorage.getItem("credentials_aMe-8VSlkrbQXpUR")||"{}").refresh_token')
    display.info("然后: quark-cli guangya config set --refresh-token <token>")


# ═══════════════════════════════════════
# account
# ═══════════════════════════════════════

def _account(args):
    from quark_cli.guangya_api import GuangyaAPI
    client = _get_guangya_client(args)
    info = client.init()
    if not info:
        display.error("凭证无效，请检查 DID 和 Refresh Token")
        return

    if is_json_mode():
        json_out(info)
        return

    display.header("光鸭云盘账号")
    display.kvline("昵称", info.get("nickName", "N/A"))
    display.kvline("VIP", "是" if info.get("vipStatus") else "否")
    display.kvline("总空间", GuangyaAPI.format_bytes(info.get("totalSpaceSize", 0)))
    display.kvline("已用", GuangyaAPI.format_bytes(info.get("usedSpaceSize", 0)))
    total = info.get("totalSpaceSize", 0)
    used = info.get("usedSpaceSize", 0)
    if total > 0:
        pct = used / total * 100
        display.kvline("使用率", "{:.1f}%".format(pct))


# ═══════════════════════════════════════
# ls
# ═══════════════════════════════════════

def _ls(args):
    from quark_cli.guangya_api import GuangyaAPI
    svc = _get_service(args)
    parent_id = getattr(args, "parent_id", "") or ""

    result = svc.list_dir(parent_id)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
        return

    display.header("\U0001f4c2 光鸭云盘  ({} 项)".format(result["total"]))

    items = result["items"]
    if not items:
        display.info("空目录")
        return

    cols = ["", "文件名", "大小", "FileID"]
    widths = [4, 42, 12, 38]
    display.table_header(cols, widths)

    for f in items:
        icon = "\U0001f4c1" if f["is_dir"] else "\U0001f4c4"
        name = f["fileName"]
        size = f["size_fmt"]
        fid = f["fileId"]
        name_color = display.Color.BLUE if f["is_dir"] else display.Color.WHITE
        display.table_row(
            [icon, name, size, fid],
            widths,
            [None, name_color, display.Color.CYAN, display.Color.DIM],
        )

    print()
    display.info("{} 个文件夹, {} 个文件, 总计 {}".format(
        result["dirs_count"], result["files_count"], result["total_size_fmt"]))


# ═══════════════════════════════════════
# mkdir
# ═══════════════════════════════════════

def _mkdir(args):
    svc = _get_service(args)
    dir_name = args.dir_name
    parent_id = getattr(args, "parent_id", "") or ""

    result = svc.mkdir(dir_name, parent_id=parent_id)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
    else:
        display.success("目录已创建: {}".format(result.get("fileName", dir_name)))
        display.kvline("FileID", result.get("fileId", ""))


# ═══════════════════════════════════════
# rename
# ═══════════════════════════════════════

def _rename(args):
    svc = _get_service(args)
    result = svc.rename(args.file_id, args.new_name)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
    else:
        display.success("重命名成功 → {}".format(args.new_name))


# ═══════════════════════════════════════
# delete
# ═══════════════════════════════════════

def _delete(args):
    svc = _get_service(args)
    file_ids = args.file_id

    if not is_json_mode():
        display.warning("即将删除 {} 个文件/文件夹".format(len(file_ids)))
        confirm = input("  确认删除? (y/N): ").strip().lower()
        if confirm != "y":
            display.info("操作已取消")
            return

    result = svc.delete(file_ids)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
    else:
        display.success("已删除 {} 个文件/文件夹".format(result.get("deleted", 0)))


# ═══════════════════════════════════════
# download
# ═══════════════════════════════════════

def _download(args):
    from quark_cli.guangya_api import GuangyaAPI
    svc = _get_service(args)

    save_dir = getattr(args, "save_dir", None)

    # 如果指定了 --save-dir，下载到服务器本地
    if save_dir:
        if not save_dir.strip():
            # 从配置读取默认目录
            from quark_cli.config import ConfigManager
            cfg = ConfigManager(getattr(args, "config", None))
            cfg.load()
            save_dir = cfg.data.get("guangya", {}).get("download_dir", "/downloads/guangya")

        display.info("正在下载到 {} ...".format(save_dir))
        result = svc.download_to_local(args.file_id, save_dir)
        if "error" in result:
            display.error(result["error"])
            return

        if is_json_mode():
            json_out(result)
            return

        display.success("下载完成")
        display.kvline("文件", result.get("fileName", ""))
        display.kvline("路径", result.get("path", ""))
        display.kvline("大小", result.get("size_fmt", ""))
        return

    # 默认: 仅获取下载链接
    result = svc.get_download_url(args.file_id)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
        return

    display.header("下载链接")
    display.kvline("URL", result.get("signedURL", "N/A"))
    display.kvline("有效期", "{}s".format(result.get("urlDuration", 0)))
    display.info("提示: 下载链接有时效限制，请尽快使用")
    display.info("提示: 使用 --save-dir <目录> 可直接下载到服务器")




# ═══════════════════════════════════════
# sync (递归下载)
# ═══════════════════════════════════════

def _sync(args):
    """递归下载目录/文件到本地 — 类似 rsync"""
    import time
    import sys as _sys
    from quark_cli.guangya_api import GuangyaAPI
    from quark_cli.services.guangya_sync import SyncManager, SyncTask

    client = _get_guangya_client(args)
    file_id = args.file_id
    save_dir = getattr(args, "save_dir", None)
    skip_existing = not getattr(args, "no_skip", False)

    if not save_dir:
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(getattr(args, "config", None))
        cfg.load()
        save_dir = cfg.data.get("guangya", {}).get("download_dir", "/downloads/guangya")

    display.header("光鸭云盘 Sync")
    display.kvline("目标目录", save_dir)
    display.kvline("跳过已存在", "是" if skip_existing else "否")
    display.info("")

    mgr = SyncManager()
    task = mgr.create_task(client, file_id, save_dir, skip_existing=skip_existing)

    # 轮询显示进度
    last_log_idx = 0
    try:
        while task.status in (SyncTask.STATUS_PENDING, SyncTask.STATUS_RUNNING):
            time.sleep(0.5)

            # 输出新日志
            logs = task.log[last_log_idx:]
            for line in logs:
                print(line)
            last_log_idx = len(task.log)

            # 进度条
            if task.total_bytes > 0 and task.status == SyncTask.STATUS_RUNNING:
                pct = task.done_bytes / task.total_bytes * 100
                done_fmt = GuangyaAPI.format_bytes(task.done_bytes)
                total_fmt = GuangyaAPI.format_bytes(task.total_bytes)
                bar_w = 30
                filled = int(bar_w * pct / 100)
                bar = "█" * filled + "░" * (bar_w - filled)
                _sys.stdout.write(
                    "\r  [{bar}] {pct:.1f}%  {done}/{total}  "
                    "{df}/{tf} 文件  当前: {cur}    ".format(
                        bar=bar, pct=pct,
                        done=done_fmt, total=total_fmt,
                        df=task.done_files, tf=task.total_files,
                        cur=task.current_file[:40] if task.current_file else "",
                    )
                )
                _sys.stdout.flush()

    except KeyboardInterrupt:
        display.info("")
        display.warning("正在取消...")
        task.cancel()
        time.sleep(1)

    # 最终状态
    print()
    logs = task.log[last_log_idx:]
    for line in logs:
        print(line)

    info = task.to_dict()
    if is_json_mode():
        json_out(info)
        return

    print()
    if task.status == SyncTask.STATUS_DONE:
        display.success("Sync 完成")
    elif task.status == SyncTask.STATUS_CANCELLED:
        display.warning("Sync 已取消")
    else:
        display.error("Sync 失败: {}".format(task.error))

    display.kvline("文件", "{}/{} (跳过 {}, 失败 {})".format(
        info["done_files"], info["total_files"],
        info["skipped_files"], info["failed_files"]))
    display.kvline("大小", "{} / {}".format(info["done_bytes_fmt"], info["total_bytes_fmt"]))
    display.kvline("耗时", "{:.1f}s".format(info["elapsed"]))
    if info["speed_fmt"]:
        display.kvline("速度", info["speed_fmt"])


# ═══════════════════════════════════════
# cloud (云添加)
# ═══════════════════════════════════════

def _cloud(args):
    sub = getattr(args, "guangya_cloud_action", None)
    if sub == "magnet":
        _cloud_magnet(args)
    elif sub == "torrent":
        _cloud_torrent(args)
    elif sub == "create":
        _cloud_create(args)
    elif sub == "list":
        _cloud_list(args)
    elif sub == "delete":
        _cloud_delete(args)
    else:
        display.info("用法: quark-cli guangya cloud {magnet|torrent|create|list|delete}")


def _cloud_magnet(args):
    svc = _get_service(args)
    result = svc.resolve_magnet(args.url)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
        return

    display.header("磁力解析结果")
    display.kvline("名称", result.get("fileName", "N/A"))
    files = result.get("files", [])
    display.kvline("文件数", str(len(files)))
    for i, f in enumerate(files):
        display.info("  [{}] {} ({})".format(
            i, f.get("fileName", ""), f.get("size_fmt", "")))


def _cloud_torrent(args):
    svc = _get_service(args)
    result = svc.resolve_torrent(args.torrent_path)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
        return

    display.header("种子解析结果")
    display.kvline("名称", result.get("fileName", "N/A"))
    files = result.get("files", [])
    display.kvline("文件数", str(len(files)))
    for i, f in enumerate(files):
        display.info("  [{}] {} ({})".format(
            i, f.get("fileName", ""), f.get("size_fmt", "")))


def _cloud_create(args):
    svc = _get_service(args)
    url = args.url
    parent_id = getattr(args, "parent_id", "") or ""
    file_indexes = getattr(args, "file_indexes", None)
    new_name = getattr(args, "new_name", None)

    # 解析 file_indexes
    idx_list = None
    if file_indexes:
        idx_list = [int(x.strip()) for x in file_indexes.split(",")]

    result = svc.create_cloud_task(
        url=url, parent_id=parent_id,
        file_indexes=idx_list, new_name=new_name,
    )
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
    else:
        display.success("云添加任务已创建")
        display.kvline("TaskID", result.get("taskId", "N/A"))


def _cloud_list(args):
    from quark_cli.guangya_api import GuangyaAPI
    svc = _get_service(args)
    status = getattr(args, "status", None)
    result = svc.list_cloud_tasks(status=status)
    if isinstance(result, dict) and "error" in result:
        display.error(result["error"])
        return

    # result 是 {statusCounts, list, total, cursor}
    tasks = result.get("list", []) if isinstance(result, dict) else result

    if is_json_mode():
        json_out({"tasks": tasks, "total": len(tasks)})
        return

    STATUS_MAP = {0: "等待中", 1: "下载中", 2: "已完成", 3: "失败"}

    display.header("云添加任务 ({} 项)".format(len(tasks)))
    if not tasks:
        display.info("暂无任务")
        return

    for t in tasks:
        st = t.get("status", -1)
        label = STATUS_MAP.get(st, "未知({})".format(st))
        display.kvline("任务", t.get("fileName", "N/A"))
        display.kvline("  状态", label)
        display.kvline("  TaskID", t.get("taskId", ""))
        if t.get("fileSize"):
            display.kvline("  大小", GuangyaAPI.format_bytes(t["fileSize"]))
        display.info("")


def _cloud_delete(args):
    svc = _get_service(args)
    task_ids = args.task_id
    result = svc.delete_cloud_tasks(task_ids)
    if "error" in result:
        display.error(result["error"])
        return

    if is_json_mode():
        json_out(result)
    else:
        display.success("已删除 {} 个云添加任务".format(len(task_ids)))
