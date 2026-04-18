"""
定时任务调度器 — 自动发现 + 搜索 + 转存

功能:
  - 从 TMDB 发现页随机挑选影视
  - 通过媒体库查重，已有则跳过
  - 自动搜索网盘资源 → 转存
  - 飞书机器人通知转存结果
  - 支持多个定时任务，各自独立配置

任务配置 (config.json → scheduler.tasks[]):
  {
    "name": "每日随机电影",
    "enabled": true,
    "cron": "0 3 * * *",           # cron 表达式 (或 interval_minutes)
    "interval_minutes": 360,        # 简单间隔 (分钟)，与 cron 二选一
    "media_type": "movie",          # movie / tv
    "count": 3,                     # 每次挑选数量
    "filters": {
      "min_rating": 7.0,
      "genre": "科幻",
      "year": 2024,
      "country": "US"
    },
    "save_base_path": "/媒体",
    "check_media_lib": true,        # 是否媒体库查重
    "bot_notify": true,             # 是否飞书通知
    "notify_open_id": ""            # 通知人 open_id (空=使用全局配置)
  }
"""

import logging
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quark_cli.scheduler")


# ── 任务配置默认值 ──

DEFAULT_TASK = {
    "name": "自动发现",
    "enabled": True,
    "interval_minutes": 360,
    "media_type": "movie",
    "count": 3,
    "filters": {},
    "save_base_path": "/媒体",
    "check_media_lib": True,
    "bot_notify": True,
    "notify_open_id": "",
}


def _merge_defaults(task):
    """填充默认值"""
    merged = dict(DEFAULT_TASK)
    merged.update(task)
    return merged


# ── Cron 简易解析 ──

def _parse_interval(task):
    """从任务配置解析执行间隔 (秒)"""
    if task.get("interval_minutes"):
        return int(task["interval_minutes"]) * 60

    # 简易 cron: 只支持 "分 时 * * *" 形式 → 算作每日定时
    cron = task.get("cron", "")
    if cron:
        parts = cron.strip().split()
        if len(parts) >= 2:
            try:
                minute = int(parts[0])
                hour = int(parts[1])
                now = datetime.now()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return max(int((target - now).total_seconds()), 60)
            except (ValueError, IndexError):
                pass

    # 默认 6 小时
    return 360 * 60


# ── 单次任务执行 ──

def run_discover_task(task_config, config_path=None):
    """
    执行一次「自动发现」任务。

    流程:
      1. TMDB discover 随机页获取候选列表
      2. 按 count 挑选
      3. 媒体库查重 (可选)
      4. 逐个自动搜索+转存
      5. 收集结果

    Returns:
        dict: {
            "task_name": str,
            "discovered": int,
            "skipped_existing": int,
            "attempted": int,
            "saved": [{"title", "year", "save_path", "saved_count"}],
            "failed": [{"title", "year", "error"}],
            "timestamp": str,
        }
    """
    from quark_cli.config import ConfigManager

    task = _merge_defaults(task_config)
    cfg = ConfigManager(config_path)
    cfg.load()

    result = {
        "task_name": task["name"],
        "discovered": 0,
        "skipped_existing": 0,
        "attempted": 0,
        "saved": [],
        "failed": [],
        "timestamp": datetime.now().isoformat(),
    }

    # ── Step 1: TMDB 发现 ──
    try:
        from quark_cli.media.discovery.tmdb import TmdbSource

        disc_cfg = cfg.data.get("media", {}).get("discovery", {})
        tmdb_key = disc_cfg.get("tmdb_api_key", "")
        if not tmdb_key:
            result["error"] = "TMDB API Key 未配置"
            return result

        tmdb = TmdbSource(
            api_key=tmdb_key,
            language=disc_cfg.get("language", "zh-CN"),
            region=disc_cfg.get("region", "CN"),
        )
        media_type = task.get("media_type", "movie")
        filters = task.get("filters", {})
        count = task.get("count", 3)

        # 随机页数 (1~20)
        random_page = random.randint(1, 20)

        # 构建 discover 参数
        discover_kwargs = {
            "sort_by": "popularity.desc",
            "min_votes": 50,
        }
        if filters.get("min_rating"):
            discover_kwargs["min_rating"] = float(filters["min_rating"])
        if filters.get("genre"):
            genre_val = filters["genre"]
            # 尝试解析中文类型名
            if not str(genre_val).isdigit():
                try:
                    genre_ids = tmdb.resolve_genre_ids(
                        [g.strip() for g in str(genre_val).split(",")],
                        media_type,
                    )
                    if genre_ids:
                        discover_kwargs["genre"] = genre_ids
                except Exception:
                    pass
            else:
                discover_kwargs["genre"] = str(genre_val)
        if filters.get("year"):
            discover_kwargs["year"] = int(filters["year"])
        if filters.get("country"):
            discover_kwargs["country"] = filters["country"]

        discover_result = tmdb.discover(media_type, random_page, **discover_kwargs)
        candidates = discover_result.items
        result["discovered"] = len(candidates)

        if not candidates:
            result["error"] = "TMDB 未返回结果 (page={})".format(random_page)
            return result

        # 随机打乱后取 count 个
        random.shuffle(candidates)
        selected = candidates[:count]

    except Exception as e:
        result["error"] = "TMDB 发现失败: {}".format(str(e))
        logger.exception("TMDB discover error")
        return result

    # ── Step 2: 媒体库查重 ──
    media_provider = None
    if task.get("check_media_lib", True):
        try:
            from quark_cli.media.registry import create_provider
            from quark_cli.media.fnos.config import FnosConfig
            media_cfg = cfg.data.get("media", {})
            provider_name = media_cfg.get("provider", "fnos")
            if provider_name == "fnos":
                fnos_data = media_cfg.get("fnos", {})
                fnos_config = FnosConfig.from_dict(fnos_data)
                fnos_config = FnosConfig.from_env(fnos_config)
                fnos_config.validate()
                media_provider = create_provider("fnos", fnos_config)
        except Exception:
            logger.debug("媒体库不可用，跳过查重")

    # ── Step 3: 逐个搜索+转存 ──
    try:
        from quark_cli.api import QuarkAPI
        from quark_cli.search import PanSearch
        from quark_cli.media.discovery.naming import suggest_search_keywords, suggest_save_path

        cookies = cfg.get_cookies()
        if not cookies:
            result["error"] = "未配置 Cookie"
            return result

        client = QuarkAPI(cookies[0])
        if not client.init():
            result["error"] = "Cookie 失效"
            return result

        searcher = PanSearch(cfg)
        base_path = task.get("save_base_path", "/媒体")

    except Exception as e:
        result["error"] = "初始化失败: {}".format(str(e))
        return result

    for item in selected:
        title = item.title
        year = item.year

        # 媒体库查重 (仅用纯标题搜索，不带年份括号)
        if media_provider:
            try:
                # 搜索关键词只用标题，不加年份/括号
                search_keyword = title.strip()
                search_result = media_provider.search_items(keyword=search_keyword, page=1, page_size=10)
                found_existing = False
                if search_result.items:
                    for existing in search_result.items:
                        ex_title = (existing.title or "").strip()
                        # 标题模糊匹配 + 年份容差
                        if ex_title and (
                            title.lower() in ex_title.lower()
                            or ex_title.lower() in title.lower()
                        ):
                            year_int = int(year) if year and str(year).isdigit() else 0
                            ex_year = existing.year if hasattr(existing, "year") and existing.year else 0
                            if not year_int or not ex_year or abs(int(ex_year) - year_int) <= 1:
                                result["skipped_existing"] += 1
                                logger.info("跳过已有: %s (%s) — 媒体库已存在: %s", title, year, ex_title)
                                found_existing = True
                                break
                if found_existing:
                    continue
            except Exception as e:
                logger.debug("媒体库查重异常: %s", e)

        result["attempted"] += 1

        # 获取详情 + 搜索关键词
        try:
            detail_item = tmdb.get_detail(item.source_id, media_type)
            if detail_item.genres and isinstance(detail_item.genres[0], int):
                try:
                    detail_item.genres = tmdb.resolve_genre_names(detail_item.genres, media_type)
                except Exception:
                    pass

            keywords = suggest_search_keywords(detail_item)
            paths = suggest_save_path(detail_item, base_path=base_path)
            save_path = paths[0]["path"] if paths else "{}/{}".format(base_path, title)

        except Exception:
            keywords = [title]
            if year:
                keywords.append("{} {}".format(title, year))
            save_path = "{}/{}".format(base_path, title)

        # 自动转存
        try:
            from quark_cli.media.autosave import auto_save_pipeline

            save_result = auto_save_pipeline(
                quark_client=client,
                search_engine=searcher,
                keywords=keywords,
                save_path=save_path,
                max_attempts=5,
                media_title=title,
                media_year=int(year) if year else None,
                media_type=media_type,
            )

            if save_result.get("success"):
                result["saved"].append({
                    "title": title,
                    "year": year,
                    "tmdb_id": item.source_id,
                    "save_path": save_path,
                    "saved_count": save_result.get("saved_count", 0),
                    "saved_from": save_result.get("saved_from", ""),
                })
                logger.info("转存成功: %s (%s) → %s", title, year, save_path)
            else:
                result["failed"].append({
                    "title": title,
                    "year": year,
                    "tmdb_id": item.source_id,
                    "error": save_result.get("error", "未知错误"),
                })
                logger.info("转存失败: %s (%s) - %s", title, year, save_result.get("error"))

        except Exception as e:
            result["failed"].append({
                "title": title,
                "year": year,
                "error": str(e),
            })
            logger.exception("Auto-save error for %s", title)

    return result


# ── 飞书通知 ──

def format_notify_text(result):
    """将任务结果格式化为飞书 post 消息"""
    lines = []

    task_name = result.get("task_name", "自动发现")
    saved = result.get("saved", [])
    failed = result.get("failed", [])
    skipped = result.get("skipped_existing", 0)

    # 标题行
    if saved:
        lines.append([{"tag": "text", "text": "✅ {} 完成".format(task_name)}])
    elif result.get("error"):
        lines.append([{"tag": "text", "text": "❌ {} 失败: {}".format(task_name, result["error"])}])
        return {"zh_cn": {"title": "📺 {}".format(task_name), "content": lines}}
    else:
        lines.append([{"tag": "text", "text": "⚠️ {} 完成 (无新增)".format(task_name)}])

    # 统计
    stats_parts = []
    if saved:
        stats_parts.append("转存 {} 部".format(len(saved)))
    if failed:
        stats_parts.append("失败 {} 部".format(len(failed)))
    if skipped:
        stats_parts.append("已有 {} 部".format(skipped))
    if stats_parts:
        lines.append([{"tag": "text", "text": " · ".join(stats_parts)}])

    # 成功列表
    for s in saved:
        year_str = " ({})".format(s["year"]) if s.get("year") else ""
        lines.append([
            {"tag": "text", "text": "  ✅ {}{}".format(s["title"], year_str)},
        ])
        lines.append([
            {"tag": "text", "text": "      → {} ({} 个文件)".format(
                s.get("save_path", ""), s.get("saved_count", 0)
            )},
        ])

    # 失败列表
    for f in failed:
        year_str = " ({})".format(f["year"]) if f.get("year") else ""
        lines.append([
            {"tag": "text", "text": "  ❌ {}{}: {}".format(
                f["title"], year_str, f.get("error", "")
            )},
        ])

    title = "📺 {}".format(task_name)
    return {"zh_cn": {"title": title, "content": lines}}


def _get_tenant_token(app_id, app_secret, api_base="https://open.feishu.cn"):
    """获取 tenant_access_token"""
    import requests
    url = "{}/open-apis/auth/v3/tenant_access_token/internal".format(api_base)
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    data = resp.json()
    if data.get("code") == 0 and data.get("tenant_access_token"):
        return data["tenant_access_token"]
    logger.error("获取 tenant_access_token 失败: %s", data.get("msg", ""))
    return None


def send_bot_notify(config_path, result, notify_open_id=""):
    """
    通过飞书 API 发送通知 (私聊方式, 不依赖 bot 进程)

    发送方式: 用 tenant_access_token + open_id 向指定用户私聊
    消息格式: 富文本 post
    """
    import os
    import json
    import requests
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()

    # 读取 bot 配置 — 兼容 bot.feishu.xxx 和 bot.xxx
    bot_data = cfg.data.get("bot", {})
    bot_cfg = bot_data.get("feishu", bot_data)

    app_id = bot_cfg.get("app_id") or os.environ.get("FEISHU_APP_ID", "")
    app_secret = bot_cfg.get("app_secret") or os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        logger.info("飞书 Bot 未配置 app_id/app_secret，跳过通知")
        return False

    # 确定通知人 — 优先任务级 → 全局配置级
    open_id = (
        notify_open_id
        or bot_cfg.get("notify_open_id", "")
        or os.environ.get("FEISHU_NOTIFY_OPEN_ID", "")
    )
    if not open_id:
        logger.info("未配置通知人 open_id (bot.feishu.notify_open_id)，跳过通知")
        return False

    # API 域名: 支持内网 (bytedance) 和外网 (feishu)
    api_base = bot_cfg.get("api_base", "") or os.environ.get("FEISHU_API_BASE", "")
    if not api_base:
        api_base = "https://open.feishu.cn"

    # Step 1: 获取 tenant_access_token
    token = _get_tenant_token(app_id, app_secret, api_base)
    if not token:
        return False

    # Step 2: 发送消息
    try:
        content = format_notify_text(result)
        msg_content = json.dumps(content, ensure_ascii=False)

        url = "{}/open-apis/im/v1/messages?receive_id_type=open_id".format(api_base)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(token),
        }
        payload = {
            "receive_id": open_id,
            "msg_type": "post",
            "content": msg_content,
        }

        logger.info("发送飞书通知 → open_id=%s", open_id)
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        data = resp.json()

        if data.get("code") == 0:
            logger.info("飞书通知发送成功")
            return True
        else:
            logger.error("飞书通知发送失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return False

    except Exception as e:
        logger.exception("发送飞书通知异常: %s", e)
        return False


# ── 调度器主类 ──

class AutoDiscoverScheduler:
    """定时任务调度器 (后台守护线程)"""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self._running = False
        self._thread = None
        self._task_threads = {}  # task_name → thread
        self._last_run = {}  # task_name → datetime
        self._results = {}  # task_name → last result

    def start(self):
        """启动调度器 (非阻塞)"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("定时任务调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        logger.info("定时任务调度器已停止")

    def _load_tasks(self):
        """从配置读取任务列表"""
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        tasks = cfg.data.get("scheduler", {}).get("tasks", [])
        return [_merge_defaults(t) for t in tasks if t.get("enabled", True)]

    def _loop(self):
        """主调度循环"""
        # 启动后等待 30 秒再开始第一轮，避免与 serve 启动冲突
        time.sleep(30)

        while self._running:
            try:
                tasks = self._load_tasks()
                now = datetime.now()

                for task in tasks:
                    name = task["name"]
                    interval = _parse_interval(task)
                    last = self._last_run.get(name)

                    if last and (now - last).total_seconds() < interval:
                        continue

                    # 避免重复执行
                    if name in self._task_threads and self._task_threads[name].is_alive():
                        continue

                    logger.info("开始执行定时任务: %s", name)
                    self._last_run[name] = now
                    t = threading.Thread(
                        target=self._execute_task, args=(task,), daemon=True
                    )
                    self._task_threads[name] = t
                    t.start()

            except Exception:
                logger.exception("调度循环异常")

            # 每 60 秒检查一次
            time.sleep(60)

    def _execute_task(self, task):
        """执行单个任务"""
        name = task["name"]
        try:
            result = run_discover_task(task, self.config_path)
            self._results[name] = result

            # 飞书通知
            if task.get("bot_notify", True):
                # 只在有结果时通知 (有转存或有失败)
                if result.get("saved") or result.get("failed") or result.get("error"):
                    send_bot_notify(
                        self.config_path, result,
                        notify_open_id=task.get("notify_open_id", ""),
                    )

            logger.info("定时任务完成: %s (saved=%d, failed=%d)",
                        name, len(result.get("saved", [])), len(result.get("failed", [])))

            # 写入历史记录
            try:
                from quark_cli.history import record as history_record
                saved_count = len(result.get("saved", []))
                failed_count = len(result.get("failed", []))
                h_status = "success" if saved_count > 0 and failed_count == 0 else (
                    "partial" if saved_count > 0 else ("error" if failed_count > 0 else "success"))
                history_record(
                    record_type="task",
                    name=name,
                    status=h_status,
                    summary="转存 {} / 失败 {} / 跳过 {}".format(
                        saved_count, failed_count, len(result.get("skipped", []))),
                    detail=result,
                    config_path=self.config_path,
                )
            except Exception:
                logger.debug("写入任务历史失败", exc_info=True)

            # 同步到本地 NAS (可选)
            if result.get("saved") and task.get("sync", {}).get("enabled", False):
                self._run_sync_after_save(task, result)

        except Exception as exc:
            logger.exception("定时任务执行异常: %s", name)
            self._results[name] = {
                "task_name": name,
                "error": "执行异常",
                "timestamp": datetime.now().isoformat(),
            }
            try:
                from quark_cli.history import record as history_record
                history_record(
                    record_type="task",
                    name=name,
                    status="error",
                    summary="执行异常: {}".format(str(exc)[:200]),
                    config_path=self.config_path,
                )
            except Exception:
                pass

    def _run_sync_after_save(self, task, save_result):
        """转存成功后自动同步到本地 NAS"""
        name = task["name"]
        try:
            from quark_cli.config import ConfigManager
            from quark_cli.media.sync import sync_from_config

            cfg = ConfigManager(self.config_path)
            cfg.load()

            logger.info("开始同步到本地: %s", name)
            sync_progress = sync_from_config(
                config_data=cfg.data,
                task_config=task,
            )

            if sync_progress.status == "done":
                logger.info(
                    "同步完成: %s — 拷贝 %d / 跳过 %d / 删除 %d",
                    name,
                    sync_progress.copied_files,
                    sync_progress.skipped_files,
                    sync_progress.deleted_files,
                )
                # 追加同步信息到结果
                save_result["sync"] = {
                    "status": "done",
                    "copied": sync_progress.copied_files,
                    "skipped": sync_progress.skipped_files,
                    "deleted": sync_progress.deleted_files,
                }
            else:
                logger.warning("同步异常: %s — %s", name, sync_progress.errors)
                save_result["sync"] = {
                    "status": sync_progress.status,
                    "errors": sync_progress.errors,
                }

        except Exception as e:
            logger.exception("同步到本地失败: %s", name)
            save_result["sync"] = {"status": "error", "error": str(e)}

    def get_status(self):
        """获取调度器状态"""
        tasks = []
        try:
            all_tasks = self._load_tasks()
        except Exception:
            all_tasks = []

        for task in all_tasks:
            name = task["name"]
            tasks.append({
                "name": name,
                "enabled": task.get("enabled", True),
                "interval_minutes": task.get("interval_minutes", 360),
                "cron": task.get("cron", ""),
                "media_type": task.get("media_type", "movie"),
                "count": task.get("count", 3),
                "filters": task.get("filters", {}),
                "last_run": self._last_run.get(name, "").isoformat() if self._last_run.get(name) else None,
                "running": name in self._task_threads and self._task_threads[name].is_alive(),
                "last_result": self._results.get(name),
            })

        return {
            "running": self._running,
            "tasks": tasks,
        }

    def trigger_task(self, task_name):
        """手动触发指定任务"""
        tasks = self._load_tasks()
        for task in tasks:
            if task["name"] == task_name:
                if task_name in self._task_threads and self._task_threads[task_name].is_alive():
                    return {"error": "任务正在执行中"}
                self._last_run[task_name] = datetime.now()
                t = threading.Thread(
                    target=self._execute_task, args=(task,), daemon=True
                )
                self._task_threads[task_name] = t
                t.start()
                return {"status": "started", "task_name": task_name}
        return {"error": "未找到任务: {}".format(task_name)}


# ── 全局单例 ──

_scheduler_instance = None


def get_scheduler(config_path=None):
    """获取/创建调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutoDiscoverScheduler(config_path)
    return _scheduler_instance


def try_start_scheduler(config_path=None):
    """尝试启动调度器，无任务则跳过"""
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path)
    cfg.load()
    tasks = cfg.data.get("scheduler", {}).get("tasks", [])
    enabled = [t for t in tasks if t.get("enabled", True)]

    if not enabled:
        logger.info("定时任务: 无启用的任务，跳过")
        return None

    scheduler = get_scheduler(config_path)
    scheduler.start()
    return scheduler
