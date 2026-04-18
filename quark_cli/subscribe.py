"""
订阅追剧引擎 — 周期性搜索 + 集数追踪 + 自动转存

工作原理:
  1. 从 config.json → subscriptions[] 读取订阅列表
  2. 调度器按 cron/interval 触发 check()
  3. 构造搜索词 (keyword + SxxExx) → 复用 PanSearch 搜索
  4. 集数提取 + 画质筛选 → 最佳候选 → auto_save 转存
  5. 贪心模式: 一次调度可追多集 (连续搜索直到无结果)
  6. 状态回写 config + history 记录

订阅配置 (config.json → subscriptions[]):
  {
    "name":               "三体",
    "keyword":            "三体 2024",
    "season":             1,
    "next_episode":       6,
    "max_episode":        null,
    "quality":            "4K|2160p|1080p",
    "save_path":          "/追剧/三体/S01",
    "interval_minutes":   240,
    "cron":               "",
    "enabled":            true,
    "finished":           false,
    "miss_count":         0,
    "last_check":         null,
    "last_episode":       5,
    "episodes_found":     [1,2,3,4,5],
    "bot_notify":         true
  }
"""

import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quark_cli.subscribe")


# ═══════════════════════════════════════════════════════════
#  集数提取器
# ═══════════════════════════════════════════════════════════

EPISODE_PATTERNS = [
    # S01E05, s1e05
    (r'[Ss](\d{1,2})[Ee](\d{1,3})', True),
    # Season 1 Episode 5
    (r'[Ss]eason\s*(\d+).*?[Ee]p(?:isode)?\s*(\d+)', True),
    # 第1季第5集 / 第1季第5话 / 第1季第5期
    (r'第(\d+)季.*?第(\d+)[集话期]', True),
    # EP05 / E05 (单集号, 无季号)
    (r'[Ee][Pp]?(\d{2,3})(?!\d)', False),
    # [05] 或 .05. (常见于动漫)
    (r'[\[\s\.](\d{2,3})[\]\s\.]', False),
    # 第5集 / 第5话 (无季号)
    (r'第(\d+)[集话期]', False),
]


def extract_episode(filename, default_season=1):
    """
    从文件名提取 (season, episode).

    Returns:
        (season, episode) 或 (None, None)
    """
    for pattern, has_season in EPISODE_PATTERNS:
        m = re.search(pattern, filename)
        if m:
            groups = m.groups()
            if has_season and len(groups) == 2:
                return int(groups[0]), int(groups[1])
            elif len(groups) >= 1:
                return default_season, int(groups[-1])
    return None, None


def build_search_queries(keyword, season, episode):
    """
    构造多种搜索关键词, 提高命中率.

    Returns:
        关键词列表 (优先级从高到低)
    """
    queries = []
    queries.append("{} S{:02d}E{:02d}".format(keyword, season, episode))
    queries.append("{} 第{}集".format(keyword, episode))
    queries.append("{} E{:02d}".format(keyword, episode))
    queries.append(keyword)
    return queries


def filter_candidates(results, season, episode, quality_re=None):
    """
    从搜索结果中找到匹配指定季集的最佳资源.
    """
    matched = []
    for item in results:
        title = item.get("title", "") or item.get("note", "")
        s, e = extract_episode(title, default_season=season)
        if s == season and e == episode:
            matched.append(item)

    if not matched:
        return None

    if quality_re:
        for q_pattern in quality_re.split("|"):
            q_pattern = q_pattern.strip()
            if not q_pattern:
                continue
            for item in matched:
                title = item.get("title", "") or item.get("note", "")
                if re.search(q_pattern, title, re.IGNORECASE):
                    return item

    scored = [m for m in matched if m.get("score")]
    if scored:
        return max(scored, key=lambda x: x["score"])
    return matched[0]


# ═══════════════════════════════════════════════════════════
#  默认配置 + 工具函数
# ═══════════════════════════════════════════════════════════

DEFAULT_SUB = {
    "name": "",
    "keyword": "",
    "season": 1,
    "next_episode": 1,
    "max_episode": None,
    "quality": "",
    "save_path": "/追剧",
    "interval_minutes": 240,
    "cron": "",
    "enabled": True,
    "finished": False,
    "miss_count": 0,
    "last_check": None,
    "last_episode": 0,
    "episodes_found": [],
    "bot_notify": True,
}

MAX_GREEDY_EPISODES = 50
MISS_THRESHOLD = 5


def _merge_sub_defaults(sub):
    merged = dict(DEFAULT_SUB)
    merged.update(sub)
    return merged


def _parse_sub_interval(sub):
    """解析订阅的检查间隔 (秒)"""
    if sub.get("interval_minutes"):
        return int(sub["interval_minutes"]) * 60
    cron = sub.get("cron", "")
    if cron:
        parts = cron.strip().split()
        if len(parts) >= 2:
            try:
                minute, hour = int(parts[0]), int(parts[1])
                now = datetime.now()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return max(int((target - now).total_seconds()), 60)
            except (ValueError, IndexError):
                pass
    return 240 * 60


# ═══════════════════════════════════════════════════════════
#  单次订阅检查
# ═══════════════════════════════════════════════════════════

def check_subscription(sub_config, config_path=None):
    """
    执行一次订阅检查 (贪心模式: 一次可追多集).
    """
    from quark_cli.config import ConfigManager

    sub = _merge_sub_defaults(sub_config)
    name = sub["name"]
    keyword = sub.get("keyword") or name
    season = sub["season"]
    episode = sub["next_episode"]
    max_ep = sub.get("max_episode")
    quality = sub.get("quality", "")
    save_path = sub["save_path"]

    result = {
        "name": name,
        "new_episodes": [],
        "checked_up_to": episode - 1,
        "finished": False,
        "error": None,
    }

    try:
        cfg = ConfigManager(config_path)
        cfg.load()

        from quark_cli.api import QuarkAPI
        from quark_cli.search import PanSearch

        cookies = cfg.get_cookies()
        if not cookies:
            result["error"] = "未配置 Cookie"
            return result

        client = QuarkAPI(cookies[0])
        if not client.init():
            result["error"] = "Cookie 失效"
            return result

        searcher = PanSearch(cfg)
    except Exception as e:
        result["error"] = "初始化失败: {}".format(str(e))
        return result

    consecutive_miss = 0
    for _ in range(MAX_GREEDY_EPISODES):
        if max_ep and episode > max_ep:
            result["finished"] = True
            break

        queries = build_search_queries(keyword, season, episode)
        logger.info("[%s] 检查 S%02dE%02d, 关键词: %s", name, season, episode, queries[0])

        best_candidate = None
        for q in queries:
            try:
                search_result = searcher.search_all(q)
                if not search_result.get("success"):
                    continue
                items = search_result.get("results", [])
                if not items:
                    continue
                candidate = filter_candidates(items, season, episode, quality)
                if candidate:
                    best_candidate = candidate
                    break
            except Exception as e:
                logger.debug("搜索异常 [%s]: %s", q, e)
                continue

        if not best_candidate:
            consecutive_miss += 1
            logger.info("[%s] S%02dE%02d 未找到 (miss %d)", name, season, episode, consecutive_miss)
            if max_ep and episode > max_ep:
                result["finished"] = True
            elif consecutive_miss >= MISS_THRESHOLD and max_ep:
                result["finished"] = True
            break

        url = best_candidate["url"]
        file_title = best_candidate.get("title", "")
        logger.info("[%s] S%02dE%02d 找到: %s", name, season, episode, file_title[:60])

        try:
            from quark_cli.media.autosave import auto_save_pipeline

            save_result = auto_save_pipeline(
                quark_client=client,
                search_engine=searcher,
                keywords=["{} S{:02d}E{:02d}".format(keyword, season, episode)],
                save_path=save_path,
                max_attempts=3,
                media_title=name,
                media_type="tv",
            )

            if save_result.get("success"):
                ep_info = {
                    "season": season,
                    "episode": episode,
                    "file_title": file_title,
                    "url": url,
                    "save_path": save_path,
                    "saved_count": save_result.get("saved_count", 0),
                }
                result["new_episodes"].append(ep_info)
                result["checked_up_to"] = episode
                consecutive_miss = 0
            else:
                logger.warning("[%s] S%02dE%02d 转存失败: %s",
                               name, season, episode, save_result.get("error", ""))
                break
        except Exception as e:
            logger.exception("[%s] S%02dE%02d 转存异常", name, season, episode)
            result["error"] = "S{:02d}E{:02d} 转存异常: {}".format(season, episode, str(e))
            break

        episode += 1

    return result


# ═══════════════════════════════════════════════════════════
#  状态回写
# ═══════════════════════════════════════════════════════════

def update_subscription_state(config_path, sub_name, check_result):
    """将检查结果回写到 config.json"""
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()

    subs = cfg.data.get("subscriptions", [])
    for sub in subs:
        if sub.get("name") != sub_name:
            continue

        sub["last_check"] = datetime.now().isoformat(timespec="seconds")

        new_eps = check_result.get("new_episodes", [])
        if new_eps:
            last_ep = max(ep["episode"] for ep in new_eps)
            sub["next_episode"] = last_ep + 1
            sub["last_episode"] = last_ep
            sub["miss_count"] = 0
            found = set(sub.get("episodes_found", []))
            for ep in new_eps:
                found.add(ep["episode"])
            sub["episodes_found"] = sorted(found)
        else:
            sub["miss_count"] = sub.get("miss_count", 0) + 1

        if check_result.get("finished"):
            sub["finished"] = True
        break

    cfg.save()


# ═══════════════════════════════════════════════════════════
#  飞书通知
# ═══════════════════════════════════════════════════════════

def format_subscribe_notify(sub_config, check_result):
    """将追更结果格式化为飞书 post 消息"""
    lines = []
    name = check_result.get("name", sub_config.get("name", ""))
    new_eps = check_result.get("new_episodes", [])

    if new_eps:
        ep_list = ", ".join("E{:02d}".format(ep["episode"]) for ep in new_eps)
        lines.append([{"tag": "text", "text": "🎬 {} 更新啦！".format(name)}])
        lines.append([{"tag": "text", "text": "新集数: {} (共{}集)".format(ep_list, len(new_eps))}])
        for ep in new_eps:
            lines.append([{"tag": "text", "text": "  ✅ S{:02d}E{:02d} → {}".format(
                ep["season"], ep["episode"], ep.get("save_path", ""))}])
    elif check_result.get("finished"):
        lines.append([{"tag": "text", "text": "📺 {} 已完结".format(name)}])
    elif check_result.get("error"):
        lines.append([{"tag": "text", "text": "⚠️ {} 检查异常: {}".format(name, check_result["error"])}])
    else:
        return {}

    title = "📺 追剧更新 · {}".format(name)
    return {"zh_cn": {"title": title, "content": lines}}


# ═══════════════════════════════════════════════════════════
#  调度器
# ═══════════════════════════════════════════════════════════

class SubscribeScheduler:
    """订阅追剧调度器 (后台守护线程)"""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self._running = False
        self._thread = None
        self._task_threads = {}
        self._last_check = {}
        self._results = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("订阅追剧调度器已启动")

    def stop(self):
        self._running = False
        logger.info("订阅追剧调度器已停止")

    def _load_subscriptions(self):
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        subs = cfg.data.get("subscriptions", [])
        return [_merge_sub_defaults(s) for s in subs
                if s.get("enabled", True) and not s.get("finished", False)]

    def _loop(self):
        time.sleep(60)
        while self._running:
            try:
                subs = self._load_subscriptions()
                now = datetime.now()
                for sub in subs:
                    name = sub["name"]
                    interval = _parse_sub_interval(sub)
                    last = self._last_check.get(name)
                    if last and (now - last).total_seconds() < interval:
                        continue
                    if name in self._task_threads and self._task_threads[name].is_alive():
                        continue
                    logger.info("检查订阅: %s", name)
                    self._last_check[name] = now
                    t = threading.Thread(
                        target=self._execute_check, args=(sub,), daemon=True
                    )
                    self._task_threads[name] = t
                    t.start()
            except Exception:
                logger.exception("订阅调度循环异常")
            time.sleep(60)

    def _execute_check(self, sub):
        name = sub["name"]
        t0 = time.time()
        try:
            result = check_subscription(sub, self.config_path)
            self._results[name] = result
            duration = time.time() - t0

            try:
                update_subscription_state(self.config_path, name, result)
            except Exception:
                logger.exception("订阅状态回写失败: %s", name)

            try:
                from quark_cli.history import record as history_record
                new_eps = result.get("new_episodes", [])
                if new_eps:
                    ep_str = ", ".join("E{:02d}".format(ep["episode"]) for ep in new_eps)
                    summary = "新增 {} 集: {}".format(len(new_eps), ep_str)
                    status = "success"
                elif result.get("error"):
                    summary = "检查异常: {}".format(result["error"][:100])
                    status = "error"
                else:
                    summary = "无新集数"
                    status = "success"
                history_record(
                    record_type="subscribe",
                    name=name,
                    status=status,
                    summary=summary,
                    detail=result,
                    duration=round(duration, 2),
                    config_path=self.config_path,
                )
            except Exception:
                logger.debug("写入订阅历史失败", exc_info=True)

            new_eps = result.get("new_episodes", [])
            if new_eps and sub.get("bot_notify", True):
                try:
                    from quark_cli.scheduler import send_bot_notify
                    notify_content = format_subscribe_notify(sub, result)
                    if notify_content:
                        send_bot_notify(
                            self.config_path,
                            {"_custom_content": notify_content},
                        )
                except Exception:
                    logger.debug("订阅通知发送失败", exc_info=True)

            logger.info("订阅检查完成: %s (新增 %d 集, %.1fs)",
                        name, len(result.get("new_episodes", [])), duration)

        except Exception:
            logger.exception("订阅检查异常: %s", name)
            self._results[name] = {
                "name": name,
                "error": "执行异常",
                "new_episodes": [],
            }

    def get_status(self):
        subs = []
        try:
            from quark_cli.config import ConfigManager
            cfg = ConfigManager(self.config_path)
            cfg.load()
            all_subs = cfg.data.get("subscriptions", [])
        except Exception:
            all_subs = []

        for sub in all_subs:
            sub = _merge_sub_defaults(sub)
            name = sub["name"]
            subs.append({
                "name": name,
                "keyword": sub.get("keyword") or name,
                "season": sub["season"],
                "next_episode": sub["next_episode"],
                "last_episode": sub.get("last_episode", 0),
                "max_episode": sub.get("max_episode"),
                "quality": sub.get("quality", ""),
                "save_path": sub.get("save_path", ""),
                "interval_minutes": sub.get("interval_minutes", 240),
                "enabled": sub.get("enabled", True),
                "finished": sub.get("finished", False),
                "miss_count": sub.get("miss_count", 0),
                "last_check": sub.get("last_check"),
                "episodes_found": sub.get("episodes_found", []),
                "running": name in self._task_threads and self._task_threads[name].is_alive(),
                "last_result": self._results.get(name),
            })

        return {
            "running": self._running,
            "subscriptions": subs,
        }

    def trigger_check(self, sub_name):
        """手动触发检查"""
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        all_subs = cfg.data.get("subscriptions", [])
        for sub in all_subs:
            sub = _merge_sub_defaults(sub)
            if sub["name"] == sub_name:
                if sub_name in self._task_threads and self._task_threads[sub_name].is_alive():
                    return {"error": "正在检查中"}
                self._last_check[sub_name] = datetime.now()
                t = threading.Thread(
                    target=self._execute_check, args=(sub,), daemon=True
                )
                self._task_threads[sub_name] = t
                t.start()
                return {"status": "started", "name": sub_name}
        return {"error": "未找到订阅: {}".format(sub_name)}


# ── 全局单例 ──

_sub_scheduler_instance = None


def get_subscribe_scheduler(config_path=None):
    global _sub_scheduler_instance
    if _sub_scheduler_instance is None:
        _sub_scheduler_instance = SubscribeScheduler(config_path)
    return _sub_scheduler_instance


def try_start_subscribe_scheduler(config_path=None):
    """尝试启动订阅调度器, 无订阅则跳过"""
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path)
    cfg.load()
    subs = cfg.data.get("subscriptions", [])
    active = [s for s in subs if s.get("enabled", True) and not s.get("finished", False)]
    if not active:
        logger.info("订阅追剧: 无活跃订阅, 跳过")
        return None
    scheduler = get_subscribe_scheduler(config_path)
    scheduler.start()
    return scheduler
