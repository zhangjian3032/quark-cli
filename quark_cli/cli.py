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

文件同步:
  quark-cli sync run                               执行 WebDAV → NAS 同步
  quark-cli sync run --source /mnt/alist --dest /mnt/nas  手动指定同步路径
  quark-cli sync config --show                     查看同步配置
  quark-cli sync status                            查看同步状态

飞书机器人:
  quark-cli bot                                    启动飞书影视转存机器人
  quark-cli bot --app-id <id> --app-secret <key>   指定凭证启动

光鸭云盘:
  quark-cli guangya config set --refresh-token <TOKEN>              设置凭证
  quark-cli guangya config show                 查看配置
  quark-cli guangya account                     查看账号信息
  quark-cli guangya ls                          列出根目录
  quark-cli guangya ls --parent-id <ID>         列出子目录
  quark-cli guangya mkdir <名称>                创建目录
  quark-cli guangya download <file_id>          获取下载链接
  quark-cli guangya cloud magnet <磁力链接>     解析磁力
  quark-cli guangya cloud create <URL>          创建云添加任务
  quark-cli guangya cloud list                  查看云添加任务

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

    # media meta  (影视元数据查询)
    mm = media_sub.add_parser("meta", help="查询影视元数据 (TMDB/豆瓣)")
    mm.add_argument("query", nargs="?", help="搜索关键词 (如 '流浪地球2')")
    mm.add_argument("--tmdb", help="直接指定 TMDB ID")
    mm.add_argument("--imdb", help="直接指定 IMDb ID")
    mm.add_argument("--douban", help="直接指定豆瓣 ID")
    mm.add_argument("-s", "--source", default="auto",
                     choices=["auto", "tmdb", "douban"],
                     help="数据源 (默认 auto: 优先 TMDB, 无 key 回退豆瓣)")
    mm.add_argument("-t", "--type", default="movie", choices=["movie", "tv"], help="类型 (默认 movie)")
    mm.add_argument("-y", "--year", type=int, help="年份过滤")
    mm.add_argument("--base-path", default="/媒体", help="保存路径基准目录 (默认 /媒体)")

    # media discover  (高分影视推荐)
    md = media_sub.add_parser("discover", help="高分影视推荐 (TMDB/豆瓣)")
    md.add_argument("--list", dest="list_type", default="top_rated",
                     choices=["popular", "top_rated", "trending", "discover"],
                     help="推荐列表类型 (默认 top_rated)")
    md.add_argument("-s", "--source", default="auto",
                     choices=["auto", "tmdb", "douban"],
                     help="数据源 (默认 auto: 优先 TMDB, 无 key 回退豆瓣)")
    md.add_argument("-t", "--type", default="movie", choices=["movie", "tv"], help="类型 (默认 movie)")
    md.add_argument("-p", "--page", type=int, default=1, help="页码")
    md.add_argument("--min-rating", type=float, help="最低评分 (如 8.0)")
    md.add_argument("--genre", help="类型过滤 (逗号分隔, 如 '动作,科幻' 或 TMDB genre_id)")
    md.add_argument("--tag", help="豆瓣标签 (如 '热门','科幻','美剧', 仅 --source douban)")
    md.add_argument("-y", "--year", type=int, help="年份")
    md.add_argument("--country", help="国家/地区代码 (如 CN, US, JP)")
    md.add_argument("--sort-by", default="vote_average.desc",
                     help="排序方式 (TMDB: vote_average.desc | 豆瓣: recommend/time/rank)")
    md.add_argument("--min-votes", type=int, default=50, help="最低票数 (默认 50, 仅 TMDB)")
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

    # media person  (演员/人物发现)
    mp_person = media_sub.add_parser("person", help="演员/人物发现 (搜索演员 + 查看参演作品)")
    mp_person.add_argument("name", nargs="?", help="演员名称 (如 '刘德华')")
    mp_person.add_argument("--id", dest="person_id", help="直接指定演员 ID (TMDB person_id 或 豆瓣 celebrity_id)")
    mp_person.add_argument("-s", "--source", default="auto",
                            choices=["auto", "tmdb", "douban"],
                            help="数据源 (默认 auto)")
    mp_person.add_argument("-t", "--type", default=None, choices=["movie", "tv"],
                            help="过滤作品类型 (不指定则显示全部)")
    mp_person.add_argument("-p", "--page", type=int, default=1, help="搜索页码")

    # media batch-save  (批量搜索转存)
    mbs = media_sub.add_parser("batch-save", help="批量搜索+转存 (多部影视一次搞定)")
    mbs.add_argument("names", nargs="+", help="影视名称列表 (如 '流浪地球2' '三体' '满江红')")
    mbs.add_argument("-t", "--type", default="movie", choices=["movie", "tv"],
                      help="类型 (默认 movie)")
    mbs.add_argument("--base-path", default="/媒体",
                      help="保存路径基准目录 (默认 /媒体)")
    mbs.add_argument("--max-attempts", type=int, default=10,
                      help="每部影视最大尝试链接数 (默认 10)")
    mbs.add_argument("--dry-run", action="store_true", default=False,
                      help="仅搜索排序，不实际转存")


    # ========== sync (WebDAV → NAS 同步) ==========
    sync_parser = subparsers.add_parser("sync", help="WebDAV 挂载目录 → NAS 本地文件同步")
    sync_sub = sync_parser.add_subparsers(dest="sync_action")

    sr = sync_sub.add_parser("run", help="执行同步 (默认)")
    sr.add_argument("--source", help="源目录 (WebDAV 挂载路径)")
    sr.add_argument("--dest", help="目标目录 (NAS 本地路径)")
    sr.add_argument("--delete", action="store_true", default=False, help="同步后删除源文件")
    sr.add_argument("--task", help="指定调度任务名称 (使用该任务的同步配置)")
    sr.add_argument("--no-progress", action="store_true", default=False, help="不显示进度条")

    sync_sub.add_parser("status", help="查看同步状态")

    sc_sync = sync_sub.add_parser("config", help="查看/设置同步配置")
    sc_sync.add_argument("--show", action="store_true", help="显示当前配置")
    sc_sync.add_argument("--webdav-mount", help="设置 WebDAV 挂载路径")
    sc_sync.add_argument("--local-dest", help="设置本地目标路径")
    sc_sync.add_argument("--delete-after-sync", choices=["true", "false"], help="设置同步后是否删除源")

    # ========== bot (飞书机器人) ==========
    bot_parser = subparsers.add_parser("bot", help="启动飞书/Lark 机器人 (影视自动转存)")
    bot_parser.add_argument("--app-id", help="飞书应用 APP_ID")
    bot_parser.add_argument("--app-secret", help="飞书应用 APP_SECRET")
    bot_parser.add_argument("--base-path", default="/媒体", help="转存基准目录 (默认 /媒体)")



    # ========== torrent (Torrent 客户端) ==========
    torrent_parser = subparsers.add_parser("torrent", help="Torrent 客户端管理 (qBittorrent)")
    torrent_sub = torrent_parser.add_subparsers(dest="torrent_action")

    # torrent config
    tc_config = torrent_sub.add_parser("config", help="配置 qBittorrent 连接")
    tc_config.add_argument("--show", action="store_true", help="显示当前配置")
    tc_config.add_argument("--host", default=None, help="qBittorrent 地址")
    tc_config.add_argument("--port", type=int, default=None, help="端口 (默认 8080)")
    tc_config.add_argument("--username", default=None, help="用户名 (默认 admin)")
    tc_config.add_argument("--password", default=None, help="密码")
    tc_config.add_argument("--use-https", action="store_true", default=False, help="使用 HTTPS")
    tc_config.add_argument("--save-path", default=None, help="默认下载路径")
    tc_config.add_argument("--category", default=None, help="默认分类")
    tc_config.add_argument("--name", default=None, help="客户端名称")
    tc_config.add_argument("--id", default=None, help="客户端 ID")

    # torrent test
    tc_test = torrent_sub.add_parser("test", help="测试 qBittorrent 连接")
    tc_test.add_argument("--client-id", default=None, help="客户端 ID (不指定则用默认)")

    # torrent list
    tc_list = torrent_sub.add_parser("list", help="查看下载列表")
    tc_list.add_argument("--client-id", default=None, help="客户端 ID")
    tc_list.add_argument("--filter", default="all",
                          choices=["all", "downloading", "seeding", "completed", "paused", "active"],
                          help="状态过滤 (默认 all)")
    tc_list.add_argument("--category", default="", help="分类过滤")
    tc_list.add_argument("--limit", type=int, default=20, help="显示条数 (默认 20)")

    # torrent add
    tc_add = torrent_sub.add_parser("add", help="手动添加种子/磁力链接")
    tc_add.add_argument("url", help="磁力链接或 .torrent URL")
    tc_add.add_argument("--client-id", default=None, help="客户端 ID")
    tc_add.add_argument("--save-path", default="", help="下载保存路径")
    tc_add.add_argument("--category", default="", help="分类")
    tc_add.add_argument("--paused", action="store_true", default=False, help="添加后暂停")

    # ========== rss (RSS 订阅) ==========
    rss_parser = subparsers.add_parser("rss", help="RSS 订阅管理 (Feed + 规则 + 自动转存)")
    rss_sub = rss_parser.add_subparsers(dest="rss_action")

    # rss add
    rss_add = rss_sub.add_parser("add", help="添加 RSS Feed")
    rss_add.add_argument("feed_url", help="Feed URL")
    rss_add.add_argument("--name", default="", help="Feed 名称")
    rss_add.add_argument("--interval", type=int, default=30, help="检查间隔 (分钟, 默认 30)")
    rss_add.add_argument("--passkey", default="", help="PT 站 passkey")
    rss_add.add_argument("--cookie", default="", help="Cookie 认证")

    # rss list
    rss_sub.add_parser("list", help="列出所有 Feed")

    # rss show
    rss_show = rss_sub.add_parser("show", help="查看 Feed 详情")
    rss_show.add_argument("feed_id", help="Feed ID 或名称")

    # rss remove
    rss_rm = rss_sub.add_parser("remove", help="删除 Feed")
    rss_rm.add_argument("feed_id", help="Feed ID 或名称")

    # rss enable / disable
    rss_en = rss_sub.add_parser("enable", help="启用 Feed")
    rss_en.add_argument("feed_id", help="Feed ID 或名称")
    rss_dis = rss_sub.add_parser("disable", help="禁用 Feed")
    rss_dis.add_argument("feed_id", help="Feed ID 或名称")

    # rss test
    rss_test = rss_sub.add_parser("test", help="测试拉取 Feed (预览条目)")
    rss_test.add_argument("feed_url", help="Feed URL")
    rss_test.add_argument("--passkey", default="", help="PT 站 passkey")
    rss_test.add_argument("--cookie", default="", help="Cookie 认证")

    # rss check
    rss_check = rss_sub.add_parser("check", help="立即触发检查")
    rss_check.add_argument("feed_id", nargs="?", default=None, help="Feed ID (不指定则检查全部)")
    rss_check.add_argument("--dry-run", action="store_true", default=False, help="仅匹配, 不执行动作")

    # rss rule
    rss_rule = rss_sub.add_parser("rule", help="规则管理")
    rule_sub = rss_rule.add_subparsers(dest="rule_action")

    rule_add = rule_sub.add_parser("add", help="添加匹配规则")
    rule_add.add_argument("feed_id", help="Feed ID 或名称")
    rule_add.add_argument("--name", default="", help="规则名称")
    rule_add.add_argument("--match", default="", help="匹配正则 (标题)")
    rule_add.add_argument("--exclude", default="", help="排除正则")
    rule_add.add_argument("--quality", default="", help="画质正则 (如 4K|1080p)")
    rule_add.add_argument("--save-path", default="", help="转存路径")
    rule_add.add_argument("--action", default="auto_save", choices=["auto_save", "torrent", "notify", "log"],
                           help="匹配后动作 (默认 auto_save; torrent = 推送到 qBittorrent)")
    rule_add.add_argument("--link-type", default="quark",
                           choices=["quark", "alipan", "magnet", "enclosure", "torrent_enclosure", "web", "any"],
                           help="优先链接类型 (默认 quark; torrent 动作建议 enclosure/magnet)")
    rule_add.add_argument("--min-size", type=float, default=None, help="最小大小 (GB)")
    rule_add.add_argument("--max-size", type=float, default=None, help="最大大小 (GB)")
    rule_add.add_argument("--torrent-save-path", default=None, help="[torrent] qB 下载路径")
    rule_add.add_argument("--torrent-category", default=None, help="[torrent] qB 分类")
    rule_add.add_argument("--torrent-tags", default=None, help="[torrent] qB 标签 (逗号分隔)")
    rule_add.add_argument("--torrent-client", default=None, help="[torrent] 客户端 ID")
    rule_add.add_argument("--torrent-paused", action="store_true", default=False, help="[torrent] 添加后暂停")

    rule_list = rule_sub.add_parser("list", help="查看规则列表")
    rule_list.add_argument("feed_id", help="Feed ID 或名称")

    rule_rm = rule_sub.add_parser("remove", help="删除规则")
    rule_rm.add_argument("feed_id", help="Feed ID 或名称")
    rule_rm.add_argument("index", type=int, help="规则索引")

    # rss history
    rss_hist = rss_sub.add_parser("history", help="查看 RSS 历史记录")
    rss_hist.add_argument("--limit", type=int, default=20, help="显示条数 (默认 20)")


    # ========== guangya (光鸭云盘) ==========
    guangya_parser = subparsers.add_parser("guangya", help="光鸭云盘 (guangyapan.com)")
    guangya_sub = guangya_parser.add_subparsers(dest="guangya_action")

    # guangya config
    gy_config = guangya_sub.add_parser("config", help="凭证配置")
    gy_config_sub = gy_config.add_subparsers(dest="guangya_config_action")

    gy_cfg_set = gy_config_sub.add_parser("set", help="设置凭证")
    gy_cfg_set.add_argument("--refresh-token", default=None, help="OIDC Refresh Token")

    gy_config_sub.add_parser("show", help="显示当前配置")

    # guangya account
    guangya_sub.add_parser("account", help="查看账号信息")

    # guangya ls
    gy_ls = guangya_sub.add_parser("ls", help="列出目录内容")
    gy_ls.add_argument("--parent-id", default="", help="父目录 fileId (空=根目录)")

    # guangya mkdir
    gy_mk = guangya_sub.add_parser("mkdir", help="创建目录")
    gy_mk.add_argument("dir_name", help="目录名称")
    gy_mk.add_argument("--parent-id", default="", help="父目录 fileId")

    # guangya rename
    gy_rn = guangya_sub.add_parser("rename", help="重命名")
    gy_rn.add_argument("file_id", help="文件 fileId")
    gy_rn.add_argument("new_name", help="新名称")

    # guangya delete
    gy_rm = guangya_sub.add_parser("delete", help="删除文件/目录")
    gy_rm.add_argument("file_id", nargs="+", help="文件 fileId (可多个)")

    # guangya download
    gy_dl = guangya_sub.add_parser("download", help="下载文件 (获取链接 或 下载到服务器)")
    gy_dl.add_argument("file_id", help="文件 fileId")
    gy_dl.add_argument("--save-dir", dest="save_dir", default=None, help="下载到服务器本地目录 (不指定则仅返回下载链接)")

    # guangya sync (递归下载)
    gy_sync = guangya_sub.add_parser("sync", help="递归下载目录/文件到本地 (sync)")
    gy_sync.add_argument("file_id", help="目录或文件 fileId")
    gy_sync.add_argument("--save-dir", dest="save_dir", default=None, help="本地保存目录 (默认读配置 download_dir)")
    gy_sync.add_argument("--no-skip", dest="no_skip", action="store_true", help="不跳过已存在的文件 (默认跳过大小一致的)")

        # guangya cloud (云添加)
    gy_cloud = guangya_sub.add_parser("cloud", help="云添加 (磁力/种子)")
    gy_cloud_sub = gy_cloud.add_subparsers(dest="guangya_cloud_action")

    gy_magnet = gy_cloud_sub.add_parser("magnet", help="解析磁力链接")
    gy_magnet.add_argument("url", help="磁力链接 URL")

    gy_torrent = gy_cloud_sub.add_parser("torrent", help="解析种子文件")
    gy_torrent.add_argument("torrent_path", help="种子文件路径")

    gy_create = gy_cloud_sub.add_parser("create", help="创建云添加任务")
    gy_create.add_argument("url", help="磁力/种子 URL")
    gy_create.add_argument("--parent-id", default="", help="保存目录 fileId")
    gy_create.add_argument("--file-indexes", default=None, help="选择文件索引 (逗号分隔)")
    gy_create.add_argument("--new-name", default=None, help="重命名")

    gy_cloud_sub.add_parser("list", help="查看云添加任务列表")

    gy_cloud_del = gy_cloud_sub.add_parser("delete", help="删除云添加任务")
    gy_cloud_del.add_argument("task_id", nargs="+", help="任务 ID (可多个)")

    # ========== serve (Web 面板) ==========
    serve_parser = subparsers.add_parser("serve", help="启动 Web 管理面板 (FastAPI + React)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0; Linux 可用 :: 启用 IPv6 双栈)")
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


def _try_start_scheduler(config_path):
    """尝试启动定时任务调度器，无任务则跳过"""
    from quark_cli.display import info
    try:
        from quark_cli.scheduler import try_start_scheduler
        scheduler = try_start_scheduler(config_path)
        if scheduler:
            info("定时任务调度器: 已启动")
    except Exception as e:
        info("定时任务调度器: 启动失败 - {}".format(e))




def _try_start_keepalive(config_path):
    """尝试启动 Cookie 保活"""
    from quark_cli.display import info
    try:
        from quark_cli.keepalive import try_start_keepalive
        ka = try_start_keepalive(config_path)
        if ka:
            info("Cookie 保活: 已启动")
    except Exception as e:
        info("Cookie 保活: 启动失败 - {}".format(e))

def _try_start_sync_scheduler(config_path):
    """尝试启动同步定时调度器"""
    from quark_cli.display import info
    try:
        from quark_cli.media.sync import try_start_sync_scheduler
        sched = try_start_sync_scheduler(config_path)
        if sched:
            info("同步定时调度器: 已启动 (每 {}m)".format(sched._interval // 60))
    except Exception as e:
        info("同步定时调度器: 启动失败 - {}".format(e))




def _try_start_subscribe_scheduler(config_path):
    """尝试启动订阅追剧调度器"""
    from quark_cli.display import info
    try:
        from quark_cli.subscribe import try_start_subscribe_scheduler
        sched = try_start_subscribe_scheduler(config_path)
        if sched:
            info("订阅追剧调度器: 已启动")
    except Exception as e:
        info("订阅追剧调度器: 启动失败 - {}".format(e))



def _try_start_rss_scheduler(config_path):
    """尝试启动 RSS 订阅调度器"""
    try:
        from quark_cli.rss.manager import try_start_rss_scheduler
        sched = try_start_rss_scheduler(config_path)
        if sched:
            import logging
            logging.getLogger('quark_cli').info('RSS 调度器已启动')
    except Exception:
        pass


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

    # IPv6 双栈: 仅 Linux + bindv6only=0 时才安全使用 ::
    if host == "::":
        import platform
        if platform.system() != "Linux":
            # macOS/BSD 默认 IPV6_V6ONLY=1, bind :: 无法接受 IPv4
            host = "0.0.0.0"
        else:
            try:
                with open("/proc/sys/net/ipv6/conf/all/bindv6only") as _f:
                    if _f.read().strip() == "1":
                        host = "0.0.0.0"
            except OSError:
                host = "0.0.0.0"
    reload = getattr(args, "reload", False)
    no_open = getattr(args, "no_open", False)

    # 设置配置路径
    config_path = getattr(args, "config", None)
    from quark_cli.web.deps import set_config_path
    set_config_path(config_path)

    # --- IPv6 地址格式处理 ---
    def _display_host(h):
        """将监听地址转为浏览器可用的 host 部分"""
        if h in ("::", "0.0.0.0"):
            return "127.0.0.1"          # 本机回环, 浏览器兼容最好
        if ":" in h and not h.startswith("["):
            return "[{}]".format(h)      # 裸 IPv6 需要方括号
        return h

    display = _display_host(host)

    from quark_cli.display import success, info, kvline
    success("启动 Quark CLI Web 面板")
    kvline("监听", "{} (IPv6 双栈)".format(host) if ":" in host else host)
    kvline("地址", "http://{}:{}".format(display, port))
    kvline("API 文档", "http://{}:{}/api/docs".format(display, port))
    if reload:
        info("开发模式: 热重载已启用")

    # 尝试在后台启动飞书机器人
    if not reload:
        _try_start_bot(config_path)

    # 尝试启动定时任务调度器
    if not reload:
        _try_start_scheduler(config_path)

    # 尝试启动同步定时调度器
    if not reload:
        _try_start_sync_scheduler(config_path)

    # 尝试启动 Cookie 保活
    if not reload:
        _try_start_keepalive(config_path)

    # 尝试启动 RSS 订阅调度器
    if not reload:
        _try_start_rss_scheduler(config_path)

    # 自动打开浏览器
    if not no_open and not reload:
        import threading, webbrowser
        url = "http://{}:{}".format(display, port)
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
    from quark_cli.commands import sync_cmd, rss_cmd, torrent_cmd, guangya_cmd

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
        "sync": sync_cmd.handle,
        "rss": rss_cmd.handle,
        "torrent": torrent_cmd.handle,
        "guangya": guangya_cmd.handle,
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
