"""
RSS 订阅管理器

负责 Feed 的 CRUD、状态维护、去重记录。
数据存储在 config.json → rss_feeds[] 和 SQLite history。
已处理的 item guid 存储在 SQLite 表 rss_seen 中。
"""

import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from quark_cli.rss.fetcher import FeedItem, FeedResult, FetchError, fetch_feed
from quark_cli.rss.matcher import MatchResult, match_items, match_items_with_reasons, merge_rule_defaults
from quark_cli.rss.actions import execute_action

logger = logging.getLogger("quark_cli.rss.manager")


# ═══════════════════════════════════════════════════
#  Feed 默认配置
# ═══════════════════════════════════════════════════

DEFAULT_FEED = {
    "id": "",
    "name": "",
    "feed_url": "",
    "feed_type": "auto",            # auto / rss / atom / json
    "interval_minutes": 30,
    "enabled": True,

    "auth": {
        "passkey": "",
        "cookie": "",
        "headers": {},
    },

    "rules": [],

    "max_items_per_check": 50,
    "action_delay_seconds": 0,   # 每条匹配动作间隔秒数 (0 = 不等待)
    "post_actions": [],          # 一轮完成后的后置动作列表
    "dedupe_window_hours": 168,      # 7 天
    "bot_notify": True,

    # 状态 (自动维护)
    "last_check": None,
    "last_item_id": "",
    "last_item_date": "",
    "etag": "",
    "last_modified": "",
    "error": "",
    "stats": {
        "total_checked": 0,
        "total_matched": 0,
        "total_saved": 0,
    },
}


def _merge_feed_defaults(feed):
    """填充默认值"""
    merged = dict(DEFAULT_FEED)
    # 深拷贝 auth 和 stats
    merged["auth"] = dict(DEFAULT_FEED["auth"])
    merged["stats"] = dict(DEFAULT_FEED["stats"])
    for k, v in feed.items():
        if k == "auth" and isinstance(v, dict):
            merged["auth"].update(v)
        elif k == "stats" and isinstance(v, dict):
            merged["stats"].update(v)
        elif k == "rules" and isinstance(v, list):
            merged["rules"] = [merge_rule_defaults(r) for r in v]
        else:
            merged[k] = v
    return merged


def _generate_feed_id():
    """生成短 Feed ID"""
    return "feed_" + uuid.uuid4().hex[:8]


# ═══════════════════════════════════════════════════
#  去重存储 (SQLite)
# ═══════════════════════════════════════════════════

_seen_lock = threading.Lock()
_seen_conn = None


def _get_seen_db(config_path):
    """获取 RSS 去重数据库连接"""
    import os
    global _seen_conn
    with _seen_lock:
        if _seen_conn is None:
            if config_path:
                db_dir = os.path.dirname(os.path.abspath(config_path))
            else:
                db_dir = os.path.join(os.path.expanduser("~"), ".quark-cli")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "rss_seen.db")
            _seen_conn = sqlite3.connect(db_path, check_same_thread=False)
            _seen_conn.execute("PRAGMA journal_mode=WAL")
            _seen_conn.executescript("""
                CREATE TABLE IF NOT EXISTS rss_seen (
                    feed_id  TEXT NOT NULL,
                    guid     TEXT NOT NULL,
                    title    TEXT NOT NULL DEFAULT '',
                    seen_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    PRIMARY KEY (feed_id, guid)
                );
                CREATE INDEX IF NOT EXISTS idx_rss_seen_ts ON rss_seen(seen_at);
            """)
            _seen_conn.commit()
        return _seen_conn


def get_seen_guids(feed_id, config_path=None):
    """获取已处理的 guid 集合"""
    conn = _get_seen_db(config_path)
    with _seen_lock:
        rows = conn.execute(
            "SELECT guid FROM rss_seen WHERE feed_id = ?", (feed_id,)
        ).fetchall()
    return {row[0] for row in rows}


def mark_seen(feed_id, guid, title="", config_path=None):
    """标记 guid 已处理"""
    conn = _get_seen_db(config_path)
    with _seen_lock:
        conn.execute(
            "INSERT OR IGNORE INTO rss_seen (feed_id, guid, title) VALUES (?, ?, ?)",
            (feed_id, guid, title),
        )
        conn.commit()


def cleanup_seen(feed_id=None, keep_hours=168, config_path=None):
    """清理过期的去重记录"""
    conn = _get_seen_db(config_path)
    with _seen_lock:
        if feed_id:
            conn.execute(
                "DELETE FROM rss_seen WHERE feed_id = ? AND seen_at < datetime('now', 'localtime', ?)",
                (feed_id, "-{} hours".format(int(keep_hours))),
            )
        else:
            conn.execute(
                "DELETE FROM rss_seen WHERE seen_at < datetime('now', 'localtime', ?)",
                ("-{} hours".format(int(keep_hours)),),
            )
        conn.commit()


# ═══════════════════════════════════════════════════
#  Feed CRUD (操作 config.json)
# ═══════════════════════════════════════════════════


def _run_pre_check(script_path, match_result):
    """执行 pre-check 脚本

    脚本通过环境变量接收匹配信息:
      RSS_ITEM_TITLE, RSS_ITEM_GUID, RSS_ITEM_LINK,
      RSS_RULE_NAME, RSS_ACTION, RSS_LINK_TYPE

    返回: True (脚本退出 0, 通过) / False (非 0, 拒绝)
    """
    import subprocess

    if not os.path.isfile(script_path):
        logger.warning("pre-check 脚本不存在: %s", script_path)
        return False

    env = dict(os.environ)
    item = match_result.item
    rule = match_result.rule
    env["RSS_ITEM_TITLE"] = item.title or ""
    env["RSS_ITEM_GUID"] = item.guid or ""
    env["RSS_ITEM_LINK"] = item.link or ""
    env["RSS_RULE_NAME"] = rule.get("name", "")
    env["RSS_ACTION"] = rule.get("action", "")
    env["RSS_LINK_TYPE"] = rule.get("link_type", "")

    # 传递链接
    links = match_result.get_target_links()
    env["RSS_TARGET_LINK"] = links[0] if links else ""

    try:
        result = subprocess.run(
            [script_path],
            env=env,
            capture_output=True, text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.info("pre-check 拒绝 [%s]: exit=%d, stderr=%s",
                        item.title[:60], result.returncode, result.stderr[:200])
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.warning("pre-check 超时 (30s): %s", script_path)
        return False
    except Exception as e:
        logger.warning("pre-check 异常: %s — %s", script_path, e)
        return False


class RssManager:
    """RSS 订阅管理器"""

    def __init__(self, config_path=None):
        self.config_path = config_path

    def _load_config(self):
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        return cfg

    def _get_feeds(self, cfg):
        return cfg.data.get("rss_feeds", [])

    def _save_feeds(self, cfg, feeds):
        cfg._data["rss_feeds"] = feeds
        cfg.save()

    def _get_proxy(self, cfg=None):
        """获取 RSS 代理配置, 若未启用则返回 None"""
        if cfg is None:
            cfg = self._load_config()
        proxy_cfg = cfg.data.get("proxy", {})
        proxy_url = proxy_cfg.get("url", "").strip()
        if not proxy_url:
            return None
        targets = proxy_cfg.get("targets", [])
        if "rss" in targets:
            return proxy_url
        return None

    # ── 列表 ──

    def list_feeds(self):
        """获取所有 Feed 列表"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        return [_merge_feed_defaults(f) for f in feeds]

    # ── 获取单个 ──

    def get_feed(self, feed_id_or_name):
        """按 ID 或名称获取 Feed"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        for f in feeds:
            if f.get("id") == feed_id_or_name or f.get("name") == feed_id_or_name:
                return _merge_feed_defaults(f)
        return None

    # ── 新增 ──

    def add_feed(self, feed_url, name="", interval_minutes=30, auth=None, rules=None):
        """新增 RSS Feed"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)

        # 检查 URL 重复
        for f in feeds:
            if f.get("feed_url") == feed_url:
                raise ValueError("Feed URL 已存在: {}".format(feed_url))

        feed_id = _generate_feed_id()
        feed = _merge_feed_defaults({
            "id": feed_id,
            "name": name or feed_url[:60],
            "feed_url": feed_url,
            "interval_minutes": interval_minutes,
            "auth": auth or {},
            "rules": rules or [],
        })

        feeds.append(feed)
        self._save_feeds(cfg, feeds)
        return feed

    # ── 更新 ──

    def update_feed(self, feed_id_or_name, updates):
        """更新 Feed 配置"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)

        for i, f in enumerate(feeds):
            if f.get("id") == feed_id_or_name or f.get("name") == feed_id_or_name:
                for k, v in updates.items():
                    if k in ("id",):
                        continue  # 不允许改 ID
                    if k == "auth" and isinstance(v, dict):
                        f.setdefault("auth", {}).update(v)
                    elif k == "stats" and isinstance(v, dict):
                        f.setdefault("stats", {}).update(v)
                    else:
                        f[k] = v
                feeds[i] = f
                self._save_feeds(cfg, feeds)
                return _merge_feed_defaults(f)

        raise ValueError("Feed 不存在: {}".format(feed_id_or_name))

    # ── 删除 ──

    def remove_feed(self, feed_id_or_name):
        """删除 Feed"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        before = len(feeds)
        feeds = [f for f in feeds
                 if f.get("id") != feed_id_or_name and f.get("name") != feed_id_or_name]
        if len(feeds) == before:
            raise ValueError("Feed 不存在: {}".format(feed_id_or_name))
        self._save_feeds(cfg, feeds)

    # ── 启用/禁用 ──

    def toggle_feed(self, feed_id_or_name):
        """切换 Feed 启用状态"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        for f in feeds:
            if f.get("id") == feed_id_or_name or f.get("name") == feed_id_or_name:
                f["enabled"] = not f.get("enabled", True)
                self._save_feeds(cfg, feeds)
                return f["enabled"]
        raise ValueError("Feed 不存在: {}".format(feed_id_or_name))

    # ── 规则管理 ──

    def add_rule(self, feed_id_or_name, rule):
        """给 Feed 添加规则"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        for f in feeds:
            if f.get("id") == feed_id_or_name or f.get("name") == feed_id_or_name:
                if "rules" not in f:
                    f["rules"] = []
                f["rules"].append(merge_rule_defaults(rule))
                self._save_feeds(cfg, feeds)
                return f["rules"]
        raise ValueError("Feed 不存在: {}".format(feed_id_or_name))

    def remove_rule(self, feed_id_or_name, rule_index):
        """删除 Feed 的指定规则"""
        cfg = self._load_config()
        feeds = self._get_feeds(cfg)
        for f in feeds:
            if f.get("id") == feed_id_or_name or f.get("name") == feed_id_or_name:
                rules = f.get("rules", [])
                if 0 <= rule_index < len(rules):
                    rules.pop(rule_index)
                    f["rules"] = rules
                    self._save_feeds(cfg, feeds)
                    return rules
                raise ValueError("规则索引越界: {} (共 {} 条)".format(rule_index, len(rules)))
        raise ValueError("Feed 不存在: {}".format(feed_id_or_name))

    # ── 检查单个 Feed ──

    def check_feed(self, feed_id_or_name, dry_run=False):
        """
        拉取并检查单个 Feed.

        Returns:
            dict: {feed_id, new_items, matched, actions, error}
        """
        feed = self.get_feed(feed_id_or_name)
        if not feed:
            return {"error": "Feed 不存在: {}".format(feed_id_or_name)}

        if not feed.get("enabled", True):
            return {
                "feed_id": feed.get("id", ""),
                "feed_name": feed.get("name", ""),
                "error": "Feed 已禁用，请先启用后再检查",
                "new_items": 0, "matched": 0, "actions": [],
            }

        return self._execute_check(feed, dry_run=dry_run)

    def _execute_check(self, feed, dry_run=False):
        """执行单次 Feed 检查"""
        feed_id = feed["id"]
        feed_name = feed["name"]
        result = {
            "feed_id": feed_id,
            "feed_name": feed_name,
            "new_items": 0,
            "matched": 0,
            "skipped": 0,
            "actions": [],
            "unmatched_items": [],
            "error": "",
        }

        t0 = time.time()

        # 1. 拉取 Feed
        try:
            feed_result = fetch_feed(
                feed["feed_url"],
                auth=feed.get("auth"),
                etag=feed.get("etag", ""),
                last_modified=feed.get("last_modified", ""),
                proxy=self._get_proxy(),
            )
        except FetchError as e:
            result["error"] = str(e)
            self._update_feed_state(feed, error=str(e))
            return result

        if feed_result.not_modified:
            self._update_feed_state(feed, error="")
            result["new_items"] = 0
            return result

        # 2. 限制条目数
        items = feed_result.items[:feed.get("max_items_per_check", 50)]

        # 3. 去重 — 过滤已处理的 item
        seen_guids = get_seen_guids(feed_id, self.config_path)
        new_items = [it for it in items if it.guid and it.guid not in seen_guids]
        result["new_items"] = len(new_items)
        result["skipped"] = len(items) - len(new_items)

        # 4. 规则匹配
        rules = feed.get("rules", [])
        if not rules:
            # 无规则 — 不标记 seen, 等用户配好规则后可重新匹配
            self._update_feed_state(
                feed, error="",
                etag=feed_result.etag,
                last_modified=feed_result.last_modified,
                last_item=items[0] if items else None,
            )
            result["unmatched_items"] = [{
                "title": it.title, "guid": it.guid,
                "pub_date": it.pub_date.isoformat() if it.pub_date else None,
                "reason": "无匹配规则",
            } for it in new_items[:50]]
            return result

        # 对新 item 执行匹配 (已去重, 不再传 seen_guids)
        matches, unmatched_items = match_items_with_reasons(new_items, rules, seen_guids=None)
        result["matched"] = len(matches)
        result["unmatched_items"] = unmatched_items[:50]

        # 5. 执行动作
        delay_sec = float(feed.get("action_delay_seconds", 0) or 0)
        for i, match in enumerate(matches):
            # pre-check 插件
            pre_script = match.rule.get("pre_check", "").strip()
            if pre_script and not dry_run:
                if not _run_pre_check(pre_script, match):
                    result["actions"].append({
                        "action": match.action,
                        "item_title": match.item.title,
                        "rule_name": match.rule.get("name", ""),
                        "success": False,
                        "detail": {"error": "pre-check 脚本拒绝: {}".format(pre_script)},
                        "skipped_by_precheck": True,
                    })
                    continue

            if dry_run:
                result["actions"].append({
                    "dry_run": True,
                    "item_title": match.item.title,
                    "rule_name": match.rule.get("name", ""),
                    "action": match.action,
                    "target_links": match.get_target_links(),
                })
            else:
                action_result = execute_action(match, config_path=self.config_path)
                result["actions"].append(action_result)

            # 标记已处理
            mark_seen(feed_id, match.item.guid, match.item.title, self.config_path)

            # 动作间隔
            if delay_sec > 0 and i < len(matches) - 1 and not dry_run:
                time.sleep(delay_sec)

        # 只标记匹配到的 item 为 seen
        # 未匹配的不标记, 用户调整规则后可重新匹配

        # 5.5 后置动作 (post_actions)
        if not dry_run:
            post_results = self._execute_post_actions(feed, result)
            if post_results:
                result["post_actions"] = post_results

        # 6. 更新状态
        saved_count = sum(
            1 for a in result["actions"]
            if a.get("success") and a.get("action") in ("auto_save", "torrent")
        )
        self._update_feed_state(
            feed, error="",
            etag=feed_result.etag,
            last_modified=feed_result.last_modified,
            last_item=items[0] if items else None,
            matched=len(matches),
            saved=saved_count,
        )

        result["duration"] = round(time.time() - t0, 2)
        return result

    def _execute_post_actions(self, feed, check_result):
        """执行一轮检查完成后的后置动作"""
        post_actions = feed.get("post_actions", [])
        if not post_actions:
            return []

        success_actions = [a for a in check_result.get("actions", []) if a.get("success")]
        if not success_actions:
            return []

        results = []
        for pa in post_actions:
            pa_type = pa.get("type", "")
            try:
                if pa_type == "guangya_copy":
                    r = self._post_action_guangya_copy(pa, success_actions)
                    results.append({"type": pa_type, **r})
                else:
                    results.append({"type": pa_type, "success": False, "error": "未知后置动作: {}".format(pa_type)})
            except Exception as e:
                logger.exception("后置动作异常: %s", pa_type)
                results.append({"type": pa_type, "success": False, "error": str(e)})
        return results

    def _post_action_guangya_copy(self, pa_config, success_actions):
        """光鸭云盘拷贝后置动作

        配置格式:
            {
                "type": "guangya_copy",
                "source_dir": "RSS下载",       # 源目录名或 ID
                "dest_dir": "媒体库/电影",      # 目标目录名/路径或 ID
                "delete_after_copy": false,     # 拷贝完是否删除源文件
            }
        """
        from quark_cli.config import ConfigManager
        from quark_cli.guangya_api import GuangyaAPI

        cfg = ConfigManager(self.config_path)
        cfg.load()
        gy_cfg = cfg.data.get("guangya", {})
        refresh_token = gy_cfg.get("refresh_token", "")
        if not refresh_token:
            return {"success": False, "error": "未配置光鸭云盘 refresh_token"}

        client = GuangyaAPI(refresh_token=refresh_token)
        if not client.init():
            return {"success": False, "error": "光鸭云盘凭证无效"}

        # 解析源目录
        source_dir = pa_config.get("source_dir", "").strip()
        source_id = self._resolve_guangya_dir(client, source_dir)
        if source_id is None:
            return {"success": False, "error": "源目录不存在: {}".format(source_dir)}

        # 解析目标目录
        dest_dir = pa_config.get("dest_dir", "").strip()
        dest_id = self._resolve_guangya_dir(client, dest_dir, auto_create=True)
        if dest_id is None:
            return {"success": False, "error": "目标目录解析失败: {}".format(dest_dir)}

        # 列出源目录下所有文件
        ls_result = client.ls_dir(parent_id=source_id, page_size=200)
        if not client._ok(ls_result):
            return {"success": False, "error": "列出源目录失败"}

        file_list = ls_result.get("data", {}).get("list", [])
        if not file_list:
            return {"success": True, "copied": 0, "message": "源目录为空"}

        file_ids = [f["fileId"] for f in file_list]

        # 拷贝
        copy_resp = client.copy_file(file_ids, dest_parent_id=dest_id)
        if not client._ok(copy_resp):
            return {"success": False, "error": "拷贝失败: {}".format(copy_resp.get("msg", "unknown"))}

        result = {"success": True, "copied": len(file_ids)}

        # 拷贝完删除源文件
        if pa_config.get("delete_after_copy", False):
            del_resp = client.delete(file_ids, wait=True)
            if client._ok(del_resp):
                result["deleted"] = len(file_ids)
            else:
                result["delete_error"] = del_resp.get("msg", "删除失败")

        return result

    @staticmethod
    def _resolve_guangya_dir(client, dir_spec, auto_create=False):
        """解析光鸭目录: 支持 ID 或路径名

        如果 dir_spec 看起来像 ID (纯数字或含特定格式), 直接使用;
        否则按路径名逐级查找/创建.
        """
        if not dir_spec:
            return ""  # 根目录

        # 如果是纯数字或像 file ID 格式, 直接作为 ID
        if dir_spec.isdigit() or len(dir_spec) > 20:
            return dir_spec

        # 否则按路径名解析
        if auto_create:
            return client.resolve_dir_path(dir_spec)
        else:
            # 逐级查找但不创建
            parts = [p.strip() for p in dir_spec.replace("\\", "/").split("/") if p.strip()]
            current_id = ""
            for part in parts:
                found = client.find_dir_by_name(part, parent_id=current_id)
                if not found:
                    return None
                current_id = found
            return current_id

    def _update_feed_state(self, feed, error="", etag="", last_modified="",
                           last_item=None, matched=0, saved=0):
        """更新 Feed 状态到 config"""
        try:
            cfg = self._load_config()
            feeds = cfg.data.get("rss_feeds", [])
            for f in feeds:
                if f.get("id") == feed["id"]:
                    f["last_check"] = datetime.now().isoformat(timespec="seconds")
                    f["error"] = error
                    if etag:
                        f["etag"] = etag
                    if last_modified:
                        f["last_modified"] = last_modified
                    if last_item:
                        f["last_item_id"] = last_item.guid
                        f["last_item_date"] = (
                            last_item.pub_date.isoformat() if last_item.pub_date else ""
                        )
                    stats = f.get("stats", {})
                    stats["total_checked"] = stats.get("total_checked", 0) + 1
                    stats["total_matched"] = stats.get("total_matched", 0) + matched
                    stats["total_saved"] = stats.get("total_saved", 0) + saved
                    f["stats"] = stats
                    break
            cfg._data["rss_feeds"] = feeds
            cfg.save()
        except Exception:
            logger.debug("更新 Feed 状态失败", exc_info=True)

    # ── 测试 Feed ──

    def test_feed(self, feed_url, auth=None, max_items=10):
        """
        测试拉取 Feed, 返回前 N 条条目 (不写入任何状态).

        Returns:
            dict: {feed_title, feed_link, items: [...]}
        """
        try:
            feed_result = fetch_feed(feed_url, auth=auth, proxy=self._get_proxy())
        except FetchError as e:
            return {"error": str(e)}

        items = feed_result.items[:max_items]
        return {
            "feed_title": feed_result.feed_title,
            "feed_link": feed_result.feed_link,
            "feed_description": feed_result.feed_description,
            "item_count": len(feed_result.items),
            "items": [item.to_dict() for item in items],
        }


# ═══════════════════════════════════════════════════
#  RSS 调度器
# ═══════════════════════════════════════════════════

class RssScheduler:
    """RSS 订阅调度器 (后台守护线程)"""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self._running = False
        self._thread = None
        self._last_check = {}   # feed_id → datetime
        self._results = {}      # feed_id → last check result

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("RSS 调度器已启动")

    def stop(self):
        self._running = False
        logger.info("RSS 调度器已停止")

    def _loop(self):
        time.sleep(30)  # 启动延迟
        while self._running:
            try:
                manager = RssManager(self.config_path)
                feeds = manager.list_feeds()
                now = datetime.now()

                for feed in feeds:
                    if not feed.get("enabled", True):
                        continue
                    feed_id = feed["id"]
                    interval_sec = int(feed.get("interval_minutes", 30)) * 60
                    last = self._last_check.get(feed_id)
                    if last and (now - last).total_seconds() < interval_sec:
                        continue

                    logger.info("RSS 检查: %s (%s)", feed["name"], feed["feed_url"][:60])
                    self._last_check[feed_id] = now

                    try:
                        result = manager._execute_check(feed)
                        self._results[feed_id] = result
                        logger.info("RSS 完成: %s — 新 %d, 匹配 %d",
                                    feed["name"], result.get("new_items", 0), result.get("matched", 0))
                    except Exception:
                        logger.exception("RSS 检查异常: %s", feed["name"])

                # 定期清理去重记录
                try:
                    cleanup_seen(keep_hours=168, config_path=self.config_path)
                except Exception:
                    pass

            except Exception:
                logger.exception("RSS 调度循环异常")
            time.sleep(60)

    def get_status(self):
        """获取调度器状态"""
        manager = RssManager(self.config_path)
        feeds = manager.list_feeds()

        feed_status = []
        for feed in feeds:
            fid = feed["id"]
            feed_status.append({
                "id": fid,
                "name": feed["name"],
                "feed_url": feed["feed_url"],
                "enabled": feed.get("enabled", True),
                "interval_minutes": feed.get("interval_minutes", 30),
                "last_check": feed.get("last_check"),
                "error": feed.get("error", ""),
                "rules_count": len(feed.get("rules", [])),
                "stats": feed.get("stats", {}),
                "last_result": self._results.get(fid),
            })

        return {
            "running": self._running,
            "feeds": feed_status,
        }

    def trigger_check(self, feed_id_or_name):
        """手动触发检查"""
        manager = RssManager(self.config_path)
        feed = manager.get_feed(feed_id_or_name)
        if not feed:
            return {"error": "Feed 不存在: {}".format(feed_id_or_name)}

        try:
            result = manager._execute_check(feed)
            self._results[feed["id"]] = result
            self._last_check[feed["id"]] = datetime.now()
            return result
        except Exception as e:
            return {"error": str(e)}


# ── 全局单例 ──

_rss_scheduler_instance = None


def get_rss_scheduler(config_path=None):
    global _rss_scheduler_instance
    if _rss_scheduler_instance is None:
        _rss_scheduler_instance = RssScheduler(config_path)
    return _rss_scheduler_instance


def try_start_rss_scheduler(config_path=None):
    """尝试启动 RSS 调度器, 无 Feed 则跳过"""
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path)
    cfg.load()
    feeds = cfg.data.get("rss_feeds", [])
    active = [f for f in feeds if f.get("enabled", True)]
    if not active:
        logger.info("RSS 订阅: 无活跃 Feed, 跳过")
        return None
    scheduler = get_rss_scheduler(config_path)
    scheduler.start()
    return scheduler
