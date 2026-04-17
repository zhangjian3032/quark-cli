"""
task 子命令 - 自动转存任务管理
"""

import re
import json
from datetime import datetime
from quark_cli import display
from quark_cli.display import is_json_mode, json_out
from quark_cli.api import QuarkAPI
from quark_cli.commands.helpers import get_client, get_config


def handle(args):
    action = getattr(args, "task_action", None)

    if action == "list":
        _list(args)
    elif action == "add":
        _add(args)
    elif action == "remove":
        _remove(args)
    elif action == "run":
        _run(args)
    elif action == "run-one":
        _run_one(args)
    else:
        display.info("用法: quark-cli task {list|add|remove|run|run-one}")


def _list(args):
    """列出所有任务"""
    cfg = get_config(args)
    tasks = cfg.get_tasklist()

    if not tasks:
        if is_json_mode():
            json_out([])
        else:
            display.info("暂无任务，使用 quark-cli task add 添加")
        return

    if is_json_mode():
        json_out(tasks)
        return

    display.header("任务列表 ({} 个)".format(len(tasks)))

    cols = ["#", "任务名称", "保存路径", "结束日期", "运行星期"]
    widths = [4, 32, 28, 14, 16]
    display.table_header(cols, widths)

    for i, task in enumerate(tasks):
        name = task.get("taskname", "未命名")
        path = task.get("savepath", "N/A")
        enddate = task.get("enddate", "永久")
        runweek = task.get("runweek", [])
        week_str = ",".join(str(d) for d in runweek) if runweek else "每天"

        expired = False
        if task.get("enddate"):
            try:
                expired = datetime.now().date() > datetime.strptime(
                    task["enddate"], "%Y-%m-%d"
                ).date()
            except ValueError:
                pass

        name_color = display.Color.DIM if expired else display.Color.WHITE
        display.table_row(
            [str(i + 1), name, path, enddate, week_str],
            widths,
            [display.Color.CYAN, name_color, display.Color.DIM, None, None],
        )
        if expired:
            print("      {}".format(display.colorize("(已过期)", display.Color.RED)))

    print()
    for i, task in enumerate(tasks):
        display.subheader("#{} {}".format(i + 1, task.get("taskname", "未命名")))
        display.kvline("分享链接", task.get("shareurl", "N/A"))
        display.kvline("保存路径", task.get("savepath", "N/A"))
        if task.get("pattern"):
            display.kvline("正则过滤", task["pattern"])
        if task.get("replace"):
            display.kvline("正则替换", task["replace"])
        if task.get("update_subdir"):
            display.kvline("更新子目录", task["update_subdir"])
        if task.get("shareurl_ban"):
            display.kvline("失效记录", display.colorize(task["shareurl_ban"], display.Color.RED))


def _add(args):
    """添加任务"""
    cfg = get_config(args)

    task = {
        "taskname": args.name,
        "shareurl": args.url,
        "savepath": args.savepath,
        "pattern": args.pattern,
        "replace": args.replace,
    }
    if args.enddate:
        task["enddate"] = args.enddate
    if args.runweek:
        task["runweek"] = [int(d) for d in args.runweek.split(",")]

    cfg.load()
    cfg.add_task(task)

    if is_json_mode():
        json_out(task)
        return

    display.success("任务已添加: {}".format(args.name))
    display.kvline("分享链接", args.url)
    display.kvline("保存路径", args.savepath)

    try:
        cookies = cfg.get_cookies()
        if cookies:
            client = QuarkAPI(cookies[0])
            pwd_id, passcode, _, _ = QuarkAPI.extract_share_url(args.url)
            if pwd_id:
                resp = client.get_stoken(pwd_id, passcode)
                if resp.get("status") == 200:
                    display.success("分享链接验证有效 \u2714")
                else:
                    display.warning("分享链接可能无效: {}".format(resp.get("message")))
    except Exception:
        pass


def _remove(args):
    """移除任务"""
    cfg = get_config(args)
    cfg.load()
    tasks = cfg.get_tasklist()
    idx = args.index - 1

    if idx < 0 or idx >= len(tasks):
        display.error("无效的任务序号: {}（共 {} 个任务）".format(args.index, len(tasks)))
        return

    task = tasks[idx]

    if is_json_mode():
        cfg.remove_task(idx)
        json_out({"removed": task.get("taskname", ""), "index": args.index})
        return

    display.warning("即将移除任务: {}".format(task.get("taskname", "未命名")))
    confirm = input("  确认? (y/N): ").strip().lower()
    if confirm == "y":
        cfg.remove_task(idx)
        display.success("任务已移除")
    else:
        display.info("操作已取消")


def _run(args):
    """执行全部任务"""
    cfg = get_config(args)
    cfg.load()
    tasks = cfg.get_tasklist()

    if not tasks:
        display.info("暂无任务")
        return

    client = get_client(args)
    info = client.init()
    if not info:
        display.error("账号验证失败")
        return

    if not is_json_mode():
        display.header("执行全部任务 ({} 个)".format(len(tasks)))
        display.kvline("账号", client.nickname)
        display.kvline("时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    dir_paths = [
        re.sub(r"/{2,}", "/", "/{}".format(t["savepath"]))
        for t in tasks
        if _is_active(t)
    ]
    if dir_paths:
        fids_result = client.get_fids(dir_paths)
        for item in fids_result:
            client.savepath_fid[item["file_path"]] = item["fid"]

    success_count = 0
    skip_count = 0
    fail_count = 0
    results = []

    for i, task in enumerate(tasks):
        if not is_json_mode():
            print()
            display.subheader("#{} {}".format(i + 1, task.get("taskname", "未命名")))
            display.kvline("分享链接", task.get("shareurl", "N/A"))
            display.kvline("保存路径", task.get("savepath", "N/A"))

        if not _is_active(task):
            if not is_json_mode():
                display.info("任务不在运行周期内，跳过")
            skip_count += 1
            results.append({"task": task.get("taskname"), "status": "skipped", "reason": "not_active"})
            continue

        if task.get("shareurl_ban"):
            if not is_json_mode():
                display.warning("链接已失效: {}".format(task["shareurl_ban"]))
            skip_count += 1
            results.append({"task": task.get("taskname"), "status": "skipped", "reason": "banned"})
            continue

        result = _execute_single_task(client, task, cfg)
        if result:
            success_count += 1
            results.append({"task": task.get("taskname"), "status": "success"})
        else:
            fail_count += 1
            results.append({"task": task.get("taskname"), "status": "failed"})

    cfg.save()

    if is_json_mode():
        json_out({"success": success_count, "skipped": skip_count, "failed": fail_count, "details": results})
    else:
        print()
        display.header("执行完毕")
        display.kvline("成功", str(success_count))
        display.kvline("跳过", str(skip_count))
        display.kvline("失败", str(fail_count))


def _run_one(args):
    """执行单个任务"""
    cfg = get_config(args)
    cfg.load()
    tasks = cfg.get_tasklist()
    idx = args.index - 1

    if idx < 0 or idx >= len(tasks):
        display.error("无效的任务序号: {}".format(args.index))
        return

    task = tasks[idx]
    client = get_client(args)
    info = client.init()
    if not info:
        display.error("账号验证失败")
        return

    if not is_json_mode():
        display.header("执行任务: {}".format(task.get("taskname")))
    _execute_single_task(client, task, cfg)
    cfg.save()


def _execute_single_task(client, task, cfg):
    """执行单个转存任务"""
    pwd_id, passcode, pdir_fid, _ = QuarkAPI.extract_share_url(task["shareurl"])
    if not pwd_id:
        display.error("无法解析分享链接")
        return False

    resp = client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        msg = resp.get("message", "未知错误")
        display.error("分享链接无效: {}".format(msg))
        task["shareurl_ban"] = msg
        return False

    stoken = resp["data"]["stoken"]

    detail = client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        display.error("获取分享文件失败: {}".format(detail.get("message")))
        return False

    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享为空")
        task["shareurl_ban"] = "分享为空"
        return False

    if len(file_list) == 1 and file_list[0].get("dir"):
        detail = client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]

    pattern = task.get("pattern", ".*")
    filtered = [f for f in file_list if re.search(pattern, f["file_name"])]

    savepath = re.sub(r"/{2,}", "/", "/{}".format(task["savepath"]))
    if not client.savepath_fid.get(savepath):
        fids = client.get_fids([savepath])
        if fids:
            client.savepath_fid[savepath] = fids[0]["fid"]
        else:
            mkdir_resp = client.mkdir(savepath)
            if mkdir_resp.get("code") == 0:
                client.savepath_fid[savepath] = mkdir_resp["data"]["fid"]
                if not is_json_mode():
                    display.info("已创建目录: {}".format(savepath))
            else:
                display.error("创建目录失败: {}".format(mkdir_resp.get("message")))
                return False

    to_pdir_fid = client.savepath_fid[savepath]

    dir_resp = client.ls_dir(to_pdir_fid)
    existing = []
    if dir_resp.get("code") == 0:
        existing = [f["file_name"] for f in dir_resp["data"]["list"]]

    to_save = [f for f in filtered if f["file_name"] not in existing]

    if not to_save:
        if not is_json_mode():
            display.info("没有需要转存的新文件")
        return True

    if not is_json_mode():
        display.info("发现 {} 个新文件".format(len(to_save)))

    saved_fids = []
    for i in range(0, len(to_save), 100):
        batch = to_save[i : i + 100]
        fid_list = [f["fid"] for f in batch]
        token_list = [f["share_fid_token"] for f in batch]
        save_resp = client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)
        if save_resp.get("code") == 0:
            task_id = save_resp["data"]["task_id"]
            task_resp = client.query_task(task_id)
            if task_resp.get("code") == 0:
                saved_fids.extend(task_resp["data"]["save_as"]["save_as_top_fids"])
        else:
            display.error("转存失败: {}".format(save_resp.get("message")))

    replace = task.get("replace", "")
    if replace and saved_fids:
        for idx, f in enumerate(to_save):
            if idx < len(saved_fids):
                new_name = re.sub(pattern, replace, f["file_name"])
                if new_name != f["file_name"]:
                    client.rename(saved_fids[idx], new_name)

    if not is_json_mode():
        for f in to_save:
            icon = display.file_icon(f)
            display.success("{} {}".format(icon, f["file_name"]))
        display.success("转存完成，共 {} 个文件".format(len(saved_fids)))

    return True


def _is_active(task):
    """判断任务是否在有效期和运行周期内"""
    if task.get("enddate"):
        try:
            if datetime.now().date() > datetime.strptime(task["enddate"], "%Y-%m-%d").date():
                return False
        except ValueError:
            pass
    if task.get("runweek"):
        if (datetime.today().weekday() + 1) not in task["runweek"]:
            return False
    return True
