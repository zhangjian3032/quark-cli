"""
网盘资源搜索模块 - 聚合多个网盘搜索引擎

支持的搜索源类型:
  - api:   JSON API 搜索（如自部署的 pansou，返回结构化 JSON）
  - html:  HTML 页面解析（通过正则从搜索结果页面提取链接）
"""

import re
import json
import requests
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin


class PanSearch:
    """网盘资源搜索引擎聚合器"""

    # 默认搜索源配置
    DEFAULT_SOURCES = {
        "pansou": {
            "name": "盘搜",
            "base_url": "https://www.pansou.com",
            "type": "html",
            "search_path": "/s?q={keyword}&pan=quark",
            "link_pattern": r'href="(https?://pan\.quark\.cn/s/[a-zA-Z0-9]+)"',
            "title_pattern": r'class="item-title[^"]*"[^>]*>([^<]+)<',
        },
        "funletu": {
            "name": "盘乐趣",
            "base_url": "https://pan.funletu.com",
            "type": "html",
            "search_path": "/search?keyword={keyword}&type=quark",
            "link_pattern": r'href="(https?://pan\.quark\.cn/s/[a-zA-Z0-9]+)"',
            "title_pattern": r'title="([^"]+)"',
        },
    }

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, config=None):
        self.sources = {}
        # 深拷贝默认配置
        for k, v in self.DEFAULT_SOURCES.items():
            self.sources[k] = dict(v)

        # 从配置加载自定义搜索源
        if config:
            custom = config.data.get("search_sources", {})
            if isinstance(custom, dict):
                for name, value in custom.items():
                    if isinstance(value, str):
                        # 纯 URL 字符串：自动检测类型
                        self._add_url_source(name, value)
                    elif isinstance(value, dict):
                        # 完整配置对象
                        self.sources[name] = value

    def _add_url_source(self, name: str, url: str):
        """根据 URL 自动判断并添加搜索源"""
        url = url.rstrip("/")
        # 如果已有同名源，仅覆盖 base_url
        if name in self.sources:
            self.sources[name]["base_url"] = url
            return

        # 新搜索源：尝试探测 API 端点
        # 含 /api 或常见 API 特征的，默认当 API 源处理
        self.sources[name] = {
            "name": name,
            "base_url": url,
            "type": "api",
            "api_path": "/api/search",
            "api_params": {"kw": "{keyword}", "res": "merge", "src": "all"},
            "result_path": "data.merged_by_type",
            "filter_types": ["quark"],
        }

    def search(self, keyword: str, source: str = "pansou") -> dict:
        """
        搜索网盘资源

        Args:
            keyword: 搜索关键词
            source: 搜索源名称

        Returns:
            dict: {success, results: [{title, url, source}]}
        """
        if not keyword or not keyword.strip():
            return {"success": False, "error": "搜索关键词不能为空"}

        src = self.sources.get(source)
        if not src:
            return {
                "success": False,
                "error": f"未知搜索源: {source}",
                "available_sources": list(self.sources.keys()),
            }

        try:
            src_type = src.get("type", "html")
            if src_type == "api":
                return self._search_api(keyword, src, source)
            else:
                return self._search_html(keyword, src, source)
        except requests.Timeout:
            return {"success": False, "error": f"搜索超时 ({source})"}
        except requests.ConnectionError as e:
            return {"success": False, "error": f"无法连接搜索源 ({source}): {e}"}
        except Exception as e:
            return {"success": False, "error": f"搜索异常: {str(e)}"}

    def search_all(self, keyword: str) -> dict:
        """在所有搜索源中搜索"""
        all_results = []
        errors = []
        for source_name in self.sources:
            result = self.search(keyword, source_name)
            if result["success"]:
                all_results.extend(result.get("results", []))
            else:
                errors.append(f"{source_name}: {result.get('error')}")

        # 去重（按 URL）
        seen = set()
        unique = []
        for r in all_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        return {
            "success": True,
            "keyword": keyword,
            "results": unique,
            "count": len(unique),
            "errors": errors if errors else None,
        }

    def _search_api(self, keyword: str, src: dict, source_name: str) -> dict:
        """JSON API 搜索（适配 pansou 自部署等 API）"""
        base_url = src["base_url"].rstrip("/")
        api_path = src.get("api_path", "/api/search")
        url = f"{base_url}{api_path}"

        # 构建请求参数
        api_params = src.get("api_params", {"kw": "{keyword}"})
        params = {}
        for k, v in api_params.items():
            if isinstance(v, str):
                params[k] = v.replace("{keyword}", keyword)
            else:
                params[k] = v

        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.USER_AGENT,
        }

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return {
                "success": False,
                "error": data.get("message", "API 返回错误"),
                "source": source_name,
            }

        # 解析结果
        results = []
        filter_types = src.get("filter_types", ["quark"])
        result_path = src.get("result_path", "data.merged_by_type")

        # 导航到嵌套路径
        obj = data
        for key in result_path.split("."):
            obj = obj.get(key, {}) if isinstance(obj, dict) else {}

        if isinstance(obj, dict):
            # merged_by_type 格式: {"quark": [...], "baidu": [...], ...}
            for type_name, items in obj.items():
                if filter_types and type_name not in filter_types:
                    continue
                if not isinstance(items, list):
                    continue
                for item in items:
                    url_val = item.get("url", "")
                    note = item.get("note", "").strip()
                    password = item.get("password", "")
                    source_tag = item.get("source", "")
                    if url_val:
                        entry = {
                            "title": note or "未知资源",
                            "url": url_val,
                            "source": source_name,
                            "type": type_name,
                            "password": password,
                        }
                        if source_tag:
                            entry["upstream"] = source_tag
                        results.append(entry)
        elif isinstance(obj, list):
            # 平铺列表格式
            for item in obj:
                url_val = item.get("url", "")
                note = item.get("note", item.get("title", "")).strip()
                if url_val:
                    results.append({
                        "title": note or "未知资源",
                        "url": url_val,
                        "source": source_name,
                        "password": item.get("password", ""),
                    })

        return {
            "success": True,
            "keyword": keyword,
            "source": source_name,
            "source_url": f"{url}?kw={quote(keyword)}",
            "results": results,
            "count": len(results),
            "total": data.get("data", {}).get("total", len(results)),
        }

    def _search_html(self, keyword: str, src: dict, source_name: str) -> dict:
        """HTML 页面解析搜索"""
        base_url = src["base_url"]
        search_path = src["search_path"].replace("{keyword}", quote(keyword))
        url = urljoin(base_url, search_path)

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": base_url,
        }

        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        # 提取链接
        links = re.findall(src.get("link_pattern", ""), html)
        # 提取标题
        titles = re.findall(src.get("title_pattern", ""), html)

        if not links:
            # 尝试通用夸克链接提取
            links = re.findall(r"https?://pan\.quark\.cn/s/[a-zA-Z0-9]+", html)

        results = []
        seen = set()
        for i, link in enumerate(links):
            if link in seen:
                continue
            seen.add(link)
            title = titles[i].strip() if i < len(titles) else f"资源 {i + 1}"
            # 清理 HTML 实体
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            title = re.sub(r"<[^>]+>", "", title)
            results.append({
                "title": title,
                "url": link,
                "source": source_name,
            })

        return {
            "success": True,
            "keyword": keyword,
            "source": source_name,
            "source_url": url,
            "results": results,
            "count": len(results),
        }

    def list_sources(self) -> List[dict]:
        """列出所有可用搜索源"""
        return [
            {
                "name": key,
                "display_name": val.get("name", key),
                "base_url": val.get("base_url", ""),
                "type": val.get("type", "html"),
            }
            for key, val in self.sources.items()
        ]
