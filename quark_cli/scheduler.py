"""
定时任务调度器 — 自动发现 + 搜索 + 转存

功能:
  - 从 TMDB/豆瓣 发现页随机挑选影视
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
    "source": "tmdb",               # 数据源: tmdb / douban (默认 tmdb)
    "media_type": "movie",          # movie / tv
    "count": 3,                     # 每次挑选数量
    "filters": {
      "min_rating": 7.0,
      "genre": "科幻",
      "year": 2024,
      "country": "US",
      "tag": "热门"                  # 豆瓣专用: 标签
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
    "source": "tmdb",
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
    """从任务配置解析执行间隔 (秒)

    优先级: cron > interval_minutes > 默认 6 小时
    cron 模式使用固定 86400 秒间隔，由 _should_run_cron() 判断是否到达触发时间。
    """
    # cron 优先 — 每日定时任务
    cron = task.get("cron", "")
    if cron:
        # cron 模式: 返回固定的每日间隔，实际触发判断由 _should_run_cron 负责
        return 86400

    if task.get("interval_minutes"):
        return int(task["interval_minutes"]) * 60

    # 默认 6 小时
    return 360 * 60


def _should_run_cron(task, last_run):
    """判断 cron 任务是否应该执行

    仅支持 "分 时 * * *" 格式 (每日定时)。
    返回 True 如果当前已过触发时间且今天尚未执行。
    """
    cron = task.get("cron", "")
    if not cron:
        return True  # 非 cron 任务，由 interval 逻辑控制

    parts = cron.strip().split()
    if len(parts) < 2:
        return True

    try:
        minute = int(parts[0])
        hour = int(parts[1])
    except (ValueError, IndexError):
        return True

    now = datetime.now()
    today_target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 还没到今天的触发时间
    if now < today_target:
        return False

    # 已到触发时间 — 检查今天是否已执行过
    if last_run and last_run.date() == now.date() and last_run >= today_target:
        return False

    return True


# ── 创建数据源 ──


def _get_proxy(cfg, target):
    """从配置中获取 proxy URL"""
    from quark_cli.config import get_proxy_for
    return get_proxy_for(cfg.data, target)



def _create_discovery_source(task, cfg):
    """
    根据任务配置创建数据源实例。

    Args:
        task: 合并了默认值的任务配置 dict
        cfg: ConfigManager 实例

    Returns:
        (source, source_name) 或 (None, error_msg)
    """
    source_name = task.get("source", "tmdb")
    disc_cfg = cfg.data.get("media", {}).get("discovery", {})

    if source_name == "douban":
        from quark_cli.media.discovery.douban import DoubanSource
        proxy = _get_proxy(cfg, "douban")
        return DoubanSource(proxy=proxy), "douban"

    # 默认 tmdb
    from quark_cli.media.discovery.tmdb import TmdbSource
    tmdb_key = disc_cfg.get("tmdb_api_key", "")
    if not tmdb_key:
        # 回退到豆瓣
        logger.warning("TMDB API Key 未配置, 回退到豆瓣数据源")
        from quark_cli.media.discovery.douban import DoubanSource
        proxy = _get_proxy(cfg, "douban")
        return DoubanSource(proxy=proxy), "douban"

    proxy = _get_proxy(cfg, "tmdb")
    return TmdbSource(
        api_key=tmdb_key,
        language=disc_cfg.get("language", "zh-CN"),
        region=disc_cfg.get("region", "CN"),
        proxy=proxy,
    ), "tmdb"


# ── 单次任务执行 ──

def run_discover_task(task_config, config_path=None):
    """
    执行一次「自动发现」任务。

    流程:
      1. 从数据源 (TMDB/豆瓣) discover 随机页获取候选列表
      2. 按 count 挑选
      3. 媒体库查重 (可选)
      4. 逐个自动搜索+转存
      5. 收集结果

    Returns:
        dict: {
            "task_name": str,
            "source": str,
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
        "source": task.get("source", "tmdb"),
        "discovered": 0,
        "skipped_existing": 0,
        "attempted": 0,
        "saved": [],
        "failed": [],
        "timestamp": datetime.now().isoformat(),
    }

    # ── Step 1: 创建数据源并发现 ──
    try:
        source, actual_source = _create_discovery_source(task, cfg)
        result["source"] = actual_source

        media_type = task.get("media_type", "movie")
        filters = task.get("filters", {})
        count = task.get("count", 3)

        # 随机页数 (1~20)
        random_page = random.randint(1, 20)

        if actual_source == "douban":
            # ── 豆瓣发现 ──
            discover_kwargs = {}
            if filters.get("min_rating"):
                discover_kwargs["min_rating"] = float(filters["min_rating"])
            if filters.get("tag"):
                discover_kwargs["tag"] = filters["tag"]
            elif filters.get("genre"):
                # genre 直接用作 tag (豆瓣支持中文类型名)
                discover_kwargs["tag"] = str(filters["genre"])
            elif filters.get("country"):
                country_tag = {
                    "CN": "华语", "US": "欧美", "JP": "日本", "KR": "韩国",
                }.get(str(filters["country"]).upper(), str(filters["country"]))
                discover_kwargs["tag"] = country_tag

            if filters.get("sort"):
                discover_kwargs["sort"] = filters["sort"]

            discover_result = source.discover(media_type, random_page, **discover_kwargs)

        else:
            # ── TMDB 发现 ──
            discover_kwargs = {
                "sort_by": "popularity.desc",
                "min_votes": 50,
            }
            if filters.get("min_rating"):
                discover_kwargs["min_rating"] = float(filters["min_rating"])
            if filters.get("genre"):
                genre_val = filters["genre"]
                if not str(genre_val).isdigit():
                    try:
                        genre_ids = source.resolve_genre_ids(
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

            discover_result = source.discover(media_type, random_page, **discover_kwargs)

        candidates = discover_result.items

        # 页码超出 total_pages 时, 在有效范围内重随机
        if not candidates and random_page > 1:
            total_pages = getattr(discover_result, "total_pages", 1) or 1
            fallback_page = random.randint(1, max(1, min(total_pages, 20)))
            logger.info("page=%d 无结果 (total_pages=%d), fallback page=%d",
                        random_page, total_pages, fallback_page)
            random_page = fallback_page
            if actual_source == "douban":
                discover_result = source.discover(media_type, fallback_page, **discover_kwargs)
            else:
                discover_result = source.discover(media_type, fallback_page, **discover_kwargs)
            candidates = discover_result.items

        result["discovered"] = len(candidates)

        if not candidates:
            result["error"] = "数据源未返回结果 (source={}, page={})".format(actual_source, random_page)
            return result

        # 随机打乱后取 count 个
        random.shuffle(candidates)
        selected = candidates[:count]

    except Exception as e:
        result["error"] = "发现失败 ({}): {}".format(task.get("source", "tmdb"), str(e))
        logger.exception("Discover error")
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

        # 媒体库查重
        if media_provider:
            try:
                search_keyword = title.strip()
                search_result = media_provider.search_items(keyword=search_keyword, page=1, page_size=10)
                found_existing = False
                if search_result.items:
                    for existing in search_result.items:
                        ex_title = (existing.title or "").strip()
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
            detail_item = source.get_detail(item.source_id, media_type)
            if detail_item.genres and isinstance(detail_item.genres[0], int):
                try:
                    if hasattr(source, "resolve_genre_names"):
                        detail_item.genres = source.resolve_genre_names(detail_item.genres, media_type)
                except Exception:
                    pass

            keywords = suggest_search_keywords(detail_item)
            # 读取平铺路径配置，确保定时任务也尊重用户的 flat_save_path 设置
            flat_mode = cfg.data.get("autosave", {}).get("flat_save_path", False)
            paths = suggest_save_path(detail_item, base_path=base_path, flat=flat_mode)
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
                    "source_id": item.source_id,
                    "source": actual_source,
                    "save_path": save_path,
                    "saved_count": save_result.get("saved_count", 0),
                    "saved_from": save_result.get("saved_from", ""),
                })
                logger.info("转存成功: %s (%s) → %s", title, year, save_path)
            else:
                result["failed"].append({
                    "title": title,
                    "year": year,
                    "source_id": item.source_id,
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
    source = result.get("source", "")
    saved = result.get("saved", [])
    failed = result.get("failed", [])
    skipped = result.get("skipped_existing", 0)

    # 标题行
    source_label = " [{}]".format(source.upper()) if source else ""
    if saved:
        lines.append([{"tag": "text", "text": "✅ {}{} 完成".format(task_name, source_label)}])
    elif result.get("error"):
        lines.append([{"tag": "text", "text": "❌ {}{} 失败: {}".format(task_name, source_label, result["error"])}])
        return {"zh_cn": {"title": "📺 {}".format(task_name), "content": lines}}
    else:
        lines.append([{"tag": "text", "text": "⚠️ {}{} 完成 (无新增)".format(task_name, source_label)}])

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
        # 显示具体文件名 (最多 8 个, 避免通知过长)
        filenames = s.get("filenames", [])
        if filenames:
            shown = filenames[:8]
            for fn in shown:
                lines.append([{"tag": "text", "text": "        📄 {}".format(fn)}])
            if len(filenames) > 8:
                lines.append([{"tag": "text", "text": "        ... 共 {} 个文件".format(len(filenames))}])

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
    """
    import os
    import json
    import requests
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()

    bot_data = cfg.data.get("bot", {})
    bot_cfg = bot_data.get("feishu", bot_data)

    app_id = bot_cfg.get("app_id") or os.environ.get("FEISHU_APP_ID", "")
    app_secret = bot_cfg.get("app_secret") or os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        logger.info("飞书 Bot 未配置 app_id/app_secret，跳过通知")
        return False

    open_id = (
        notify_open_id
        or bot_cfg.get("notify_open_id", "")
        or os.environ.get("FEISHU_NOTIFY_OPEN_ID", "")
    )
    if not open_id:
        logger.info("未配置通知人 open_id (bot.feishu.notify_open_id)，跳过通知")
        return False

    api_base = bot_cfg.get("api_base", "") or os.environ.get("FEISHU_API_BASE", "")
    if not api_base:
        api_base = "https://open.feishu.cn"

    token = _get_tenant_token(app_id, app_secret, api_base)
    if not token:
        return False

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
        self._task_threads = {}
        self._last_run = {}
        self._results = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("定时任务调度器已启动")

    def stop(self):
        self._running = False
        logger.info("定时任务调度器已停止")

    def _load_tasks(self):
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        tasks = cfg.data.get("scheduler", {}).get("tasks", [])
        return [_merge_defaults(t) for t in tasks if t.get("enabled", True)]

    def _loop(self):
        time.sleep(30)

        while self._running:
            try:
                tasks = self._load_tasks()
                now = datetime.now()

                for task in tasks:
                    name = task["name"]
                    interval = _parse_interval(task)
                    last = self._last_run.get(name)

                    # cron 模式: 使用精确的时间窗口判断
                    if task.get("cron"):
                        if not _should_run_cron(task, last):
                            continue
                    elif last and (now - last).total_seconds() < interval:
                        continue

                    if name in self._task_threads and self._task_threads[name].is_alive():
                        continue

                    logger.info("开始执行定时任务: %s (source=%s)", name, task.get("source", "tmdb"))
                    self._last_run[name] = now
                    t = threading.Thread(
                        target=self._execute_task, args=(task,), daemon=True
                    )
                    self._task_threads[name] = t
                    t.start()

            except Exception:
                logger.exception("调度循环异常")

            time.sleep(60)

    def _execute_task(self, task):
        name = task["name"]
        try:
            result = run_discover_task(task, self.config_path)
            self._results[name] = result

            if task.get("bot_notify", True):
                if result.get("saved") or result.get("failed") or result.get("error"):
                    send_bot_notify(
                        self.config_path, result,
                        notify_open_id=task.get("notify_open_id", ""),
                    )

            logger.info("定时任务完成: %s (saved=%d, failed=%d)",
                        name, len(result.get("saved", [])), len(result.get("failed", [])))

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
                "source": task.get("source", "tmdb"),
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
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutoDiscoverScheduler(config_path)
    return _scheduler_instance


def try_start_scheduler(config_path=None):
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
