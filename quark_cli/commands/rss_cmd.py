"""
rss 子命令处理模块 — RSS 订阅管理
"""

import json
import sys

from quark_cli.display import (
    Color, colorize, success, error, warning, info,
    header, subheader, kvline, divider, table_header, table_row,
    is_json_mode, json_out,
)


# ──────────────────────────────────────────────
# rss add
# ──────────────────────────────────────────────

def _handle_add(args):
    """rss add <feed_url>"""
    from quark_cli.rss.manager import RssManager

    feed_url = args.feed_url
    name = getattr(args, "name", "") or ""
    interval = getattr(args, "interval", 30) or 30

    # auth
    auth = {}
    if getattr(args, "passkey", None):
        auth["passkey"] = args.passkey
    if getattr(args, "cookie", None):
        auth["cookie"] = args.cookie

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    try:
        feed = manager.add_feed(feed_url, name=name, interval_minutes=interval, auth=auth)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    if is_json_mode():
        json_out({"status": "created", "feed": feed})
        return

    success("RSS Feed 已添加")
    kvline("ID", feed["id"])
    kvline("名称", feed["name"])
    kvline("URL", feed["feed_url"])
    kvline("检查间隔", "{} 分钟".format(feed["interval_minutes"]))
    print()
    info("添加规则: quark-cli rss rule add {} --match \"关键词\" --save-path \"/路径\"".format(feed["id"]))
    info("测试拉取: quark-cli rss test {}".format(feed["feed_url"][:60]))


# ──────────────────────────────────────────────
# rss list
# ──────────────────────────────────────────────

def _handle_list(args):
    """rss list"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)
    feeds = manager.list_feeds()

    if not feeds:
        if is_json_mode():
            json_out([])
        else:
            warning("暂无 RSS 订阅")
            info("添加: quark-cli rss add <feed_url> --name \"名称\"")
        return

    if is_json_mode():
        json_out([{
            "id": f["id"],
            "name": f["name"],
            "feed_url": f["feed_url"],
            "enabled": f["enabled"],
            "interval_minutes": f["interval_minutes"],
            "rules_count": len(f.get("rules", [])),
            "last_check": f.get("last_check"),
            "error": f.get("error", ""),
            "stats": f.get("stats", {}),
        } for f in feeds])
        return

    header("📡 RSS 订阅列表")
    cols = ["ID", "名称", "状态", "间隔", "规则", "上次检查", "错误"]
    widths = [14, 20, 6, 6, 5, 20, 20]
    table_header(cols, widths)
    for f in feeds:
        status = colorize("✔", Color.GREEN) if f["enabled"] else colorize("✗", Color.RED)
        err = f.get("error", "")[:18]
        table_row(
            [
                f["id"],
                f["name"][:18],
                status,
                "{}m".format(f["interval_minutes"]),
                str(len(f.get("rules", []))),
                f.get("last_check", "-") or "-",
                err or "-",
            ],
            widths,
            colors=[Color.DIM, Color.CYAN, None, Color.GREEN, Color.YELLOW, Color.DIM, Color.RED if err else Color.DIM],
        )
    print("\n  共 {} 个 Feed".format(len(feeds)))


# ──────────────────────────────────────────────
# rss show
# ──────────────────────────────────────────────

def _handle_show(args):
    """rss show <feed_id>"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)
    feed = manager.get_feed(args.feed_id)

    if not feed:
        error("Feed 不存在: {}".format(args.feed_id))
        sys.exit(1)

    if is_json_mode():
        json_out(feed)
        return

    header("📡 {}".format(feed["name"]))
    kvline("ID", feed["id"])
    kvline("URL", feed["feed_url"])
    kvline("状态", colorize("启用", Color.GREEN) if feed["enabled"] else colorize("禁用", Color.RED))
    kvline("检查间隔", "{} 分钟".format(feed["interval_minutes"]))
    kvline("上次检查", feed.get("last_check") or "从未")
    if feed.get("error"):
        kvline("错误", colorize(feed["error"], Color.RED))

    stats = feed.get("stats", {})
    if any(stats.values()):
        kvline("累计检查", str(stats.get("total_checked", 0)))
        kvline("累计匹配", str(stats.get("total_matched", 0)))
        kvline("累计转存", str(stats.get("total_saved", 0)))

    rules = feed.get("rules", [])
    if rules:
        subheader("📋 规则 ({})".format(len(rules)))
        for i, rule in enumerate(rules):
            print("  {}. {} {}".format(
                colorize(str(i), Color.CYAN),
                colorize(rule.get("name", "unnamed"), Color.GREEN),
                colorize("(禁用)" if not rule.get("enabled", True) else "", Color.DIM),
            ))
            if rule.get("match"):
                print("     匹配: {}".format(colorize(rule["match"], Color.YELLOW)))
            if rule.get("exclude"):
                print("     排除: {}".format(colorize(rule["exclude"], Color.RED)))
            if rule.get("quality"):
                print("     画质: {}".format(rule["quality"]))
            if rule.get("save_path"):
                print("     路径: {}".format(rule["save_path"]))
            print("     动作: {} | 链接: {}".format(rule.get("action", "auto_save"), rule.get("link_type", "quark")))
            print()
    else:
        print()
        warning("暂无规则")
        info("添加: quark-cli rss rule add {} --match \"关键词\"".format(feed["id"]))


# ──────────────────────────────────────────────
# rss remove
# ──────────────────────────────────────────────

def _handle_remove(args):
    """rss remove <feed_id>"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    try:
        manager.remove_feed(args.feed_id)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    if is_json_mode():
        json_out({"status": "deleted", "id": args.feed_id})
    else:
        success("已删除: {}".format(args.feed_id))


# ──────────────────────────────────────────────
# rss enable / disable
# ──────────────────────────────────────────────

def _handle_toggle(args):
    """rss enable/disable <feed_id>"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    try:
        enabled = manager.toggle_feed(args.feed_id)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    state = "启用" if enabled else "禁用"
    if is_json_mode():
        json_out({"status": "toggled", "id": args.feed_id, "enabled": enabled})
    else:
        success("{}: {}".format(args.feed_id, state))


# ──────────────────────────────────────────────
# rss test
# ──────────────────────────────────────────────

def _handle_test(args):
    """rss test <feed_url>"""
    from quark_cli.rss.manager import RssManager
    from quark_cli.rss.fetcher import extract_links

    feed_url = args.feed_url

    auth = {}
    if getattr(args, "passkey", None):
        auth["passkey"] = args.passkey
    if getattr(args, "cookie", None):
        auth["cookie"] = args.cookie

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    if not is_json_mode():
        info("正在拉取: {}".format(feed_url[:80]))

    result = manager.test_feed(feed_url, auth=auth or None)

    if result.get("error"):
        error("拉取失败: {}".format(result["error"]))
        sys.exit(1)

    if is_json_mode():
        json_out(result)
        return

    header("📡 {}".format(result.get("feed_title", "Feed")))
    kvline("链接", result.get("feed_link", ""))
    if result.get("feed_description"):
        kvline("描述", result["feed_description"][:100])
    kvline("条目总数", str(result.get("item_count", 0)))
    print()

    items = result.get("items", [])
    if not items:
        warning("Feed 中没有条目")
        return

    subheader("最新 {} 条".format(len(items)))
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        pub = item.get("pub_date", "")
        link = item.get("link", "")

        print("  {}. {}".format(
            colorize(str(i), Color.CYAN),
            colorize(title[:60], Color.GREEN),
        ))
        if pub:
            print("     {}".format(colorize(pub, Color.DIM)))

        # 分析链接类型
        from quark_cli.rss.fetcher import FeedItem
        fi = FeedItem(
            title=item.get("title", ""),
            link=item.get("link", ""),
            description=item.get("description", ""),
            enclosures=item.get("enclosures", []),
        )
        links = extract_links(fi)
        link_types = []
        for lt, urls in links.items():
            if urls and lt != "web":
                link_types.append("{}({})".format(lt, len(urls)))
        if link_types:
            print("     链接: {}".format(colorize(" ".join(link_types), Color.YELLOW)))
        print()


# ──────────────────────────────────────────────
# rss check
# ──────────────────────────────────────────────

def _handle_check(args):
    """rss check [feed_id]"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)
    feed_id = getattr(args, "feed_id", None)
    dry_run = getattr(args, "dry_run", False)

    if feed_id:
        # 检查单个
        if not is_json_mode():
            info("检查 Feed: {}".format(feed_id))

        result = manager.check_feed(feed_id, dry_run=dry_run)

        if result.get("error"):
            error(result["error"])
            sys.exit(1)

        if is_json_mode():
            json_out(result)
            return

        success("检查完成: {}".format(result.get("feed_name", feed_id)))
        kvline("新条目", str(result.get("new_items", 0)))
        kvline("匹配", str(result.get("matched", 0)))
        if result.get("actions"):
            subheader("执行结果")
            for a in result["actions"]:
                if a.get("dry_run"):
                    print("  [DRY] {} → {} ({})".format(
                        a.get("item_title", "")[:40],
                        a.get("action", ""),
                        a.get("rule_name", ""),
                    ))
                else:
                    status = "✔" if a.get("success") else "✗"
                    print("  {} {} → {}".format(
                        colorize(status, Color.GREEN if a.get("success") else Color.RED),
                        a.get("item_title", "")[:40],
                        a.get("detail", {}).get("save_path", "") or a.get("detail", {}).get("error", "")[:30],
                    ))
    else:
        # 检查所有
        feeds = manager.list_feeds()
        active = [f for f in feeds if f.get("enabled", True)]

        if not active:
            warning("无活跃 Feed")
            return

        if not is_json_mode():
            header("📡 检查所有 RSS Feed")

        results = []
        for feed in active:
            if not is_json_mode():
                info("检查: {}...".format(feed["name"]))
            result = manager.check_feed(feed["id"], dry_run=dry_run)
            results.append(result)
            if not is_json_mode():
                if result.get("error"):
                    error("  ✗ {}".format(result["error"]))
                else:
                    success("  ✔ 新 {}, 匹配 {}".format(
                        result.get("new_items", 0), result.get("matched", 0)))

        if is_json_mode():
            json_out(results)


# ──────────────────────────────────────────────
# rss rule add / list / remove
# ──────────────────────────────────────────────

def _handle_rule(args):
    """rss rule {add|list|remove}"""
    rule_action = getattr(args, "rule_action", None)

    if rule_action == "add":
        _handle_rule_add(args)
    elif rule_action == "list":
        _handle_rule_list(args)
    elif rule_action == "remove":
        _handle_rule_remove(args)
    else:
        error("用法: quark-cli rss rule {add|list|remove}")


def _handle_rule_add(args):
    """rss rule add <feed_id> --match ..."""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    rule = {
        "name": getattr(args, "name", "") or "",
        "match": getattr(args, "match", "") or "",
        "exclude": getattr(args, "exclude", "") or "",
        "quality": getattr(args, "quality", "") or "",
        "save_path": getattr(args, "save_path", "") or "",
        "action": getattr(args, "action", "auto_save") or "auto_save",
        "link_type": getattr(args, "link_type", "quark") or "quark",
    }

    min_size = getattr(args, "min_size", None)
    max_size = getattr(args, "max_size", None)
    if min_size is not None:
        rule["min_size_gb"] = float(min_size)
    if max_size is not None:
        rule["max_size_gb"] = float(max_size)

    try:
        rules = manager.add_rule(args.feed_id, rule)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    if is_json_mode():
        json_out({"status": "added", "rules_count": len(rules)})
    else:
        success("规则已添加 (共 {} 条)".format(len(rules)))


def _handle_rule_list(args):
    """rss rule list <feed_id>"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)
    feed = manager.get_feed(args.feed_id)
    if not feed:
        error("Feed 不存在: {}".format(args.feed_id))
        sys.exit(1)

    rules = feed.get("rules", [])
    if is_json_mode():
        json_out(rules)
        return

    if not rules:
        warning("{} 暂无规则".format(feed["name"]))
        return

    header("📋 {} — 规则".format(feed["name"]))
    for i, rule in enumerate(rules):
        print("  {}. {}".format(i, colorize(rule.get("name", "unnamed"), Color.GREEN)))
        print("     match={} | exclude={} | action={} | link={}".format(
            rule.get("match", "*") or "*",
            rule.get("exclude", "-") or "-",
            rule.get("action", "auto_save"),
            rule.get("link_type", "quark"),
        ))
        if rule.get("save_path"):
            print("     save_path={}".format(rule["save_path"]))
        print()


def _handle_rule_remove(args):
    """rss rule remove <feed_id> <index>"""
    from quark_cli.rss.manager import RssManager

    config_path = getattr(args, "config", None)
    manager = RssManager(config_path)

    try:
        rules = manager.remove_rule(args.feed_id, int(args.index))
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    if is_json_mode():
        json_out({"status": "removed", "rules_count": len(rules)})
    else:
        success("规则已删除 (剩余 {} 条)".format(len(rules)))


# ──────────────────────────────────────────────
# rss history
# ──────────────────────────────────────────────

def _handle_history(args):
    """rss history"""
    from quark_cli.history import query

    config_path = getattr(args, "config", None)
    limit = getattr(args, "limit", 20) or 20

    records = query(record_type="rss", limit=limit, config_path=config_path)

    if is_json_mode():
        json_out(records)
        return

    if not records:
        warning("暂无 RSS 历史记录")
        return

    header("📡 RSS 历史记录")
    cols = ["时间", "规则", "状态", "摘要"]
    widths = [20, 14, 8, 40]
    table_header(cols, widths)
    for r in records:
        status_color = Color.GREEN if r.get("status") == "success" else Color.RED
        table_row(
            [r.get("ts", ""), r.get("name", "")[:12], r.get("status", ""), r.get("summary", "")[:38]],
            widths,
            colors=[Color.DIM, Color.CYAN, status_color, None],
        )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def handle(args):
    """rss 命令分发"""
    action = getattr(args, "rss_action", None)

    if action == "add":
        _handle_add(args)
    elif action == "list":
        _handle_list(args)
    elif action == "show":
        _handle_show(args)
    elif action == "remove":
        _handle_remove(args)
    elif action in ("enable", "disable"):
        _handle_toggle(args)
    elif action == "test":
        _handle_test(args)
    elif action == "check":
        _handle_check(args)
    elif action == "rule":
        _handle_rule(args)
    elif action == "history":
        _handle_history(args)
    else:
        error("用法: quark-cli rss {add|list|show|remove|enable|disable|test|check|rule|history}")
        print()
        print("  RSS 订阅管理 — 自动拉取 Feed + 规则匹配 + 转存/通知")
        print()
        print("  Feed 管理:")
        print("    add       添加 RSS Feed")
        print("    list      列出所有 Feed")
        print("    show      查看 Feed 详情")
        print("    remove    删除 Feed")
        print("    enable    启用 Feed")
        print("    disable   禁用 Feed")
        print("    test      测试拉取 Feed (预览条目)")
        print("    check     立即触发检查")
        print()
        print("  规则管理:")
        print("    rule add     添加匹配规则")
        print("    rule list    查看规则列表")
        print("    rule remove  删除规则")
        print()
        print("  历史:")
        print("    history   查看 RSS 匹配/转存历史")
