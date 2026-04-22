"""
RSS 匹配后动作执行

支持的动作:
  - auto_save: 提取夸克链接 → auto_save_pipeline 转存
  - torrent:   推送 torrent/magnet 到 qBittorrent
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
        elif action == "torrent":
            result["detail"] = _action_torrent(match_result, config_path)
            result["success"] = result["detail"].get("success", False)
        elif action == "guangya":
            result["detail"] = _action_guangya(match_result, config_path)
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


def _action_torrent(match_result, config_path):
    """
    Torrent 下载动作 — 推送 torrent/magnet 到 qBittorrent

    根据 link_type 自动判断推送方式:
      - magnet:     直接推送磁力链接
      - enclosure:  下载 .torrent 文件后上传
      - 其他 URL:   尝试作为 URL 推送 (qB 自行下载)
    """
    from quark_cli.rss.torrent_client import (
        get_torrent_client, download_torrent_file,
        is_magnet_url, is_torrent_url,
    )
    from quark_cli.config import ConfigManager, get_proxy_for

    rule = match_result.rule
    item = match_result.item

    # 获取代理
    _cfg = ConfigManager(config_path)
    _cfg.load()
    proxy = get_proxy_for(_cfg.data, "torrent") or get_proxy_for(_cfg.data, "rss")

    # 1. 获取 qBittorrent 客户端
    client_id = rule.get("torrent_client", "")
    try:
        qb = get_torrent_client(config_path, client_id or None)
    except (ValueError, Exception) as e:
        return {"success": False, "error": "qBittorrent 客户端初始化失败: {}".format(e)}

    # 2. 确定下载参数 (规则级 > 客户端默认)
    save_path = rule.get("torrent_save_path", "") or ""
    category = rule.get("torrent_category", "") or ""
    tags = rule.get("torrent_tags", []) or []
    paused = rule.get("torrent_paused", False)

    # 3. 获取目标链接
    target_links = match_result.get_target_links()
    if not target_links:
        return {"success": False, "error": "无可用链接 (link_type: {})".format(match_result.link_type)}

    link = target_links[0]

    # 4. 根据链接类型推送
    try:
        if is_magnet_url(link):
            # 磁力链接 → 直接推送
            result = qb.add_magnet(
                link,
                save_path=save_path,
                category=category,
                tags=tags,
                paused=paused,
            )
            method = "magnet"

        elif is_torrent_url(link) or _is_torrent_enclosure(match_result, link):
            # .torrent URL → 先下载文件再上传 (更可靠, 支持 PT 站认证)
            auth = _get_feed_auth(match_result, config_path)
            try:
                torrent_bytes, filename = download_torrent_file(link, auth=auth, proxy=proxy)
                result = qb.add_torrent_file(
                    torrent_bytes, filename,
                    save_path=save_path,
                    category=category,
                    tags=tags,
                    paused=paused,
                )
                method = "torrent_file"
            except Exception as e:
                # 下载失败 → 回退到 URL 模式
                logger.warning("下载 .torrent 失败, 回退到 URL 模式: %s", e)
                result = qb.add_torrent_url(
                    link,
                    save_path=save_path,
                    category=category,
                    tags=tags,
                    paused=paused,
                )
                method = "torrent_url_fallback"

        else:
            # 其他 URL → 尝试直接推送给 qB
            result = qb.add_torrent_url(
                link,
                save_path=save_path,
                category=category,
                tags=tags,
                paused=paused,
            )
            method = "url"

        return {
            "success": result.get("success", False),
            "method": method,
            "url": link[:120],
            "torrent_hash": result.get("hash", ""),
            "save_path": save_path,
            "category": category,
            "error": result.get("error", ""),
        }

    except Exception as e:
        logger.exception("Torrent 推送异常: %s", item.title)
        return {"success": False, "error": str(e), "url": link[:120]}


def _is_torrent_enclosure(match_result, link):
    """判断链接是否来自 torrent enclosure"""
    from quark_cli.rss.torrent_client import TORRENT_MIME_TYPES

    # 检查 enclosure MIME type
    for enc in match_result.item.enclosures:
        if enc.get("url") == link:
            mime = enc.get("type", "")
            if mime in TORRENT_MIME_TYPES:
                return True
    return False


def _get_feed_auth(match_result, config_path):
    """
    获取 Feed 的认证配置 (cookie/headers), 用于下载 .torrent 文件

    PT 站的 .torrent URL 通常需要 passkey 或 cookie 认证。
    """
    try:
        from quark_cli.rss.manager import RssManager
        manager = RssManager(config_path)
        feeds = manager.list_feeds()

        # 通过 rule 的 feed_id 找到对应 feed
        rule_name = match_result.rule.get("name", "")
        for feed in feeds:
            for rule in feed.get("rules", []):
                if rule.get("name") == rule_name:
                    return feed.get("auth", {})
    except Exception:
        pass

    return {}



def _action_guangya(match_result, config_path):
    """
    光鸭云盘云添加动作 — RSS 匹配到 magnet/torrent 后推送到光鸭

    根据 link_type 自动判断:
      - magnet:        解析磁力 → 创建云添加任务
      - enclosure/torrent_enclosure: 下载 .torrent → 上传解析 → 创建云添加任务
    """
    from quark_cli.config import ConfigManager
    from quark_cli.guangya_api import GuangyaAPI
    from quark_cli.rss.torrent_client import (
        download_torrent_file, is_magnet_url, is_torrent_url,
    )
    import tempfile, os

    rule = match_result.rule
    item = match_result.item

    # 1. 获取光鸭客户端
    cfg = ConfigManager(config_path)
    cfg.load()
    from quark_cli.config import get_proxy_for
    proxy = get_proxy_for(cfg.data, "torrent") or get_proxy_for(cfg.data, "rss")
    gy_cfg = cfg.data.get("guangya", {})
    refresh_token = gy_cfg.get("refresh_token", "")
    if not refresh_token:
        return {"success": False, "error": "未配置光鸭云盘 refresh_token"}

    client = GuangyaAPI(refresh_token=refresh_token)
    info = client.init()
    if not info:
        return {"success": False, "error": "光鸭云盘凭证无效"}

    # 2. 保存目录
    parent_id = rule.get("guangya_parent_id", "") or ""

    # 3. 获取目标链接
    target_links = match_result.get_target_links()
    if not target_links:
        return {"success": False, "error": "无可用链接 (link_type: {})".format(match_result.link_type)}

    link = target_links[0]

    # 4. 根据链接类型处理
    try:
        if is_magnet_url(link):
            # 磁力链接 → 解析 → 创建任务
            resolve_data = client.resolve_magnet(link)
            if not resolve_data:
                return {"success": False, "error": "磁力链接解析失败", "url": link[:120]}

            bt_info = resolve_data.get("btResInfo", {})
            subfiles = bt_info.get("subfiles", [])
            file_indexes = list(range(len(subfiles))) if subfiles else None

            task = client.create_cloud_task(
                url=link, parent_id=parent_id, file_indexes=file_indexes,
            )
            if not task:
                return {"success": False, "error": "创建云添加任务失败", "url": link[:120]}

            return {
                "success": True,
                "method": "magnet",
                "url": link[:120],
                "task_id": task.get("taskId", ""),
                "file_name": bt_info.get("fileName", item.title),
            }

        elif is_torrent_url(link) or _is_torrent_enclosure(match_result, link):
            # 种子 URL → 下载 → 上传解析 → 创建任务
            auth = _get_feed_auth(match_result, config_path)
            try:
                torrent_bytes, filename = download_torrent_file(link, auth=auth, proxy=proxy)
            except Exception as dl_err:
                logger.warning('种子下载失败 [%s]: %s, 尝试云端解析', link[:80], dl_err)
                # Fallback: 尝试让光鸭云端直接解析 URL (某些公开种子可行)
                resolve_data = client.resolve_magnet(link)
                if resolve_data:
                    bt_info = resolve_data.get('btResInfo', {})
                    subfiles = bt_info.get('subfiles', [])
                    file_indexes = list(range(len(subfiles))) if subfiles else None
                    magnet_url = resolve_data.get('url', '') or link
                    task = client.create_cloud_task(
                        url=magnet_url, parent_id=parent_id, file_indexes=file_indexes,
                    )
                    if task:
                        return {
                            'success': True,
                            'method': 'torrent_cloud_fallback',
                            'url': link[:120],
                            'task_id': task.get('taskId', ''),
                            'file_name': bt_info.get('fileName', item.title),
                        }
                return {
                    'success': False,
                    'error': '种子下载失败且云端无法解析: {} (可通过 WebUI 手动上传 .torrent)'.format(str(dl_err)[:80]),
                    'url': link[:120],
                }

            # 保存到临时文件供 API 上传
            tmp = tempfile.NamedTemporaryFile(suffix=".torrent", delete=False)
            try:
                tmp.write(torrent_bytes)
                tmp.close()

                resolve_data = client.resolve_torrent(tmp.name)
                if not resolve_data:
                    return {"success": False, "error": "种子解析失败", "url": link[:120]}

                bt_info = resolve_data.get("btResInfo", {})
                subfiles = bt_info.get("subfiles", [])
                file_indexes = list(range(len(subfiles))) if subfiles else None
                magnet_url = resolve_data.get("url", "")

                if not magnet_url:
                    # 从 info_hash 构造 magnet
                    info_hash = bt_info.get("infoHash", "")
                    if info_hash:
                        magnet_url = "magnet:?xt=urn:btih:{}".format(info_hash)
                    else:
                        return {"success": False, "error": "无法获取磁力链接", "url": link[:120]}

                task = client.create_cloud_task(
                    url=magnet_url, parent_id=parent_id, file_indexes=file_indexes,
                )
                if not task:
                    return {"success": False, "error": "创建云添加任务失败", "url": link[:120]}

                return {
                    "success": True,
                    "method": "torrent",
                    "url": link[:120],
                    "task_id": task.get("taskId", ""),
                    "file_name": bt_info.get("fileName", filename),
                }
            finally:
                os.unlink(tmp.name)

        else:
            # 未知链接类型, 尝试作为磁力链接
            return {"success": False, "error": "不支持的链接类型: {}".format(link[:80])}

    except Exception as e:
        logger.exception("光鸭云添加异常: %s", item.title)
        return {"success": False, "error": str(e), "url": link[:120]}


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
