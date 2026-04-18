"""
sync 子命令 — WebDAV 挂载目录同步到 NAS 本地

命令:
  quark-cli sync                     按全局配置同步
  quark-cli sync --source /mnt/alist --dest /mnt/nas
  quark-cli sync --delete            同步后删除源
  quark-cli sync status              查看同步状态
"""

import sys
import time

from quark_cli.display import (
    success, error, warning, info, header, kvline, divider,
    format_size, is_json_mode, json_out,
)


def register(subparsers):
    """注册 sync 子命令到 CLI"""
    sync_parser = subparsers.add_parser("sync", help="WebDAV → NAS 本地文件同步")
    sync_sub = sync_parser.add_subparsers(dest="sync_action")

    # sync run (默认)
    sr = sync_sub.add_parser("run", help="执行同步 (默认)")
    sr.add_argument("--source", help="源目录 (WebDAV 挂载路径)")
    sr.add_argument("--dest", help="目标目录 (NAS 本地路径)")
    sr.add_argument("--delete", action="store_true", default=False,
                    help="同步后删除源文件")
    sr.add_argument("--task", help="指定调度任务名称 (使用该任务的同步配置)")
    sr.add_argument("--no-progress", action="store_true", default=False,
                    help="不显示进度条")

    # sync status
    sync_sub.add_parser("status", help="查看同步状态")

    # sync config
    sc = sync_sub.add_parser("config", help="查看/设置同步配置")
    sc.add_argument("--show", action="store_true", help="显示当前配置")
    sc.add_argument("--webdav-mount", help="设置 WebDAV 挂载路径")
    sc.add_argument("--local-dest", help="设置本地目标路径")
    sc.add_argument("--delete-after-sync", choices=["true", "false"],
                    help="设置同步后是否删除源")

    return sync_parser


def handle(args):
    """处理 sync 命令"""
    action = getattr(args, "sync_action", None)

    if action == "status":
        _handle_status(args)
    elif action == "config":
        _handle_config(args)
    else:
        # 默认: run
        _handle_run(args)


def _handle_run(args):
    """执行同步"""
    from quark_cli.commands.helpers import get_config
    from quark_cli.media.sync import sync_files, sync_from_config

    cfg = get_config(args)

    source = getattr(args, "source", None)
    dest = getattr(args, "dest", None)
    delete = getattr(args, "delete", False)
    task_name_filter = getattr(args, "task", None)
    no_progress = getattr(args, "no_progress", False)

    # 进度回调 (终端实时刷新)
    _last_report = [0.0]

    def _progress_cb(progress):
        if no_progress:
            return
        now = time.time()
        if now - _last_report[0] < 0.3:
            return
        _last_report[0] = now

        cf = progress.current_file
        if cf and cf.status == "copying":
            sys.stderr.write(
                "\r\033[K  [{status}] {percent:.1f}%  {speed}  "
                "{copied}/{total}  ▸ {filename}".format(
                    status=progress.status,
                    percent=progress.percent,
                    speed=progress.to_dict()["speed_human"],
                    copied=format_size(progress.copied_bytes),
                    total=format_size(progress.total_bytes),
                    filename=cf.filename[:50],
                )
            )
            sys.stderr.flush()
        elif progress.status in ("done", "error", "cancelled"):
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    try:
        if source and dest:
            # 手动指定源/目标
            header("同步: {} → {}".format(source, dest))
            result = sync_files(
                source_dir=source,
                dest_dir=dest,
                delete_after_sync=delete,
                progress_callback=_progress_cb,
                task_name="manual",
            )
        else:
            # 从配置读取
            task_config = None
            if task_name_filter:
                tasks = cfg.data.get("scheduler", {}).get("tasks", [])
                for t in tasks:
                    if t.get("name") == task_name_filter:
                        task_config = t
                        break
                if not task_config:
                    error("未找到任务: {}".format(task_name_filter))
                    return

            sync_cfg = task_config.get("sync", {}) if task_config else cfg.data.get("sync", {})
            webdav = sync_cfg.get("webdav_mount") or cfg.data.get("sync", {}).get("webdav_mount", "")
            local = sync_cfg.get("local_dest") or cfg.data.get("sync", {}).get("local_dest", "")

            if not webdav or not local:
                error("未配置同步路径")
                info("  请设置: quark-cli sync config --webdav-mount /mnt/alist/夸克 --local-dest /mnt/nas/media")
                info("  或手动: quark-cli sync run --source /mnt/alist/夸克 --dest /mnt/nas/media")
                return

            header("同步: {} → {}".format(webdav, local))

            if delete:
                # CLI 参数覆盖配置
                if task_config:
                    task_config.setdefault("sync", {})["delete_after_sync"] = True
                else:
                    cfg._data.setdefault("sync", {})["delete_after_sync"] = True

            result = sync_from_config(
                config_data=cfg.data,
                task_config=task_config,
                progress_callback=_progress_cb,
            )

        # 输出结果
        if is_json_mode():
            json_out(result.to_dict())
            return

        print()
        if result.status == "done":
            success("同步完成")
        elif result.status == "cancelled":
            warning("同步已取消")
        else:
            error("同步失败")

        kvline("拷贝文件", str(result.copied_files))
        kvline("跳过文件", str(result.skipped_files))
        kvline("失败文件", str(result.error_files))
        if result.deleted_files > 0:
            kvline("已删除源", str(result.deleted_files))
        kvline("总大小", format_size(result.total_bytes))
        kvline("耗时", "{:.1f}s".format(result.elapsed))
        kvline("平均速度", result.to_dict()["speed_human"])

        if result.errors:
            print()
            warning("错误详情:")
            for e in result.errors:
                info("  · {}".format(e))

    except ValueError as e:
        error(str(e))
    except Exception as e:
        error("同步异常: {}".format(e))
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()


def _handle_status(args):
    """查看同步状态"""
    from quark_cli.media.sync import get_sync_manager

    mgr = get_sync_manager()
    all_progress = mgr.get_all_progress()

    if is_json_mode():
        json_out(all_progress)
        return

    if not all_progress:
        info("当前没有同步任务")
        return

    header("同步状态")
    for name, p in all_progress.items():
        divider()
        kvline("任务", name)
        kvline("状态", p["status"])
        kvline("进度", "{}%".format(p["percent"]))
        kvline("速度", p["speed_human"])
        kvline("文件", "{}/{}".format(p["copied_files"], p["total_files"]))
        if p.get("current_file"):
            cf = p["current_file"]
            kvline("当前", "{} ({}%)".format(cf["filename"], cf["percent"]))


def _handle_config(args):
    """同步配置管理"""
    from quark_cli.commands.helpers import get_config

    cfg = get_config(args)
    sync_cfg = cfg.data.get("sync", {})

    show = getattr(args, "show", False)
    webdav = getattr(args, "webdav_mount", None)
    local = getattr(args, "local_dest", None)
    delete_str = getattr(args, "delete_after_sync", None)

    if webdav or local or delete_str:
        if "sync" not in cfg._data:
            cfg._data["sync"] = {}

        if webdav:
            cfg._data["sync"]["webdav_mount"] = webdav
        if local:
            cfg._data["sync"]["local_dest"] = local
        if delete_str:
            cfg._data["sync"]["delete_after_sync"] = delete_str == "true"

        cfg.save()
        success("同步配置已更新")
        sync_cfg = cfg._data["sync"]

    # 显示
    header("同步配置")
    kvline("WebDAV 挂载", sync_cfg.get("webdav_mount", "(未配置)"))
    kvline("本地目标", sync_cfg.get("local_dest", "(未配置)"))
    kvline("同步后删除源", "是" if sync_cfg.get("delete_after_sync") else "否")
    kvline("缓冲区大小", format_size(sync_cfg.get("buffer_size", 8 * 1024 * 1024)))
    exclude = sync_cfg.get("exclude_patterns", [])
    kvline("排除模式", ", ".join(exclude) if exclude else "(无)")
