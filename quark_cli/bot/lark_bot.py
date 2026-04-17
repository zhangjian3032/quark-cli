"""
飞书/Lark 机器人 - 影视自动搜索转存

功能:
  - 通过飞书 WebSocket 长连接接收消息
  - 用户发送影视名称 → 自动查询 TMDB → 搜索网盘 → 转存 → 回复摘要
  - 支持单聊和群聊 (@机器人)

消息格式:
  - 直接发送影视名称，如: "流浪地球2"
  - 指定类型: "tv:三体"  或  "剧集:三体"
  - 指定年份: "流浪地球2 2023"
  - 预览模式 (不实际转存): "dry:流浪地球2"

依赖:
  pip install lark-oapi>=1.4.8
"""

import json
import re
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger("quark_cli.bot")


# ── 消息解析 ──

def parse_message(text):
    """
    解析用户消息，提取影视名称和选项。

    支持格式:
      - "流浪地球2"             → name=流浪地球2, type=movie
      - "tv:三体"               → name=三体, type=tv
      - "剧集:三体"             → name=三体, type=tv
      - "movie:流浪地球2"       → name=流浪地球2, type=movie
      - "dry:流浪地球2"         → name=流浪地球2, dry_run=True
      - "help" / "帮助"         → action=help

    Returns:
        dict: {
            "action": "search" | "help" | "status",
            "name": str,
            "media_type": "movie" | "tv",
            "year": int | None,
            "dry_run": bool,
        }
    """
    text = text.strip()

    # 帮助
    if text.lower() in ("help", "帮助", "?", "？", "/help"):
        return {"action": "help"}

    # 状态
    if text.lower() in ("status", "状态", "/status"):
        return {"action": "status"}

    # 解析前缀
    media_type = "movie"
    dry_run = False

    # 支持多个前缀组合: "dry:tv:三体"
    while ":" in text:
        prefix, rest = text.split(":", 1)
        prefix = prefix.strip().lower()
        if prefix in ("tv", "剧集", "剧", "电视剧"):
            media_type = "tv"
            text = rest.strip()
        elif prefix in ("movie", "电影", "片"):
            media_type = "movie"
            text = rest.strip()
        elif prefix in ("dry", "预览", "试"):
            dry_run = True
            text = rest.strip()
        else:
            # 不是已知前缀，可能是名称的一部分
            break

    # 尝试提取年份 (末尾 4 位数字)
    year = None
    m = re.search(r"\s+(\d{4})\s*$", text)
    if m:
        y = int(m.group(1))
        if 1900 <= y <= 2099:
            year = y
            text = text[: m.start()].strip()

    name = text.strip()
    if not name:
        return {"action": "help"}

    return {
        "action": "search",
        "name": name,
        "media_type": media_type,
        "year": year,
        "dry_run": dry_run,
    }


# ── 自动转存核心 ──

def run_auto_save(config_path, name, media_type="movie", year=None, dry_run=False, base_path="/媒体"):
    """
    执行自动搜索转存流程，返回结构化结果。

    Args:
        config_path: 配置文件路径
        name: 影视名称
        media_type: "movie" | "tv"
        year: 年份 (可选)
        dry_run: 是否仅预览

    Returns:
        dict: {
            "success": bool,
            "tmdb": dict | None,      # TMDB 元数据
            "keywords": list,          # 搜索关键词
            "save_path": str,          # 保存路径
            "candidates": list,        # 候选列表
            "saved_from": str,         # 成功转存的来源
            "saved_count": int,        # 转存文件数
            "attempts": int,           # 尝试次数
            "error": str,              # 错误信息
            "dry_run": bool,
        }
    """
    from quark_cli.config import ConfigManager
    from quark_cli.search import PanSearch
    from quark_cli.media.autosave import auto_save_pipeline, rank_results, filter_quark_links

    cfg = ConfigManager(config_path)
    cfg.load()

    result = {
        "success": False,
        "tmdb": None,
        "keywords": [],
        "save_path": "",
        "candidates": [],
        "saved_from": "",
        "saved_from_title": "",
        "saved_count": 0,
        "attempts": 0,
        "error": "",
        "dry_run": dry_run,
    }

    # ── TMDB 元数据 ──
    keywords = []
    save_path = None
    tmdb_info = None

    try:
        media_cfg = cfg.data.get("media", {})
        discovery_cfg = media_cfg.get("discovery", {})
        api_key = discovery_cfg.get("tmdb_api_key", "")

        if api_key:
            from quark_cli.media.discovery.tmdb import TmdbSource
            from quark_cli.media.discovery.naming import suggest_search_keywords, suggest_save_path

            language = discovery_cfg.get("language", "zh-CN")
            region = discovery_cfg.get("region", "CN")
            source = TmdbSource(api_key=api_key, language=language, region=region)

            search_result = source.search(name, media_type=media_type, page=1, year=year)
            # fallback 另一类型
            if not search_result.items:
                alt = "tv" if media_type == "movie" else "movie"
                search_result = source.search(name, media_type=alt, page=1, year=year)
                if search_result.items:
                    media_type = alt

            if search_result.items:
                first = search_result.items[0]
                detail = source.get_detail(first.source_id, media_type)

                if detail.genres and isinstance(detail.genres[0], int):
                    try:
                        detail.genres = source.resolve_genre_names(detail.genres, media_type)
                    except Exception:
                        pass

                keywords = suggest_search_keywords(detail)
                paths = suggest_save_path(detail, base_path=base_path)
                if paths:
                    save_path = paths[0]["path"]

                tmdb_info = {
                    "id": detail.source_id,
                    "title": detail.title,
                    "original_title": detail.original_title,
                    "year": detail.year,
                    "rating": detail.rating,
                    "genres": detail.genres if isinstance(detail.genres, list) else [],
                    "overview": (detail.overview or "")[:200],
                    "poster_url": source.get_poster_url(detail.poster_path) if detail.poster_path else "",
                }
                result["tmdb"] = tmdb_info
        else:
            logger.warning("TMDB API Key 未配置，跳过元数据查询")
    except Exception as e:
        logger.warning("TMDB 查询失败: %s", e)

    # fallback 关键词
    if not keywords:
        keywords = [name]
        if year:
            keywords.append("{} {}".format(name, year))

    # fallback 保存路径
    if not save_path:
        type_folder = "电影" if media_type == "movie" else "剧集"
        title_folder = "{} ({})".format(name, year) if year else name
        save_path = "/{}/{}/{}".format(base_path.strip("/"), type_folder, title_folder)

    result["keywords"] = keywords
    result["save_path"] = save_path

    # ── 搜索网盘资源 ──
    search_engine = PanSearch(config=cfg)
    all_results = []
    for kw in keywords:
        sr = search_engine.search_all(kw)
        if sr.get("success") and sr.get("results"):
            all_results.extend(sr["results"])

    # 去重
    seen = set()
    unique = []
    for r in all_results:
        u = r.get("url", "")
        if u not in seen:
            seen.add(u)
            unique.append(r)

    quark_results = filter_quark_links(unique)
    if not quark_results:
        result["error"] = "未搜索到夸克网盘链接 (共搜到 {} 条结果)".format(len(unique))
        return result

    ranked = rank_results(quark_results, keywords)
    candidates = ranked[:10]
    result["candidates"] = [
        {"title": c.get("title", ""), "url": c.get("url", ""), "score": c.get("score", 0)}
        for c in candidates
    ]

    # ── Dry run ──
    if dry_run:
        result["success"] = True
        result["dry_run"] = True
        return result

    # ── 转存 ──
    cookies = cfg.get_cookies()
    if not cookies:
        result["error"] = "夸克 Cookie 未配置"
        return result

    from quark_cli.api import QuarkAPI
    quark_client = QuarkAPI(cookies[0])
    account = quark_client.init()
    if not account:
        result["error"] = "夸克账号验证失败，Cookie 可能已过期"
        return result

    progress_events = []

    def on_progress(event, data):
        progress_events.append({"event": event, "data": data})

    pipeline_result = auto_save_pipeline(
        quark_client=quark_client,
        search_engine=search_engine,
        keywords=keywords,
        save_path=save_path,
        max_attempts=10,
        on_progress=on_progress,
    )

    result["attempts"] = pipeline_result.get("attempts", 0)
    if pipeline_result["success"]:
        result["success"] = True
        result["saved_from"] = pipeline_result.get("saved_from", "")
        result["saved_from_title"] = pipeline_result.get("saved_from_title", "")
        result["saved_count"] = pipeline_result.get("saved_count", 0)
    else:
        result["error"] = pipeline_result.get("error", "转存失败")

    return result


# ── 飞书消息格式化 ──

def format_reply_text(parsed, result):
    """
    将自动转存结果格式化为飞书富文本消息 (post 格式)。

    Returns:
        str: JSON content for Feishu message (msg_type="post")
    """
    title = "🎬 {} — {}".format(
        parsed.get("name", ""),
        "转存成功 ✅" if result["success"] and not result["dry_run"]
        else "预览完成 📋" if result["dry_run"]
        else "转存失败 ❌"
    )

    lines = []

    # TMDB 信息
    tmdb = result.get("tmdb")
    if tmdb:
        meta_line = []
        meta_line.append({"tag": "text", "text": "📌 "})
        meta_line.append({"tag": "text", "text": "{} ({})".format(tmdb["title"], tmdb.get("year", ""))})
        if tmdb.get("rating"):
            meta_line.append({"tag": "text", "text": "  ⭐{}".format(tmdb["rating"])})
        lines.append(meta_line)

        if tmdb.get("genres"):
            genre_str = " / ".join(tmdb["genres"][:4]) if isinstance(tmdb["genres"][0], str) else ""
            if genre_str:
                lines.append([{"tag": "text", "text": "🏷️ {}".format(genre_str)}])

        if tmdb.get("overview"):
            lines.append([{"tag": "text", "text": "📝 {}".format(tmdb["overview"][:120])}])

    lines.append([{"tag": "text", "text": ""}])  # 空行

    # 搜索信息
    lines.append([{"tag": "text", "text": "🔍 关键词: {}".format(" | ".join(result.get("keywords", [])))}])
    lines.append([{"tag": "text", "text": "📁 保存路径: {}".format(result.get("save_path", ""))}])

    # 候选数量
    candidates = result.get("candidates", [])
    if candidates:
        lines.append([{"tag": "text", "text": "📊 找到 {} 个候选链接".format(len(candidates))}])

    lines.append([{"tag": "text", "text": ""}])  # 空行

    # 结果
    if result["success"] and not result["dry_run"]:
        lines.append([
            {"tag": "text", "text": "✅ 转存成功!"},
        ])
        lines.append([{"tag": "text", "text": "📦 文件数: {}".format(result.get("saved_count", 0))}])
        lines.append([{"tag": "text", "text": "🔗 来源: {}".format(result.get("saved_from_title", "")[:60])}])
        lines.append([{"tag": "text", "text": "📂 已保存到: {}".format(result.get("save_path", ""))}])
        lines.append([{"tag": "text", "text": "🔄 尝试次数: {}".format(result.get("attempts", 0))}])
    elif result["dry_run"]:
        lines.append([{"tag": "text", "text": "📋 预览模式 (未实际转存)"}])
        if candidates:
            lines.append([{"tag": "text", "text": "🏆 最佳候选:"}])
            for i, c in enumerate(candidates[:3], 1):
                lines.append([{"tag": "text", "text": "  {}. [{}分] {}".format(
                    i, c.get("score", 0), c.get("title", "")[:50]
                )}])
    else:
        lines.append([
            {"tag": "text", "text": "❌ {}".format(result.get("error", "未知错误"))},
        ])

    # 时间戳
    lines.append([{"tag": "text", "text": ""}])
    lines.append([{"tag": "text", "text": "⏰ {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}])

    post = {
        "zh_cn": {
            "title": title,
            "content": lines,
        }
    }
    return json.dumps({"zh_cn": post["zh_cn"]})


def format_help_text():
    """格式化帮助消息"""
    content = {
        "zh_cn": {
            "title": "🎬 影视自动转存机器人 - 使用帮助",
            "content": [
                [{"tag": "text", "text": "发送影视名称，我会自动完成: TMDB 查询 → 搜索资源 → 转存到网盘"}],
                [{"tag": "text", "text": ""}],
                [{"tag": "text", "text": "📖 消息格式:"}],
                [{"tag": "text", "text": "  电影名称          直接发送，如: 流浪地球2"}],
                [{"tag": "text", "text": "  tv:剧集名         搜索剧集，如: tv:三体"}],
                [{"tag": "text", "text": "  名称 年份         指定年份，如: 沙丘 2024"}],
                [{"tag": "text", "text": "  dry:名称          仅预览不转存"}],
                [{"tag": "text", "text": ""}],
                [{"tag": "text", "text": "🔧 命令:"}],
                [{"tag": "text", "text": "  help / 帮助       显示此帮助"}],
                [{"tag": "text", "text": "  status / 状态     查看配置状态"}],
                [{"tag": "text", "text": ""}],
                [{"tag": "text", "text": "💡 示例:"}],
                [{"tag": "text", "text": "  流浪地球2"}],
                [{"tag": "text", "text": "  tv:三体"}],
                [{"tag": "text", "text": "  奥本海默 2023"}],
                [{"tag": "text", "text": "  dry:沙丘2"}],
            ],
        }
    }
    return json.dumps(content)


def format_status_text(config_path):
    """格式化状态消息"""
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()

    cookies = cfg.get_cookies()
    media_cfg = cfg.data.get("media", {})
    discovery_cfg = media_cfg.get("discovery", {})
    tmdb_key = discovery_cfg.get("tmdb_api_key", "")

    lines = [
        [{"tag": "text", "text": "🍪 夸克 Cookie: {}".format(
            "✅ 已配置 ({} 个)".format(len(cookies)) if cookies else "❌ 未配置"
        )}],
        [{"tag": "text", "text": "🎬 TMDB API Key: {}".format(
            "✅ 已配置 (***{})".format(tmdb_key[-6:]) if tmdb_key else "❌ 未配置"
        )}],
        [{"tag": "text", "text": "📂 基准路径: {}".format(
            discovery_cfg.get("base_path", "/媒体")
        )}],
        [{"tag": "text", "text": "🌍 语言/地区: {} / {}".format(
            discovery_cfg.get("language", "zh-CN"),
            discovery_cfg.get("region", "CN"),
        )}],
    ]

    content = {
        "zh_cn": {
            "title": "⚙️ 机器人配置状态",
            "content": lines,
        }
    }
    return json.dumps(content)


# ── 飞书机器人主类 ──

class QuarkLarkBot:
    """
    飞书机器人: 接收影视名称 → 自动搜索转存 → 回复摘要。

    使用 lark_oapi WebSocket 长连接模式。
    """

    def __init__(self, app_id, app_secret, config_path=None, base_path="/媒体"):
        self.app_id = app_id
        self.app_secret = app_secret
        self.config_path = config_path
        self.base_path = base_path

        # lazy import — 启动时才检查依赖
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )

        self._lark = lark
        self._CreateMessageRequest = CreateMessageRequest
        self._CreateMessageRequestBody = CreateMessageRequestBody
        self._ReplyMessageRequest = ReplyMessageRequest
        self._ReplyMessageRequestBody = ReplyMessageRequestBody

        # 创建 Lark Client
        self.client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

        # 注册事件处理
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message)
            .build()
        )

        self.ws_client = lark.ws.Client(
            app_id,
            app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

    def _on_message(self, data):
        """处理收到的消息"""
        try:
            msg = data.event.message
            sender = data.event.sender

            # 只处理文本消息
            if msg.message_type != "text":
                self._reply(data, "post", format_help_text())
                return

            # 解析消息内容
            content = json.loads(msg.content)
            text = content.get("text", "").strip()

            # 群聊中需要 @机器人，去除 @ 前缀
            if msg.chat_type == "group" and msg.mentions:
                for mention in msg.mentions:
                    text = text.replace("@_user_1", "").strip()
                    text = text.replace(mention.name, "").strip()

            if not text:
                self._reply(data, "post", format_help_text())
                return

            logger.info("收到消息: '%s' from %s (chat_type=%s)",
                        text, sender.sender_id.open_id, msg.chat_type)

            parsed = parse_message(text)

            if parsed["action"] == "help":
                self._reply(data, "post", format_help_text())
                return

            if parsed["action"] == "status":
                self._reply(data, "post", format_status_text(self.config_path))
                return

            # ── 自动转存 ──
            # 先发一个 "处理中" 的提示
            processing_text = json.dumps({"text": "🔍 正在为您搜索「{}」，请稍候...".format(parsed["name"])})
            self._reply(data, "text", processing_text)

            # 在后台线程中执行转存 (避免阻塞 WebSocket)
            thread = threading.Thread(
                target=self._do_auto_save,
                args=(data, parsed),
                daemon=True,
            )
            thread.start()

        except Exception as e:
            logger.exception("处理消息时出错: %s", e)
            try:
                error_text = json.dumps({"text": "❌ 处理出错: {}".format(str(e)[:200])})
                self._reply(data, "text", error_text)
            except Exception:
                pass

    def _do_auto_save(self, data, parsed):
        """在后台执行自动转存并回复结果"""
        try:
            result = run_auto_save(
                config_path=self.config_path,
                name=parsed["name"],
                media_type=parsed.get("media_type", "movie"),
                year=parsed.get("year"),
                dry_run=parsed.get("dry_run", False),
                base_path=self.base_path,
            )

            reply_content = format_reply_text(parsed, result)
            self._send_to_chat(data, "post", reply_content)

        except Exception as e:
            logger.exception("自动转存出错: %s", e)
            error_text = json.dumps({"text": "❌ 转存过程出错: {}".format(str(e)[:200])})
            self._send_to_chat(data, "text", error_text)

    def _reply(self, data, msg_type, content):
        """回复消息 (使用 reply API)"""
        msg_id = data.event.message.message_id

        request = (
            self._ReplyMessageRequest.builder()
            .message_id(msg_id)
            .request_body(
                self._ReplyMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )

        response = self.client.im.v1.message.reply(request)
        if not response.success():
            logger.error("回复消息失败: code=%s, msg=%s", response.code, response.msg)

    def _send_to_chat(self, data, msg_type, content):
        """发送消息到聊天 (使用 create API, 支持群聊和单聊)"""
        msg = data.event.message
        chat_type = msg.chat_type

        if chat_type == "group":
            receive_id_type = "chat_id"
            receive_id = msg.chat_id
        else:
            receive_id_type = "open_id"
            receive_id = data.event.sender.sender_id.open_id

        request = (
            self._CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                self._CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )

        response = self.client.im.v1.message.create(request)
        if not response.success():
            logger.error("发送消息失败: code=%s, msg=%s", response.code, response.msg)

    def start(self):
        """启动机器人 (阻塞)"""
        logger.info("飞书机器人启动中... (APP_ID=%s***)", self.app_id[:6] if len(self.app_id) > 6 else "***")
        self.ws_client.start()


def start_bot(config_path=None, app_id=None, app_secret=None, base_path="/媒体"):
    """
    便捷启动函数。

    优先使用参数，其次从配置文件读取，最后从环境变量读取。
    """
    import os
    from quark_cli.config import ConfigManager

    cfg = ConfigManager(config_path)
    cfg.load()
    bot_cfg = cfg.data.get("bot", {}).get("feishu", {})

    # 优先级: 参数 > 配置文件 > 环境变量
    app_id = app_id or bot_cfg.get("app_id") or os.environ.get("FEISHU_APP_ID", "")
    app_secret = app_secret or bot_cfg.get("app_secret") or os.environ.get("FEISHU_APP_SECRET", "")
    base_path = base_path or bot_cfg.get("base_path") or "/媒体"

    if not app_id or not app_secret:
        raise ValueError(
            "飞书机器人 APP_ID / APP_SECRET 未配置。\n"
            "请通过以下方式之一配置:\n"
            "  1. quark-cli bot --app-id <id> --app-secret <secret>\n"
            "  2. 配置文件: bot.feishu.app_id / bot.feishu.app_secret\n"
            "  3. 环境变量: FEISHU_APP_ID / FEISHU_APP_SECRET\n"
            "\n"
            "获取方式: https://open.feishu.cn/app → 创建应用 → 获取凭证"
        )

    bot = QuarkLarkBot(
        app_id=app_id,
        app_secret=app_secret,
        config_path=config_path,
        base_path=base_path,
    )
    bot.start()
