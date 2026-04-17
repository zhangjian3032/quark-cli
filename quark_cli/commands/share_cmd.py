"""
share 子命令 - 分享链接检查/列出/转存
"""

import re
from quark_cli import display
from quark_cli.display import is_json_mode, json_out
from quark_cli.api import QuarkAPI
from quark_cli.commands.helpers import get_client


def handle(args):
    action = getattr(args, "share_action", None)

    if action == "check":
        _check(args)
    elif action == "list":
        _list(args)
    elif action == "save":
        _save(args)
    else:
        display.info("用法: quark-cli share {check|list|save}")


def _check(args):
    """检查分享链接是否有效"""
    client = get_client(args)
    url = args.url
    pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)

    if not pwd_id:
        display.error("无法解析分享链接，请检查 URL 格式")
        return

    resp = client.get_stoken(pwd_id, passcode)
    status = resp.get("status")

    if is_json_mode():
        data = {"url": url, "pwd_id": pwd_id, "valid": status == 200}
        if status == 200:
            stoken = resp["data"]["stoken"]
            detail = client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
            if detail.get("code") == 0:
                file_list = detail["data"]["list"]
                data["file_count"] = len(file_list)
                data["total_size"] = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
        else:
            data["error"] = resp.get("message", "未知错误")
        json_out(data)
        return

    display.header("检查分享链接")
    display.kvline("分享 ID", pwd_id)
    if passcode:
        display.kvline("提取码", passcode)
    if paths:
        display.kvline("子目录", " / ".join(p["name"] for p in paths))

    if status == 200:
        display.success("分享链接有效 \u2714")
        stoken = resp["data"]["stoken"]
        detail = client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]
            display.kvline("文件数量", str(len(file_list)))
            total_size = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
            if total_size > 0:
                display.kvline("总大小", QuarkAPI.format_bytes(total_size))
    else:
        msg = resp.get("message", "未知错误")
        display.error("分享链接无效: {}".format(msg))


def _list(args):
    """列出分享链接中的文件"""
    client = get_client(args)
    url = args.url
    pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)

    if not pwd_id:
        display.error("无法解析分享链接")
        return

    resp = client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        display.error("分享链接无效: {}".format(resp.get("message")))
        return

    stoken = resp["data"]["stoken"]
    detail = client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
    if detail.get("code") != 0:
        display.error("获取分享详情失败: {}".format(detail.get("message")))
        return

    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享中没有文件")
        return

    if is_json_mode():
        items = []
        for f in file_list:
            items.append({
                "file_name": f.get("file_name", ""),
                "fid": f.get("fid", ""),
                "size": f.get("size", 0),
                "dir": bool(f.get("dir")),
                "updated_at": f.get("updated_at"),
            })
        json_out({"url": url, "count": len(file_list), "files": items})
        return

    display.header("分享文件列表 ({} 项)".format(len(file_list)))

    cols = ["类型", "文件名", "大小", "修改时间"]
    widths = [6, 42, 12, 18]
    display.table_header(cols, widths)

    for f in file_list:
        icon = display.file_icon(f)
        name = f.get("file_name", "N/A")
        size = display.format_size(f.get("size", 0)) if not f.get("dir") else "<DIR>"
        mtime = display.format_time(f.get("updated_at"))
        display.table_row(
            [icon, name, size, mtime],
            widths,
            [None, display.Color.WHITE, display.Color.CYAN, display.Color.DIM],
        )

    total_files = sum(1 for f in file_list if not f.get("dir"))
    total_dirs = sum(1 for f in file_list if f.get("dir"))
    total_size = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
    print()
    display.info("共 {} 个文件, {} 个文件夹, 总计 {}".format(
        total_files, total_dirs, QuarkAPI.format_bytes(total_size)))

    if getattr(args, "tree", False):
        _list_tree(client, pwd_id, stoken, file_list, indent=0)


def _list_tree(client, pwd_id, stoken, file_list, indent=0):
    """递归树形打印"""
    for f in file_list:
        if f.get("dir"):
            prefix = "  " * (indent + 1) + "\u251c\u2500\u2500 \U0001f4c1 "
            print("{}{}/ ".format(prefix, f["file_name"]))
            sub_detail = client.get_share_detail(pwd_id, stoken, f["fid"])
            if sub_detail.get("code") == 0:
                _list_tree(client, pwd_id, stoken, sub_detail["data"]["list"], indent + 1)


def _save(args):
    """转存分享链接到指定目录"""
    client = get_client(args)
    url = args.url
    savepath = args.savepath
    pattern = getattr(args, "pattern", ".*")
    replace = getattr(args, "replace", "")

    pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)
    if not pwd_id:
        display.error("无法解析分享链接")
        return

    info = client.init()
    if not info:
        display.error("账号验证失败，请检查 Cookie")
        return

    if not is_json_mode():
        display.header("转存到: {}".format(savepath))
        display.kvline("账号", client.nickname)
        display.kvline("分享 ID", pwd_id)
        display.kvline("正则过滤", pattern)
        if replace:
            display.kvline("正则替换", replace)

    resp = client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        display.error("分享链接无效: {}".format(resp.get("message")))
        return
    stoken = resp["data"]["stoken"]

    detail = client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        display.error("获取分享文件失败: {}".format(detail.get("message")))
        return
    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享中没有文件")
        return

    if len(file_list) == 1 and file_list[0].get("dir"):
        if not is_json_mode():
            display.info("自动进入子目录: {}".format(file_list[0]["file_name"]))
        detail = client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]

    filtered = [f for f in file_list if re.search(pattern, f["file_name"])]
    if not filtered:
        display.warning("没有匹配正则的文件")
        return

    if not is_json_mode():
        display.info("匹配 {}/{} 个文件".format(len(filtered), len(file_list)))
        for f in filtered:
            icon = display.file_icon(f)
            size = display.format_size(f.get("size", 0)) if not f.get("dir") else "<DIR>"
            print("    {} {}  ({})".format(icon, f["file_name"], size))

    savepath_normalized = re.sub(r"/{2,}", "/", "/{}".format(savepath))
    fids = client.get_fids([savepath_normalized])
    if fids:
        to_pdir_fid = fids[0]["fid"]
    else:
        if not is_json_mode():
            display.info("目录不存在，自动创建: {}".format(savepath_normalized))
        mkdir_resp = client.mkdir(savepath_normalized)
        if mkdir_resp.get("code") != 0:
            display.error("创建目录失败: {}".format(mkdir_resp.get("message")))
            return
        to_pdir_fid = mkdir_resp["data"]["fid"]

    dir_resp = client.ls_dir(to_pdir_fid)
    existing = []
    if dir_resp.get("code") == 0:
        existing = [f["file_name"] for f in dir_resp["data"]["list"]]

    to_save = [f for f in filtered if f["file_name"] not in existing]
    skipped = len(filtered) - len(to_save)
    if skipped > 0 and not is_json_mode():
        display.info("跳过 {} 个已存在的文件".format(skipped))

    if not to_save:
        if is_json_mode():
            json_out({"saved": 0, "skipped": skipped, "path": savepath_normalized})
        else:
            display.success("没有需要转存的新文件")
        return

    if not is_json_mode():
        display.subheader("开始转存 {} 个文件".format(len(to_save)))

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
                new_fids = task_resp["data"]["save_as"]["save_as_top_fids"]
                saved_fids.extend(new_fids)
                if not is_json_mode():
                    display.success("批次 {}: 转存 {} 个文件成功".format(i // 100 + 1, len(batch)))
            else:
                display.error("批次 {}: 查询任务失败 - {}".format(i // 100 + 1, task_resp.get("message")))
        else:
            display.error("批次 {}: 转存失败 - {}".format(i // 100 + 1, save_resp.get("message")))

    if replace and saved_fids and not is_json_mode():
        display.subheader("文件重命名")
        for idx, f in enumerate(to_save):
            if idx < len(saved_fids):
                new_name = re.sub(pattern, replace, f["file_name"])
                if new_name != f["file_name"]:
                    rn_resp = client.rename(saved_fids[idx], new_name)
                    if rn_resp.get("code") == 0:
                        display.success("{} \u2192 {}".format(f["file_name"], new_name))
                    else:
                        display.warning("重命名失败: {}".format(rn_resp.get("message")))

    if is_json_mode():
        json_out({
            "saved": len(saved_fids),
            "skipped": skipped,
            "path": savepath_normalized,
            "fids": saved_fids,
        })
    else:
        print()
        display.success("转存完成！共转存 {} 个文件到 {}".format(len(saved_fids), savepath_normalized))
