"""
RSS Feed 拉取与解析

支持 RSS 2.0 / Atom / JSON Feed, 纯标准库实现 (xml.etree), 无需 feedparser 依赖。
可选: 安装 feedparser 后自动使用更健壮的解析。

特性:
  - ETag / Last-Modified 条件请求, 节省带宽
  - 自定义 Auth (passkey / cookie / headers)
  - 超时 + 重试
  - 统一输出 FeedItem 数据模型
"""

import logging
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger("quark_cli.rss.fetcher")


# ═══════════════════════════════════════════════════
#  数据模型
# ═══════════════════════════════════════════════════

class FeedItem:
    """RSS 条目统一数据模型"""

    __slots__ = (
        "guid", "title", "link", "description", "pub_date",
        "author", "categories", "enclosures", "extra",
    )

    def __init__(
        self,
        guid="",
        title="",
        link="",
        description="",
        pub_date=None,
        author="",
        categories=None,
        enclosures=None,
        extra=None,
    ):
        self.guid = guid
        self.title = title
        self.link = link
        self.description = description
        self.pub_date = pub_date          # datetime or None
        self.author = author
        self.categories = categories or []
        self.enclosures = enclosures or []  # list[dict] with url, type, length
        self.extra = extra or {}

    def to_dict(self):
        return {
            "guid": self.guid,
            "title": self.title,
            "link": self.link,
            "description": self.description[:500] if self.description else "",
            "pub_date": self.pub_date.isoformat() if self.pub_date else None,
            "author": self.author,
            "categories": self.categories,
            "enclosures": self.enclosures,
            "extra": self.extra,
        }

    def __repr__(self):
        return "<FeedItem '{}' [{}]>".format(self.title[:40], self.guid[:20])


class FeedResult:
    """Feed 拉取结果"""

    def __init__(
        self,
        feed_title="",
        feed_link="",
        feed_description="",
        items=None,
        etag="",
        last_modified="",
        fetched_at=None,
        not_modified=False,
    ):
        self.feed_title = feed_title
        self.feed_link = feed_link
        self.feed_description = feed_description
        self.items = items or []           # list[FeedItem]
        self.etag = etag
        self.last_modified = last_modified
        self.fetched_at = fetched_at or datetime.now()
        self.not_modified = not_modified   # 304 Not Modified


class FetchError(Exception):
    """Feed 拉取错误"""
    def __init__(self, message, status_code=0):
        self.status_code = status_code
        super().__init__(message)


# ═══════════════════════════════════════════════════
#  解析器
# ═══════════════════════════════════════════════════

def _parse_date(date_str):
    """尝试解析各种日期格式, 返回 datetime 或 None"""
    if not date_str:
        return None
    date_str = date_str.strip()

    # RFC 2822 (RSS 标准)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass

    # ISO 8601 / Atom
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def _text(elem, tag, ns=""):
    """安全获取子元素文本"""
    if ns:
        child = elem.find("{%s}%s" % (ns, tag))
    else:
        child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _parse_rss2(root):
    """解析 RSS 2.0 格式"""
    channel = root.find("channel")
    if channel is None:
        return FeedResult()

    feed_title = _text(channel, "title")
    feed_link = _text(channel, "link")
    feed_desc = _text(channel, "description")

    items = []
    for item_elem in channel.findall("item"):
        guid = _text(item_elem, "guid") or _text(item_elem, "link")
        title = _text(item_elem, "title")
        link = _text(item_elem, "link")
        desc = _text(item_elem, "description")
        pub_date = _parse_date(_text(item_elem, "pubDate"))
        author = _text(item_elem, "author") or _text(item_elem, "{http://purl.org/dc/elements/1.1/}creator")

        categories = []
        for cat in item_elem.findall("category"):
            if cat.text:
                categories.append(cat.text.strip())

        enclosures = []
        for enc in item_elem.findall("enclosure"):
            enclosures.append({
                "url": enc.get("url", ""),
                "type": enc.get("type", ""),
                "length": int(enc.get("length", 0) or 0),
            })

        # 提取额外字段 (常见于 PT 站 RSS)
        extra = {}
        # 做种/下载数 (常见于 NexusPHP)
        for ns_tag in [
            "{https://mikanani.me}size",
            "contentLength",
        ]:
            val = _text(item_elem, ns_tag)
            if val:
                extra["size"] = val

        items.append(FeedItem(
            guid=guid,
            title=title,
            link=link,
            description=desc,
            pub_date=pub_date,
            author=author,
            categories=categories,
            enclosures=enclosures,
            extra=extra,
        ))

    return FeedResult(
        feed_title=feed_title,
        feed_link=feed_link,
        feed_description=feed_desc,
        items=items,
    )


_ATOM_NS = "http://www.w3.org/2005/Atom"


def _parse_atom(root):
    """解析 Atom 格式"""
    ns = _ATOM_NS
    feed_title = _text(root, "title", ns)

    feed_link = ""
    for link_elem in root.findall("{%s}link" % ns):
        rel = link_elem.get("rel", "alternate")
        if rel == "alternate":
            feed_link = link_elem.get("href", "")
            break
    if not feed_link:
        link_elem = root.find("{%s}link" % ns)
        if link_elem is not None:
            feed_link = link_elem.get("href", "")

    feed_desc = _text(root, "subtitle", ns)

    items = []
    for entry in root.findall("{%s}entry" % ns):
        guid = _text(entry, "id", ns)
        title = _text(entry, "title", ns)

        link = ""
        for link_elem in entry.findall("{%s}link" % ns):
            rel = link_elem.get("rel", "alternate")
            if rel in ("alternate", ""):
                link = link_elem.get("href", "")
                break
        if not link:
            link_elem = entry.find("{%s}link" % ns)
            if link_elem is not None:
                link = link_elem.get("href", "")

        # content or summary
        content_elem = entry.find("{%s}content" % ns)
        summary_elem = entry.find("{%s}summary" % ns)
        desc = ""
        if content_elem is not None and content_elem.text:
            desc = content_elem.text.strip()
        elif summary_elem is not None and summary_elem.text:
            desc = summary_elem.text.strip()

        pub_date = _parse_date(
            _text(entry, "published", ns) or _text(entry, "updated", ns)
        )
        author = ""
        author_elem = entry.find("{%s}author" % ns)
        if author_elem is not None:
            author = _text(author_elem, "name", ns)

        categories = []
        for cat in entry.findall("{%s}category" % ns):
            term = cat.get("term", "")
            if term:
                categories.append(term)

        enclosures = []
        for link_elem in entry.findall("{%s}link" % ns):
            if link_elem.get("rel") == "enclosure":
                enclosures.append({
                    "url": link_elem.get("href", ""),
                    "type": link_elem.get("type", ""),
                    "length": int(link_elem.get("length", 0) or 0),
                })

        items.append(FeedItem(
            guid=guid or link,
            title=title,
            link=link,
            description=desc,
            pub_date=pub_date,
            author=author,
            categories=categories,
            enclosures=enclosures,
        ))

    return FeedResult(
        feed_title=feed_title,
        feed_link=feed_link,
        feed_description=feed_desc,
        items=items,
    )


def _parse_json_feed(data):
    """解析 JSON Feed 1.0/1.1 格式"""
    items = []
    for raw in data.get("items", []):
        pub_date = _parse_date(raw.get("date_published") or raw.get("date_modified"))
        author = ""
        authors = raw.get("authors") or raw.get("author")
        if isinstance(authors, list) and authors:
            author = authors[0].get("name", "")
        elif isinstance(authors, dict):
            author = authors.get("name", "")

        enclosures = []
        for att in raw.get("attachments", []):
            enclosures.append({
                "url": att.get("url", ""),
                "type": att.get("mime_type", ""),
                "length": int(att.get("size_in_bytes", 0) or 0),
            })

        items.append(FeedItem(
            guid=str(raw.get("id", "")),
            title=raw.get("title", ""),
            link=raw.get("url", "") or raw.get("external_url", ""),
            description=raw.get("content_text", "") or raw.get("content_html", ""),
            pub_date=pub_date,
            author=author,
            categories=raw.get("tags", []),
            enclosures=enclosures,
        ))

    return FeedResult(
        feed_title=data.get("title", ""),
        feed_link=data.get("home_page_url", ""),
        feed_description=data.get("description", ""),
        items=items,
    )


def parse_feed_content(content, content_type=""):
    """
    解析 Feed 内容 (自动识别格式).

    Args:
        content: str (XML) 或 dict (JSON)
        content_type: HTTP Content-Type, 辅助判断

    Returns:
        FeedResult
    """
    # JSON Feed
    if isinstance(content, dict):
        return _parse_json_feed(content)

    text = content.strip()

    # 尝试 JSON
    if text.startswith("{"):
        import json
        try:
            data = json.loads(text)
            if "items" in data or "version" in data:
                return _parse_json_feed(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # XML 解析
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise FetchError("XML 解析失败: {}".format(e))

    tag = root.tag.lower()

    # Atom
    if "atom" in tag or "feed" in tag:
        return _parse_atom(root)

    # RSS 2.0
    if tag == "rss" or root.find("channel") is not None:
        return _parse_rss2(root)

    # RDF / RSS 1.0
    if "rdf" in tag:
        return _parse_rss2(root)

    raise FetchError("无法识别的 Feed 格式: <{}>".format(root.tag))


# ═══════════════════════════════════════════════════
#  HTTP 拉取
# ═══════════════════════════════════════════════════

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; quark-cli RSS; "
    "+https://github.com/zhangjian3032/quark-cli)"
)


def fetch_feed(
    feed_url,
    auth=None,
    etag="",
    last_modified="",
    timeout=30,
    max_retries=2,
):
    """
    拉取并解析 RSS Feed.

    Args:
        feed_url: Feed URL
        auth: dict with optional passkey/cookie/headers
        etag: 上次的 ETag (条件请求)
        last_modified: 上次的 Last-Modified (条件请求)
        timeout: 请求超时秒数
        max_retries: 最大重试次数

    Returns:
        FeedResult

    Raises:
        FetchError
    """
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "application/rss+xml, application/atom+xml, "
                  "application/json, application/xml, text/xml, */*",
    }

    # 条件请求
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    # Auth
    if auth:
        if auth.get("cookie"):
            headers["Cookie"] = auth["cookie"]
        if auth.get("headers") and isinstance(auth["headers"], dict):
            headers.update(auth["headers"])
        # passkey — 追加到 URL
        passkey = auth.get("passkey", "")
        if passkey and "passkey=" not in feed_url:
            sep = "&" if "?" in feed_url else "?"
            feed_url = "{}{}passkey={}".format(feed_url, sep, passkey)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                feed_url, headers=headers, timeout=timeout, allow_redirects=True
            )

            # 304 Not Modified
            if resp.status_code == 304:
                return FeedResult(not_modified=True, etag=etag, last_modified=last_modified)

            if resp.status_code >= 400:
                raise FetchError(
                    "HTTP {} — {}".format(resp.status_code, resp.text[:200]),
                    status_code=resp.status_code,
                )

            ct = resp.headers.get("Content-Type", "")
            new_etag = resp.headers.get("ETag", "")
            new_lm = resp.headers.get("Last-Modified", "")

            # 解析
            if "json" in ct:
                result = parse_feed_content(resp.json(), ct)
            else:
                result = parse_feed_content(resp.text, ct)

            result.etag = new_etag
            result.last_modified = new_lm
            result.fetched_at = datetime.now()
            return result

        except FetchError:
            raise
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise FetchError("网络请求失败 (重试 {} 次): {}".format(max_retries, e))
        except Exception as e:
            raise FetchError("Feed 解析异常: {}".format(e))

    raise FetchError("未知错误")


# ═══════════════════════════════════════════════════
#  链接提取
# ═══════════════════════════════════════════════════

# 匹配夸克网盘链接
_QUARK_LINK_RE = re.compile(r"https?://pan\.quark\.cn/s/\w+")
# 匹配阿里云盘链接
_ALI_LINK_RE = re.compile(r"https?://www\.alipan\.com/s/\w+|https?://www\.aliyundrive\.com/s/\w+")
# 匹配磁力链接
_MAGNET_RE = re.compile(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+")


def extract_links(item):
    """
    从 FeedItem 中提取各类资源链接.

    Returns:
        dict: {
            "quark": [url, ...],
            "alipan": [url, ...],
            "magnet": [url, ...],
            "web": [url, ...],      # 原始 link
            "enclosure": [url, ...], # RSS enclosure (通常是种子)
        }
    """
    text = " ".join([
        item.title or "",
        item.description or "",
        item.link or "",
    ])

    links = {
        "quark": list(set(_QUARK_LINK_RE.findall(text))),
        "alipan": list(set(_ALI_LINK_RE.findall(text))),
        "magnet": list(set(_MAGNET_RE.findall(text))),
        "web": [item.link] if item.link else [],
        "enclosure": [e["url"] for e in item.enclosures if e.get("url")],
    }
    return links
