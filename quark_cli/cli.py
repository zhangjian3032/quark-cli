#!/usr/bin/env python3
"""
Quark Drive CLI - 夸克网盘命令行工具
主入口模块，基于 argparse 实现子命令分发
"""

import argparse
import sys

from quark_cli import __version__


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quark-cli",
        description="夸克网盘命令行工具 - 签到/搜索/转存/文件管理/影视中心 一站式 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  quark-cli config set-cookie "your_cookie_here"   设置 Cookie
  quark-cli account info                           查看账号信息
  quark-cli account sign                           每日签到
  quark-cli share check <url>                      检查分享链接是否有效
  quark-cli share list <url>                       列出分享链接中的文件
  quark-cli share save <url> /保存路径             转存文件
  quark-cli search query "关键词"                  搜索网盘资源
  quark-cli search save "关键词" /保存路径         搜索并转存
  quark-cli drive ls /路径                         列出网盘目录
  quark-cli drive mkdir /新目录                    创建目录
  quark-cli drive search <关键词>                  搜索网盘内文件
  quark-cli task list                              查看任务列表
  quark-cli task add                               添加转存任务
  quark-cli task run                               执行全部任务
  quark-cli media login --host <ip> -u <user>      登录影视中心
  quark-cli media status                           检查影视中心连接
  quark-cli media lib list                         列出媒体库
  quark-cli media search "关键词"                  搜索影片
  quark-cli media info <GUID>                      查看影片详情
  quark-cli media meta "流浪地球2"                 查询 TMDB 元数据
  quark-cli media discover --list top_rated        高分影视推荐
  quark-cli media auto-save "流浪地球2"            自动搜索+转存

飞书机器人:
  quark-cli bot                                    启动飞书影视转存机器人
  quark-cli bot --app-id <id> --app-secret <key>   指定凭证启动

Web 面板:
  quark-cli serve                                  启动 Web 管理面板
  quark-cli serve --port 8080                      自定义端口

调试模式:
  quark-cli --debug search query "关键词"          启用 debug 输出
        """,
    )
    parser.add_argument("-v", "--version", action="version", version=f"quark-cli {__version__}")
    parser.add_argument("-c", "--config", help="指定配置文件路径", default=None)
    parser.add_argument(
        "--debug", action="store_true", default=False,
        help="启用 debug 模式，打印所有 API 请求/响应详情到 stderr"
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="所有命令以 JSON 格式输出结果"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ========== config ==========
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(dest="config_action")

    sc = config_sub.add_parser("set-cookie", help="设置夸克网盘 Cookie")
    sc.add_argument("cookie", help="Cookie 字符串")
    sc.add_argument("-i", "--index", type=int, default=0, help="账号索引（默认 0）")

    config_sub.add_parser("show", help="显示当前配置")
    config_sub.add_parser("path", help="显示配置文件路径")
    config_sub.add_parser("reset", help="重置配置为默认值")

    rc = config_sub.add_parser("remove-cookie", help="移除指定 Cookie")
    rc.add_argument("-i", "--index", type=int, default=0, help="账号索引")

    ss = config_sub.add_parser("set-search-source", help="配置自定义搜索源")
    ss.add_argument("source_name", help="搜索源名称，如 pansou")
    ss.add_argument("source_url", help="搜索源地址")

    # ========== account ==========
    account_parser = subparsers.add_parser("account", help="账号管理")
    account_sub = account_parser.add_subparsers(dest="account_action")

    account_sub.add_parser("info", help="查看账号信息")
    account_sub.add_parser("sign", help="每日签到")
    account_sub.add_parser("verify", help="验证 Cookie 是否有效")
    account_sub.add_parser("space", help="查看网盘空间信息")

    # ========== share ==========
    share_parser = subparsers.add_parser("share", help="分享链接操作")
    share_sub = share_parser.add_subparsers(dest="share_action")

    ck = share_sub.add_parser("check", help="检查分享链接是否有效")
    ck.add_argument("url", help="分享链接 URL")

    sl = share_sub.add_parser("list", help="列出分享链接中的文件")
    sl.add_argument("url", help="分享链接 URL")
    sl.add_argument("--tree", action="store_true", help="树形显示")

    sv = share_sub.add_parser("save", help="转存分享链接中的文件")
    sv.add_argument("url", help="分享链接 URL")
    sv.add_argument("savepath", help="保存路径，如 /我的资源/电影")
    sv.add_argument("--pattern", default=".*", help="正则过滤文件名（默认 .*）")
    sv.add_argument("--replace", default="", help="正则替换文件名")

    # ========== search (资源搜索) ==========
    search_parser = subparsers.add_parser("search", help="网盘资源搜索（pansou 等）")
    search_sub = search_parser.add_subparsers(dest="search_action")

    sq = search_sub.add_parser("query", help="搜索网盘资源")
    sq.add_argument("keyword", help="搜索关键词")
    sq.add_argument("--source", default=None, help="搜索源: pansou / funletu / all（默认 all）")

    search_sub.add_parser("sources", help="列出可用搜索源")

    sss = search_sub.add_parser("set-source", help="配置自定义搜索源")
    sss.add_argument("name", help="搜索源名称")
    sss.add_argument("url", help="搜索源地址")

    ssa = search_sub.add_parser("save", help="搜索并交互式选择转存")
    ssa.add_argument("keyword", help="搜索关键词")
    ssa.add_argument("savepath", help="保存路径")
    ssa.add_argument("--source", default=None, help="搜索源")

    # ========== drive ==========
    drive_parser = subparsers.add_parser("drive", help="网盘文件操作")
    drive_sub = drive_parser.add_subparsers(dest="drive_action")

    ls_p = drive_sub.add_parser("ls", help="列出目录内容")
    ls_p.add_argument("path", nargs="?", default="/", help="目录路径（默认 /）")

    mk = drive_sub.add_parser("mkdir", help="创建目录")
    mk.add_argument("path", help="目录路径")

    rn = drive_sub.add_parser("rename", help="重命名文件")
    rn.add_argument("fid", help="文件 FID")
    rn.add_argument("name", help="新文件名")

    dl = drive_sub.add_parser("download", help="获取文件下载链接")
    dl.add_argument("fid", help="文件 FID（多个用逗号分隔）")

    rm = drive_sub.add_parser("delete", help="删除文件")
    rm.add_argument("fid", nargs="+", help="文件 FID（可多个）")
    rm.add_argument("--permanent", action="store_true", help="彻底删除（清空回收站）")

    se = drive_sub.add_parser("search", help="搜索网盘内文件")
    se.add_argument("keyword", help="搜索关键词")
    se.add_argument("--path", default="/", help="搜索范围路径")

    # ========== task ==========
    task_parser = subparsers.add_parser("task", help="自动转存任务管理")
    task_sub = task_parser.add_subparsers(dest="task_action")

    task_sub.add_parser("list", help="列出所有任务")

    ta = task_sub.add_parser("add", help="添加任务")
    ta.add_argument("--name", required=True, help="任务名称")
    ta.add_argument("--url", required=True, help="分享链接")
    ta.add_argument("--savepath", required=True, help="保存路径")
    ta.add_argument("--pattern", default=".*", help="正则过滤")
    ta.add_argument("--replace", default="", help="正则替换")
    ta.add_argument("--enddate", default="", help="结束日期 YYYY-MM-DD")
    ta.add_argument("--runweek", default="", help="运行星期，逗号分隔如 1,3,5")

    tr = task_sub.add_parser("remove", help="移除任务")
    tr.add_argument("index", type=int, help="任务序号（从 1 开始）")

    task_sub.add_parser("run", help="执行全部任务（一次性）")

    tri = task_sub.add_parser("run-one", help="执行指定任务")
    tri.add_argument("index", type=int, help="任务序号（从 1 开始）")

    # ========== media (影视媒体中心) ==========
    media_parser = subparsers.add_parser("media", help="影视媒体中心 (fnOS / Emby / Jellyfin / TMDB)")
    media_sub = media_parser.add_subparsers(dest="media_action")

    # media login
    ml = media_sub.add_parser("login", help="登录影视中心")
    ml.add_argument("--host", help="NAS/服务器 地址 (IP/域名)")
    ml.add_argument("--port", type=int, help="端口")
    ml.add_argument("-u", "--username", help="用户名")
    ml.add_argument("-p", "--password", help="密码")

    # media status
    media_sub.add_parser("status", help="检查连接状态")

    # media config
    mc = media_sub.add_parser("config", help="查看/修改媒体配置")
    mc.add_argument("--show", action="store_true", help="显示当前配置")
    mc.add_argument("--provider", help="设置 Provider (fnos/emby/jellyfin)")
    mc.add_argument("--host", help="设置服务器地址")
    mc.add_argument("--port", type=int, help="设置端口")
    mc.add_argument("--token", help="设置 Token")
    mc.add_argument("--tmdb-key", help="设置 TMDB API Key")
    mc.add_argument("--tmdb-lang", help="设置 TMDB 语言 (默认 zh-CN)")

    # media lib
    lib_parser = media_sub.add_parser("lib", help="媒体库管理")
    lib_sub = lib_parser.add_subparsers(dest="lib_action")

    lib_sub.add_parser("list", help="列出所有媒体库")

    ls_lib = lib_sub.add_parser("show", help="显示媒体库中的影片")
    ls_lib.add_argument("lib_name", help="媒体库名称或 GUID")
    ls_lib.add_argument("-p", "--page", type=int, default=1, help="页码")
    ls_lib.add_argument("-s", "--size", type=int, default=20, help="每页数量")

    # media search
    ms = media_sub.add_parser("search", help="搜索影片")
    ms.add_argument("keyword", help="搜索关键词")
    ms.add_argument("-p", "--page", type=int, default=1, help="页码")
    ms.add_argument("-s", "--size", type=int, default=20, help="每页数量")

    # media info
    mi = media_sub.add_parser("info", help="查看影片详情")
    mi.add_argument("guid", help="影片 GUID 或名称")
    mi.add_argument("--seasons", "-S", action="store_true", help="显示季列表")
    mi.add_argument("--cast", "-C", action="store_true", help="显示演职人员")

    # media poster
    mp = media_sub.add_parser("poster", help="下载影片海报")
    mp.add_argument("guid", help="影片 GUID 或名称")
    mp.add_argument("-o", "--output", default=".", help="输出目录")

    # media export
    me = media_sub.add_parser("export", help="导出影片列表")
    me.add_argument("-o", "--output", default="export.json", help="输出文件")
    me.add_argument("-f", "--format", default="json", choices=["json", "csv"], help="格式")
    me.add_argument("-l", "--lib", help="媒体库名称 (不指定则导出全部)")

    # media playing
    media_sub.add_parser("playing", help="查看继续观看列表")

    # media meta  (TMDB 元数据查询)
    mm = media_sub.add_parser("meta", help="查询影视元数据 (TMDB)")
    mm.add_argument("query", nargs="?", help="搜索关键词 (如 '流浪地球2')")
    mm.add_argument("--tmdb", help="直接指定 TMDB ID")
    mm.add_argument("--imdb", help="直接指定 IMDb ID")
    mm.add_argument("-t", "--type", default="movie", choices=["movie", "tv"], help="类型 (默认 movie)")
    mm.add_argument("-y", "--year", type=int, help="年份过滤")
    mm.add_argument("--base-path", default="/媒体", help="保存路径基准目录 (默认 /媒体)")

    # media discover  (高分影视推荐)
    md = media_sub.add_parser("discover", help="高分影视推荐 (TMDB)")
    md.add_argument("--list", dest="list_type", default="top_rated",
                     choices=["popular", "top_rated", "trending", "discover"],
                     help="推荐列表类型 (默认 top_rated)")
    md.add_argument("-t", "--type", default="movie", choices=["movie", "tv"], help="类型 (默认 movie)")
    md.add_argument("-p", "--page", type=int, default=1, help="页码")
    md.add_argument("--min-rating", type=float, help="最低评分 (如 8.0)")
    md.add_argument("--genre", help="类型过滤 (逗号分隔, 如 '动作,科幻' 或 TMDB genre_id)")
    md.add_argument("-y", "--year", type=int, help="年份")
    md.add_argument("--country", help="国家/地区代码 (如 CN, US, JP)")
    md.add_argument("--sort-by", default="vote_average.desc",
                     help="排序方式 (默认 vote_average.desc)")
    md.add_argument("--min-votes", type=int, default=50, help="最低票数 (默认 50)")
    md.add_argument("--window", default="week", choices=["day", "week"],
                     help="趋势时间窗口 (仅 trending 有效, 默认 week)")

    # media auto-save  (自动搜索转存)
    mas = media_sub.add_parser("auto-save", help="自动搜索+转存 (一键全流程)")
    mas.add_argument("name", help="影视名称 (如 '流浪地球2')")
    mas.add_argument("--save-path", help="保存路径 (不指定则通过 TMDB 自动生成)")
    mas.add_argument("--no-tmdb", action="store_true", default=False,
                      help="跳过 TMDB 元数据查询，直接用名称搜索")
    mas.add_argument("-t", "--type", default="movie", choices=["movie", "tv"],
                      help="类型 (默认 movie, 仅 TMDB 模式有效)")
    mas.add_argument("-y", "--year", type=int, help="年份 (可选, 缩小搜索范围)")
    mas.add_argument("--pattern", default=".*", help="正则过滤文件名 (默认 .*)")
    mas.add_argument("--replace", default="", help="正则替换文件名")
    mas.add_argument("--max-attempts", type=int, default=10,
                      help="最大尝试链接数 (默认 10)")
    mas.add_argument("--base-path", default="/媒体",
                      help="保存路径基准目录 (默认 /媒体)")
    mas.add_argument("--keyword", action="append",
                      help="手动指定搜索关键词 (可多次使用, 覆盖自动生成)")
    mas.add_argument("--dry-run", action="store_true", default=False,
                      help="仅搜索和排序，不实际转存")


    # ========== bot (飞书机器人) ==========
    bot_parser = subparsers.add_parser("bot", help="启动飞书/Lark 机器人 (影视自动转存)")
    bot_parser.add_argument("--app-id", help="飞书应用 APP_ID")
    bot_parser.add_argument("--app-secret", help="飞书应用 APP_SECRET")
    bot_parser.add_argument("--base-path", default="/媒体", help="转存基准目录 (默认 /媒体)")

    # ========== serve (Web 面板) ==========
    serve_parser = subparsers.add_parser("serve", help="启动 Web 管理面板 (FastAPI + React)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=9090, help="监听端口 (默认 9090)")
    serve_parser.add_argument("--reload", action="store_true", help="开发模式: 热重载")
    serve_parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")

    return parser


def _try_start_bot(config_path):
    """尝试在后台线程启动飞书机器人，无配置则跳过"""
    import os
    from quark_cli.config import ConfigManager
    from quark_cli.display import info, kvline

    cfg = ConfigManager(config_path)
    cfg.load()
    bot_cfg = cfg.data.get("bot", {}).get("feishu", {})

    app_id = bot_cfg.get("app_id") or os.environ.get("FEISHU_APP_ID", "")
    app_secret = bot_cfg.get("app_secret") or os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        info("飞书机器人: 未配置 APP_ID/APP_SECRET，跳过启动")
        return

    try:
        from quark_cli.bot.lark_bot import QuarkLarkBot
    except ImportError:
        info("飞书机器人: lark-oapi 未安装，跳过启动 (pip install lark-oapi)")
        return

    base_path = bot_cfg.get("base_path", "/媒体")
    import threading

    def _run_bot():
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        try:
            bot = QuarkLarkBot(
                app_id=app_id,
                app_secret=app_secret,
                config_path=config_path,
                base_path=base_path,
            )
            bot.start()
        except Exception as e:
            logging.getLogger("quark_cli.bot").error("飞书机器人启动失败: %s", e)

    t = threading.Thread(target=_run_bot, daemon=True)
    t.start()

    from quark_cli.display import success
    success("飞书机器人: 已在后台启动")
    kvline("  APP_ID", "{}***".format(app_id[:6]) if len(app_id) > 6 else "***")
    kvline("  基准路径", base_path)


def _serve(args):
    """启动 FastAPI Web 服务"""
    try:
        import uvicorn
    except ImportError:
        from quark_cli.display import error, info
        error("缺少 Web 依赖，请安装:")
        info("  pip install 'quark-cli[web]'")
        info("  # 或: pip install fastapi uvicorn")
        import sys
        sys.exit(1)

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 9090)
    reload = getattr(args, "reload", False)
    no_open = getattr(args, "no_open", False)

    # 设置配置路径
    config_path = getattr(args, "config", None)
    from quark_cli.web.deps import set_config_path
    set_config_path(config_path)

    from quark_cli.display import success, info, kvline
    success("启动 Quark CLI Web 面板")
    kvline("地址", "http://{}:{}".format("127.0.0.1" if host == "0.0.0.0" else host, port))
    kvline("API 文档", "http://{}:{}/api/docs".format("127.0.0.1" if host == "0.0.0.0" else host, port))
    if reload:
        info("开发模式: 热重载已启用")

    # 尝试在后台启动飞书机器人
    if not reload:
        _try_start_bot(config_path)

    # 自动打开浏览器
    if not no_open and not reload:
        import threading, webbrowser
        url = "http://{}:{}".format("127.0.0.1" if host == "0.0.0.0" else host, port)
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    uvicorn.run(
        "quark_cli.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def _bot(args):
    """启动飞书机器人"""
    try:
        from quark_cli.bot.lark_bot import start_bot
    except ImportError:
        from quark_cli.display import error, info
        error("缺少飞书 SDK 依赖，请安装:")
        info("  pip install lark-oapi>=1.4.8")
        import sys
        sys.exit(1)

    from quark_cli.display import success, info, kvline
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    app_id = getattr(args, "app_id", None)
    app_secret = getattr(args, "app_secret", None)
    base_path = getattr(args, "base_path", "/媒体")
    config_path = getattr(args, "config", None)

    success("启动飞书影视转存机器人")
    kvline("模式", "WebSocket 长连接")
    if base_path:
        kvline("基准路径", base_path)
    info("按 Ctrl+C 停止")
    print()

    try:
        start_bot(
            config_path=config_path,
            app_id=app_id,
            app_secret=app_secret,
            base_path=base_path,
        )
    except ValueError as e:
        from quark_cli.display import error
        error(str(e))
        import sys
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  机器人已停止")



def main():
    parser = create_parser()
    args = parser.parse_args()

    # 初始化 debug 模式
    if getattr(args, "debug", False):
        from quark_cli import debug as dbg
        dbg.set_debug(True)
        dbg.log("CLI", f"Debug 模式已启用, args={vars(args)}")
    # 初始化 JSON 模式
    if getattr(args, "json", False):
        from quark_cli.display import set_json_mode
        set_json_mode(True)

    if not args.command:
        parser.print_help()
        return

    # 延迟导入命令处理器
    from quark_cli.commands import config_cmd, account_cmd, share_cmd, drive_cmd, task_cmd, search_cmd
    from quark_cli.commands import media_cmd

    # serve 命令特殊处理 (不通过 handlers dict)
    if args.command == "serve":
        _serve(args)
        return

    # bot 命令特殊处理
    if args.command == "bot":
        _bot(args)
        return



    handlers = {
        "config": config_cmd.handle,
        "account": account_cmd.handle,
        "share": share_cmd.handle,
        "search": search_cmd.handle,
        "drive": drive_cmd.handle,
        "task": task_cmd.handle,
        "media": media_cmd.handle,
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print("\n\n  操作已取消")
            sys.exit(130)
        except Exception as e:
            from quark_cli.display import error
            error(f"执行出错: {e}")
            if getattr(args, "debug", False):
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
