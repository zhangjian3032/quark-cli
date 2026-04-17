"""
网盘资源搜索模块 - 聚合多个网盘搜索引擎

支持的搜索源类型:
  - api:   JSON API 搜索（如自部署的 pansou，返回结构化 JSON）
  - html:  HTML 页面解析（通过正则从搜索结果页面提取链接）
"""

import re
import json
import time
import requests
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

from quark_cli import debug as dbg


class PanSearch:
    """网盘资源搜索引擎聚合器"""

    # 默认搜索源配置 - pansou 使用 JSON API 模式
    DEFAULT_SOURCES = {
        "pansou": {
            "name": "盘搜",
            "base_url": "https://www.pansou.com",
            "type": "api",
            "api_path": "/api/search",
            "api_params": {"kw": "{keyword}", "res": "merge", "src": "all"},
            "result_path": "data.merged_by_type",
            "filter_types": ["quark"],
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

        dbg.log("Search", f"已加载 {len(self.sources)} 个搜索源: {list(self.sources.keys())}")

    def _add_url_source(self, name: str, url: str):
        """根据 URL 自动判断并添加搜索源"""
        url = url.rstrip("/")
        # 如果已有同名源（如 pansou），覆盖 base_url，保留 API 配置
        if name in self.sources:
            self.sources[name]["base_url"] = url
            dbg.log("Search", f"更新已有搜索源 '{name}' 的 base_url → {url}")
            return

        # 新搜索源：默认当 API 源处理
        dbg.log("Search", f"新增 API 搜索源 '{name}' → {url}")
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
            dict: {success, results: [{title, url, source, note, ...}]}
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

        dbg.log("Search", f"搜索 '{keyword}' via {source} (type={src.get('type', 'html')})")

        try:
            src_type = src.get("type", "html")
            if src_type == "api":
                return self._search_api(keyword, src, source)
            else:
                return self._search_html(keyword, src, source)
        except requests.Timeout:
            dbg.log("Search", f"搜索超时: {source}")
            return {"success": False, "error": f"搜索超时 ({source})"}
        except requests.ConnectionError as e:
            dbg.log("Search", f"连接失败: {source} → {e}")
            return {"success": False, "error": f"无法连接搜索源 ({source}): {e}"}
        except Exception as e:
            dbg.log("Search", f"搜索异常: {source} → {e}")
            return {"success": False, "error": f"搜索异常: {str(e)}"}

    def search_all(self, keyword: str) -> dict:
        """在所有搜索源中搜索，优先自定义源"""
        all_results = []
        errors = []

        # 排序：自定义源（不在 DEFAULT_SOURCES 中的）优先
        custom_sources = [k for k in self.sources if k not in self.DEFAULT_SOURCES]
        default_sources = [k for k in self.sources if k in self.DEFAULT_SOURCES]
        ordered = custom_sources + default_sources

        dbg.log("Search", f"search_all 搜索顺序: {ordered}")

        for source_name in ordered:
            result = self.search(keyword, source_name)
            if result["success"]:
                count = len(result.get("results", []))
                all_results.extend(result.get("results", []))
                dbg.log("Search", f"  {source_name}: 成功, {count} 条结果")
            else:
                err_msg = f"{source_name}: {result.get('error')}"
                errors.append(err_msg)
                dbg.log("Search", f"  {source_name}: 失败 → {result.get('error')}")

        # 去重（按 URL）
        seen = set()
        unique = []
        for r in all_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        dbg.log("Search", f"search_all 汇总: {len(unique)} 条去重结果 (原始 {len(all_results)})")

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

        dbg.log_request("GET", url, params=params)
        t0 = time.time()

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        elapsed_ms = (time.time() - t0) * 1000
        dbg.log_response(resp.status_code, url, body=data, elapsed_ms=elapsed_ms)

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

        dbg.log("Search", f"API result_path='{result_path}' → 类型={type(obj).__name__}, "
                f"keys={list(obj.keys()) if isinstance(obj, dict) else len(obj) if isinstance(obj, list) else 'N/A'}")

        if isinstance(obj, dict):
            # merged_by_type 格式: {"quark": [...], "baidu": [...], ...}
            for type_name, items in obj.items():
                if filter_types and type_name not in filter_types:
                    dbg.log("Search", f"  跳过类型 '{type_name}' ({len(items) if isinstance(items, list) else '?'} 条)")
                    continue
                if not isinstance(items, list):
                    continue
                dbg.log("Search", f"  解析类型 '{type_name}': {len(items)} 条")
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
                            "note": note,
                        }
                        if source_tag:
                            entry["upstream"] = source_tag
                        results.append(entry)
        elif isinstance(obj, list):
            # 平铺列表格式
            dbg.log("Search", f"  解析列表: {len(obj)} 条")
            for item in obj:
                url_val = item.get("url", "")
                note = item.get("note", item.get("title", "")).strip()
                if url_val:
                    results.append({
                        "title": note or "未知资源",
                        "url": url_val,
                        "source": source_name,
                        "password": item.get("password", ""),
                        "note": note,
                    })

        dbg.log("Search", f"API 搜索完成: {len(results)} 条结果")

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

        timeout = 10 if source_name in self.DEFAULT_SOURCES else 15

        dbg.log_request("GET", url)
        t0 = time.time()

        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        elapsed_ms = (time.time() - t0) * 1000
        dbg.log_response(resp.status_code, url,
                         body=f"(HTML {len(html)} chars)",
                         elapsed_ms=elapsed_ms)

        # 提取链接
        links = re.findall(src.get("link_pattern", ""), html)
        # 提取标题
        titles = re.findall(src.get("title_pattern", ""), html)

        dbg.log("Search", f"HTML 正则提取: {len(links)} 个链接, {len(titles)} 个标题")

        if not links:
            links = re.findall(r"https?://pan\.quark\.cn/s/[a-zA-Z0-9]+", html)
            dbg.log("Search", f"通用正则兜底: {len(links)} 个链接")

        results = []
        seen = set()
        for i, link in enumerate(links):
            if link in seen:
                continue
            seen.add(link)
            title = titles[i].strip() if i < len(titles) else f"资源 {i + 1}"
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            title = re.sub(r"<[^>]+>", "", title)
            results.append({
                "title": title,
                "url": link,
                "source": source_name,
                "note": title,
            })

        dbg.log("Search", f"HTML 搜索完成: {len(results)} 条结果")

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
