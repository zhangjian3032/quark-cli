"""
RSS 规则匹配引擎

对每个 FeedItem 应用用户定义的规则 (Rules), 判断是否命中。
支持: 正则匹配标题、排除正则、大小过滤、画质过滤、去重。
"""

import logging
import re
from typing import Any, Dict, List, Optional

from quark_cli.rss.fetcher import FeedItem, extract_links

logger = logging.getLogger("quark_cli.rss.matcher")


# ═══════════════════════════════════════════════════
#  规则定义
# ═══════════════════════════════════════════════════

DEFAULT_RULE = {
    "name": "",                # 规则名称 (显示用)
    "match": "",               # 正则匹配标题 (为空 = 匹配所有)
    "exclude": "",             # 排除正则 (匹配到则跳过)
    "media_type": "",          # movie / tv / "" (不限)
    "quality": "",             # 画质正则 (如 "4K|2160p|1080p")
    "min_size_gb": 0,          # 最小文件大小 GB (0 = 不限)
    "max_size_gb": 0,          # 最大文件大小 GB (0 = 不限)
    "save_path": "",           # 转存路径
    "action": "auto_save",     # auto_save / notify / log
    "link_type": "quark",      # 优先提取的链接类型: quark / alipan / magnet / enclosure / web / any
    "enabled": True,
}


def merge_rule_defaults(rule):
    """填充规则默认值"""
    merged = dict(DEFAULT_RULE)
    merged.update(rule)
    return merged


# ═══════════════════════════════════════════════════
#  大小解析
# ═══════════════════════════════════════════════════

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|G|MB|M|TB|T|KB|K)\b", re.IGNORECASE)


def _parse_size_gb(text):
    """从文本中提取文件大小 (GB), 未找到返回 None"""
    m = _SIZE_RE.search(text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit in ("TB", "T"):
        return val * 1024
    if unit in ("GB", "G"):
        return val
    if unit in ("MB", "M"):
        return val / 1024
    if unit in ("KB", "K"):
        return val / (1024 * 1024)
    return val


# ═══════════════════════════════════════════════════
#  匹配结果
# ═══════════════════════════════════════════════════

class MatchResult:
    """单条匹配结果"""

    def __init__(self, item, rule, links, matched_by=""):
        self.item = item          # FeedItem
        self.rule = rule          # dict
        self.links = links        # extract_links() 结果
        self.matched_by = matched_by  # 匹配描述
        self.action = rule.get("action", "auto_save")
        self.save_path = rule.get("save_path", "")
        self.link_type = rule.get("link_type", "quark")

    def get_target_links(self):
        """根据 link_type 返回目标链接列表"""
        lt = self.link_type
        if lt == "any":
            # 优先级: quark > alipan > enclosure > magnet > web
            for key in ("quark", "alipan", "enclosure", "magnet", "web"):
                if self.links.get(key):
                    return self.links[key]
            return []
        return self.links.get(lt, [])

    def to_dict(self):
        return {
            "item": self.item.to_dict(),
            "rule_name": self.rule.get("name", ""),
            "action": self.action,
            "save_path": self.save_path,
            "link_type": self.link_type,
            "target_links": self.get_target_links(),
            "matched_by": self.matched_by,
        }


# ═══════════════════════════════════════════════════
#  匹配引擎
# ═══════════════════════════════════════════════════

def match_item(item, rule):
    """
    判断单个 FeedItem 是否匹配规则.

    Args:
        item: FeedItem
        rule: dict (已合并默认值)

    Returns:
        MatchResult 或 None
    """
    rule = merge_rule_defaults(rule)

    if not rule.get("enabled", True):
        return None

    title = item.title or ""
    full_text = "{} {}".format(title, item.description or "")

    # 1. 排除正则
    exclude = rule.get("exclude", "")
    if exclude:
        try:
            if re.search(exclude, title, re.IGNORECASE):
                return None
        except re.error:
            logger.warning("无效的排除正则: %s", exclude)

    # 2. 匹配正则
    match_pattern = rule.get("match", "")
    if match_pattern:
        try:
            if not re.search(match_pattern, title, re.IGNORECASE):
                return None
        except re.error:
            logger.warning("无效的匹配正则: %s", match_pattern)
            return None

    # 3. 画质过滤
    quality = rule.get("quality", "")
    if quality:
        try:
            if not re.search(quality, title, re.IGNORECASE):
                return None
        except re.error:
            pass

    # 4. 大小过滤
    min_gb = float(rule.get("min_size_gb", 0) or 0)
    max_gb = float(rule.get("max_size_gb", 0) or 0)
    if min_gb > 0 or max_gb > 0:
        size = _parse_size_gb(full_text)
        # 也检查 enclosure length
        if size is None and item.enclosures:
            for enc in item.enclosures:
                length = enc.get("length", 0)
                if length and length > 0:
                    size = length / (1024 * 1024 * 1024)
                    break
        if size is not None:
            if min_gb > 0 and size < min_gb:
                return None
            if max_gb > 0 and size > max_gb:
                return None

    # 5. 提取链接
    links = extract_links(item)

    # 6. 检查是否有目标类型的链接
    link_type = rule.get("link_type", "quark")
    if link_type != "any":
        if not links.get(link_type):
            # 如果指定了具体链接类型但找不到, 对 auto_save 动作跳过
            if rule.get("action") == "auto_save":
                return None

    matched_by = "rule:{}".format(rule.get("name", "unnamed"))
    if match_pattern:
        matched_by += " match:{}".format(match_pattern)

    return MatchResult(item=item, rule=rule, links=links, matched_by=matched_by)


def match_items(items, rules, seen_guids=None):
    """
    批量匹配: 对 items 列表逐个应用 rules.

    每个 item 只匹配第一个命中的 rule (优先级 = rules 列表顺序).
    已处理过的 guid (seen_guids) 自动跳过.

    Args:
        items: list[FeedItem]
        rules: list[dict]
        seen_guids: set[str] 已处理的 guid 集合

    Returns:
        list[MatchResult]
    """
    if seen_guids is None:
        seen_guids = set()

    results = []
    for item in items:
        if not item.guid:
            continue
        if item.guid in seen_guids:
            continue

        for rule in rules:
            result = match_item(item, rule)
            if result:
                results.append(result)
                break  # 一个 item 只匹配一条 rule

    return results
