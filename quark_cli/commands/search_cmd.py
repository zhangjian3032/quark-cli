"""
search 子命令 - 网盘资源搜索（pansou / funletu 等搜索引擎）
"""

from quark_cli import display
from quark_cli.search import PanSearch
from quark_cli.commands.helpers import get_config, get_client
from quark_cli.api import QuarkAPI


def handle(args):
    action = getattr(args, "search_action", None)

    if action == "query":
        _query(args)
    elif action == "sources":
        _sources(args)
    elif action == "set-source":
        _set_source(args)
    elif action == "save":
        _search_and_save(args)
    else:
        display.info("用法: quark-cli search {query|sources|set-source|save}")


def _query(args):
    """搜索网盘资源"""
    cfg = get_config(args)
    cfg.load()
    searcher = PanSearch(cfg)

    keyword = args.keyword
    source = getattr(args, "source", None)

    display.header(f"搜索: {keyword}")

    if source == "all" or not source:
        result = searcher.search_all(keyword)
    else:
        result = searcher.search(keyword, source)

    if not result["success"]:
        display.error(result.get("error", "搜索失败"))
        avail = result.get("available_sources")
        if avail:
            display.info(f"可用搜索源: {', '.join(avail)}")
        return

    results = result.get("results", [])
    if not results:
        display.warning("未找到相关资源")
        if result.get("source_url"):
            display.info(f"搜索页面: {result['source_url']}")
        return

    total = result.get("total", len(results))
    display.info(f"找到 {total} 个结果，显示 {len(results)} 个\n")

    # 判断是否有密码列
    has_pwd = any(r.get("password") for r in results)

    if has_pwd:
        cols = ["#", "标题", "分享链接", "密码", "来源"]
        widths = [4, 32, 44, 8, 10]
    else:
        cols = ["#", "标题", "分享链接", "来源"]
        widths = [4, 36, 48, 10]

    display.table_header(cols, widths)

    for i, r in enumerate(results):
        row = [str(i + 1), r["title"], r["url"]]
        colors = [display.Color.CYAN, display.Color.WHITE, display.Color.GREEN]
        if has_pwd:
            row.append(r.get("password", ""))
            colors.append(display.Color.YELLOW)
        row.append(r.get("source", ""))
        colors.append(display.Color.DIM)
        display.table_row(row, widths, colors)

    print()
    if result.get("errors"):
        for e in result["errors"]:
            display.warning(e)

    display.info("使用 quark-cli share check <url> 检查链接有效性")
    display.info("使用 quark-cli share save <url> <path> 转存文件")
    display.info("或使用 quark-cli search save <keyword> <savepath> 一步搜索+转存")


def _sources(args):
    """列出可用搜索源"""
    cfg = get_config(args)
    cfg.load()
    searcher = PanSearch(cfg)

    display.header("可用搜索源")

    sources = searcher.list_sources()
    cols = ["名称", "显示名", "类型", "地址"]
    widths = [12, 12, 8, 40]
    display.table_header(cols, widths)

    for s in sources:
        display.table_row(
            [s["name"], s["display_name"], s["type"], s["base_url"]],
            widths,
            [display.Color.CYAN, display.Color.WHITE, display.Color.YELLOW, display.Color.DIM],
        )

    print()
    display.info("使用 quark-cli search query <关键词> --source <名称>")
    display.info("使用 quark-cli search set-source <名称> <地址> 自定义搜索源")


def _set_source(args):
    """配置自定义搜索源"""
    cfg = get_config(args)
    cfg.load()

    sources = cfg.data.get("search_sources", {})
    sources[args.name] = args.url
    cfg._data["search_sources"] = sources
    cfg.save()

    display.success(f"搜索源已配置: {args.name} → {args.url}")


def _search_and_save(args):
    """搜索并交互式选择转存"""
    cfg = get_config(args)
    cfg.load()
    searcher = PanSearch(cfg)

    keyword = args.keyword
    savepath = args.savepath
    source = getattr(args, "source", None)

    display.header(f"搜索并转存: {keyword}")

    if source == "all" or not source:
        result = searcher.search_all(keyword)
    else:
        result = searcher.search(keyword, source)

    if not result["success"]:
        display.error(result.get("error"))
        return

    results = result.get("results", [])
    if not results:
        display.warning("未找到相关资源")
        return

    # 显示搜索结果
    for i, r in enumerate(results):
        pwd_str = f"  密码: {r['password']}" if r.get("password") else ""
        print(f"  {display.colorize(str(i + 1), display.Color.CYAN)}. {r['title']}")
        print(f"     {display.colorize(r['url'], display.Color.DIM)}{display.colorize(pwd_str, display.Color.YELLOW)}")

    print()
    try:
        choice = input(f"  选择要转存的序号 (1-{len(results)}, 0 取消): ").strip()
        idx = int(choice) - 1
    except (ValueError, EOFError):
        display.info("操作已取消")
        return

    if idx < 0 or idx >= len(results):
        display.info("操作已取消")
        return

    selected = results[idx]
    display.info(f"选择: {selected['title']}")
    display.info(f"链接: {selected['url']}")

    # 先检查链接有效性
    client = get_client(args)
    pwd_id, passcode, pdir_fid, _ = QuarkAPI.extract_share_url(selected["url"])
    if not pwd_id:
        display.error("无法解析分享链接")
        return

    # 如果搜索结果携带密码，尝试作为 passcode
    if not passcode and selected.get("password"):
        passcode = selected["password"]

    resp = client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        display.error(f"分享链接无效: {resp.get('message')}")
        return

    display.success("链接有效")

    # 转存
    stoken = resp["data"]["stoken"]
    detail = client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        display.error("获取分享文件失败")
        return

    file_list = detail["data"]["list"]
    if not file_list:
        display.warning("分享中没有文件")
        return

    if len(file_list) == 1 and file_list[0].get("dir"):
        display.info(f"自动进入: {file_list[0]['file_name']}")
        detail = client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
        if detail.get("code") == 0:
            file_list = detail["data"]["list"]

    display.info(f"共 {len(file_list)} 个文件")
    for f in file_list[:10]:
        icon = display.file_icon(f)
        size = display.format_size(f.get("size", 0)) if not f.get("dir") else "<DIR>"
        print(f"    {icon} {f['file_name']}  ({size})")
    if len(file_list) > 10:
        display.info(f"... 还有 {len(file_list) - 10} 个文件")

    # 初始化并转存
    info = client.init()
    if not info:
        display.error("账号验证失败")
        return

    import re as _re
    savepath_n = _re.sub(r"/{2,}", "/", f"/{savepath}")
    fids = client.get_fids([savepath_n])
    if fids:
        to_pdir_fid = fids[0]["fid"]
    else:
        mk = client.mkdir(savepath_n)
        if mk.get("code") != 0:
            display.error(f"创建目录失败: {mk.get('message')}")
            return
        to_pdir_fid = mk["data"]["fid"]
        display.info(f"已创建目录: {savepath_n}")

    fid_list = [f["fid"] for f in file_list]
    token_list = [f["share_fid_token"] for f in file_list]

    save_resp = client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)
    if save_resp.get("code") == 0:
        task_id = save_resp["data"]["task_id"]
        task_resp = client.query_task(task_id)
        if task_resp.get("code") == 0:
            saved = len(task_resp["data"]["save_as"]["save_as_top_fids"])
            display.success(f"转存完成！共 {saved} 个文件保存到 {savepath_n}")
        else:
            display.error(f"转存任务查询失败: {task_resp.get('message')}")
    else:
        display.error(f"转存失败: {save_resp.get('message')}")
