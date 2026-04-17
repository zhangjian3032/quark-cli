"""
share 子命令 - 分享链接检查/列出/转存
"""

import re
from quark_cli import display
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

    display.header("检查分享链接")
    display.kvline("分享 ID", pwd_id)
    if passcode:
        display.kvline("提取码", passcode)
    if paths:
        display.kvline("子目录", " / ".join(p["name"] for p in paths))

    resp = client.get_stoken(pwd_id, passcode)
    status = resp.get("status")
    if status == 200:
        display.success("分享链接有效 ✔")
        stoken = resp["data"]["stoken"]
        # 获取分享信息
        detail = client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]
            display.kvline("文件数量", str(len(file_list)))
            total_size = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
            if total_size > 0:
                display.kvline("总大小", QuarkAPI.format_bytes(total_size))
    else:
        msg = resp.get("message", "未知错误")
        display.error(f"分享链接无效: {msg}")


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
        display.error(f"分享链接无效: {resp.get('message')}")
        return

    stoken = resp["data"]["stoken"]
    detail = client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
    if detail.get("code") != 0:
        display.error(f"获取分享详情失败: {detail.get('message')}")
        return

    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享中没有文件")
        return

    display.header(f"分享文件列表 ({len(file_list)} 项)")

    # 表格输出
    cols = ["类型", "文件名", "大小", "修改时间"]
    widths = [6, 40, 12, 18]
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

    # 统计
    total_files = sum(1 for f in file_list if not f.get("dir"))
    total_dirs = sum(1 for f in file_list if f.get("dir"))
    total_size = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
    print()
    display.info(f"共 {total_files} 个文件, {total_dirs} 个文件夹, 总计 {QuarkAPI.format_bytes(total_size)}")

    if getattr(args, "tree", False):
        _list_tree(client, pwd_id, stoken, file_list, indent=0)


def _list_tree(client, pwd_id, stoken, file_list, indent=0):
    """递归树形打印"""
    for f in file_list:
        if f.get("dir"):
            prefix = "  " * (indent + 1) + "├── 📁 "
            print(f"{prefix}{f['file_name']}/")
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

    # 验证初始化
    info = client.init()
    if not info:
        display.error("账号验证失败，请检查 Cookie")
        return

    display.header(f"转存到: {savepath}")
    display.kvline("账号", client.nickname)
    display.kvline("分享 ID", pwd_id)
    display.kvline("正则过滤", pattern)
    if replace:
        display.kvline("正则替换", replace)

    # 获取 stoken
    resp = client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        display.error(f"分享链接无效: {resp.get('message')}")
        return
    stoken = resp["data"]["stoken"]

    # 获取分享文件列表
    detail = client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        display.error(f"获取分享文件失败: {detail.get('message')}")
        return
    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享中没有文件")
        return

    # 如果只有一个文件夹，自动进入
    if len(file_list) == 1 and file_list[0].get("dir"):
        display.info(f"自动进入子目录: {file_list[0]['file_name']}")
        detail = client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]

    # 正则过滤
    filtered = [f for f in file_list if re.search(pattern, f["file_name"])]
    if not filtered:
        display.warning("没有匹配正则的文件")
        return

    display.info(f"匹配 {len(filtered)}/{len(file_list)} 个文件")
    for f in filtered:
        icon = display.file_icon(f)
        size = display.format_size(f.get("size", 0)) if not f.get("dir") else "<DIR>"
        print(f"    {icon} {f['file_name']}  ({size})")

    # 确保目标目录存在
    savepath_normalized = re.sub(r"/{2,}", "/", f"/{savepath}")
    fids = client.get_fids([savepath_normalized])
    if fids:
        to_pdir_fid = fids[0]["fid"]
    else:
        display.info(f"目录不存在，自动创建: {savepath_normalized}")
        mkdir_resp = client.mkdir(savepath_normalized)
        if mkdir_resp.get("code") != 0:
            display.error(f"创建目录失败: {mkdir_resp.get('message')}")
            return
        to_pdir_fid = mkdir_resp["data"]["fid"]

    # 获取已存在文件
    dir_resp = client.ls_dir(to_pdir_fid)
    existing = []
    if dir_resp.get("code") == 0:
        existing = [f["file_name"] for f in dir_resp["data"]["list"]]

    # 过滤已存在
    to_save = [f for f in filtered if f["file_name"] not in existing]
    skipped = len(filtered) - len(to_save)
    if skipped > 0:
        display.info(f"跳过 {skipped} 个已存在的文件")

    if not to_save:
        display.success("没有需要转存的新文件")
        return

    display.subheader(f"开始转存 {len(to_save)} 个文件")

    # 分批转存（每次 100 个）
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
                display.success(f"批次 {i // 100 + 1}: 转存 {len(batch)} 个文件成功")
            else:
                display.error(f"批次 {i // 100 + 1}: 查询任务失败 - {task_resp.get('message')}")
        else:
            display.error(f"批次 {i // 100 + 1}: 转存失败 - {save_resp.get('message')}")

    # 重命名
    if replace and saved_fids:
        display.subheader("文件重命名")
        for idx, f in enumerate(to_save):
            if idx < len(saved_fids):
                new_name = re.sub(pattern, replace, f["file_name"])
                if new_name != f["file_name"]:
                    rn_resp = client.rename(saved_fids[idx], new_name)
                    if rn_resp.get("code") == 0:
                        display.success(f"{f['file_name']} → {new_name}")
                    else:
                        display.warning(f"重命名失败: {rn_resp.get('message')}")

    print()
    display.success(f"转存完成！共转存 {len(saved_fids)} 个文件到 {savepath_normalized}")
