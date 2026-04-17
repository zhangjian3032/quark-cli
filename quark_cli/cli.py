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
        description="夸克网盘命令行工具 - 签到/搜索/转存/文件管理一站式 CLI",
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

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    # 初始化 debug 模式
    if getattr(args, "debug", False):
        from quark_cli import debug as dbg
        dbg.set_debug(True)
        dbg.log("CLI", f"Debug 模式已启用, args={vars(args)}")

    if not args.command:
        parser.print_help()
        return

    # 延迟导入命令处理器
    from quark_cli.commands import config_cmd, account_cmd, share_cmd, drive_cmd, task_cmd, search_cmd

    handlers = {
        "config": config_cmd.handle,
        "account": account_cmd.handle,
        "share": share_cmd.handle,
        "search": search_cmd.handle,
        "drive": drive_cmd.handle,
        "task": task_cmd.handle,
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
