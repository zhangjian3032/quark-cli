"""
RSS 匹配后动作执行

支持的动作:
  - auto_save: 提取夸克链接 → auto_save_pipeline 转存
  - notify:    飞书 Bot 通知
  - log:       仅记录到历史
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("quark_cli.rss.actions")


def execute_action(match_result, config_path=None):
    """
    根据 MatchResult.action 执行对应动作.

    Args:
        match_result: MatchResult
        config_path: 配置文件路径

    Returns:
        dict: 执行结果
    """
    action = match_result.action
    item = match_result.item
    rule = match_result.rule

    result = {
        "action": action,
        "item_guid": item.guid,
        "item_title": item.title,
        "rule_name": rule.get("name", ""),
        "success": False,
        "detail": {},
    }

    t0 = time.time()

    try:
        if action == "auto_save":
            result["detail"] = _action_auto_save(match_result, config_path)
            result["success"] = result["detail"].get("success", False)
        elif action == "notify":
            result["detail"] = _action_notify(match_result, config_path)
            result["success"] = True
        elif action == "log":
            result["detail"] = {"message": "已记录"}
            result["success"] = True
        else:
            result["detail"] = {"error": "未知动作: {}".format(action)}
    except Exception as e:
        logger.exception("动作执行失败: %s [%s]", item.title, action)
        result["detail"] = {"error": str(e)}

    result["duration"] = round(time.time() - t0, 2)

    # 写入历史记录
    try:
        _record_history(match_result, result, config_path)
    except Exception:
        logger.debug("写入 RSS 历史记录失败", exc_info=True)

    return result


def _action_auto_save(match_result, config_path):
    """自动转存动作"""
    from quark_cli.config import ConfigManager
    from quark_cli.api import QuarkAPI
    from quark_cli.search import PanSearch
    from quark_cli.media.autosave import auto_save_pipeline

    target_links = match_result.get_target_links()
    if not target_links:
        return {"success": False, "error": "无可用链接 (类型: {})".format(match_result.link_type)}

    save_path = match_result.save_path
    if not save_path:
        save_path = "/RSS/{}".format(match_result.rule.get("name", "default"))

    item = match_result.item
    keywords = [item.title]

    cfg = ConfigManager(config_path)
    cfg.load()

    cookies = cfg.get_cookies()
    if not cookies:
        return {"success": False, "error": "未配置夸克 Cookie"}

    client = QuarkAPI(cookies[0])
    if not client.init():
        return {"success": False, "error": "夸克 Cookie 无效或过期"}

    searcher = PanSearch(cfg)

    # 如果有夸克直链, 直接尝试转存 (不走搜索)
    quark_links = match_result.links.get("quark", [])
    if quark_links:
        for link in quark_links[:3]:
            try:
                from quark_cli.media.autosave import _try_save_one
                save_result = _try_save_one(
                    client, link, save_path,
                    media_title=item.title,
                )
                if save_result.get("success"):
                    return {
                        "success": True,
                        "method": "direct_link",
                        "url": link,
                        "saved_count": save_result.get("saved_count", 0),
                        "save_path": save_path,
                    }
            except Exception as e:
                logger.debug("直链转存失败 [%s]: %s", link, e)
                continue

    # 回退到 auto_save_pipeline (搜索转存)
    pipeline_result = auto_save_pipeline(
        quark_client=client,
        search_engine=searcher,
        keywords=keywords,
        save_path=save_path,
        max_attempts=5,
        media_title=item.title,
    )

    return {
        "success": pipeline_result.get("success", False),
        "method": "search_pipeline",
        "saved_count": pipeline_result.get("saved_count", 0),
        "save_path": save_path,
        "attempts": pipeline_result.get("attempts", 0),
        "error": pipeline_result.get("error", ""),
    }


def _action_notify(match_result, config_path):
    """飞书通知动作"""
    item = match_result.item
    rule = match_result.rule
    links = match_result.get_target_links()
    link_str = links[0] if links else item.link

    content = {
        "zh_cn": {
            "title": "📡 RSS 新条目匹配",
            "content": [
                [{"tag": "text", "text": "📌 {}".format(item.title)}],
                [{"tag": "text", "text": "规则: {}".format(rule.get("name", ""))}],
                [{"tag": "text", "text": "链接: {}".format(link_str)}],
            ],
        },
    }

    try:
        from quark_cli.scheduler import send_bot_notify
        send_bot_notify(config_path, {"_custom_content": content})
        return {"notified": True}
    except Exception as e:
        logger.debug("通知发送失败: %s", e)
        return {"notified": False, "error": str(e)}


def _record_history(match_result, action_result, config_path):
    """写入历史记录"""
    from quark_cli.history import record

    item = match_result.item
    status = "success" if action_result.get("success") else "error"

    summary = "[{}] {} → {}".format(
        match_result.action,
        item.title[:60],
        action_result.get("detail", {}).get("save_path", "")
        or action_result.get("detail", {}).get("error", "")[:60]
        or "done",
    )

    record(
        record_type="rss",
        name=match_result.rule.get("name", "RSS"),
        status=status,
        summary=summary,
        detail={
            "item": item.to_dict(),
            "rule": match_result.rule.get("name", ""),
            "action": match_result.action,
            "result": action_result.get("detail", {}),
        },
        duration=action_result.get("duration", 0),
        config_path=config_path,
    )
