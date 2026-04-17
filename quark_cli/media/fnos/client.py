"""
fnOS 同步 HTTP 客户端 - 基于 requests，与 quark-cli 风格一致
"""

import json as json_mod
import os
import time
from typing import Any, Dict, List, Optional

import requests

from quark_cli import debug as dbg
from quark_cli.media.fnos.auth import AuthManager
from quark_cli.media.fnos.config import FnosConfig, DEFAULT_API_KEY


class FnosApiError(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
        super().__init__("API Error [{}]: {}".format(code, msg))


class FnosClient:
    """fnOS 影视 API 同步客户端"""

    def __init__(self, config):
        # type: (FnosConfig) -> None
        self._config = config
        self._auth = AuthManager(api_key=config.api_key)
        if config.token:
            self._auth.set_token(config.token)
        self._session = requests.Session()
        self._session.verify = False
        self._session.timeout = config.timeout

    def _request(
        self,
        method,       # type: str
        path,         # type: str
        authenticated=True,  # type: bool
        params=None,  # type: Optional[Dict]
        data=None,    # type: Optional[Dict]
    ):
        # type: (...) -> Any
        url = "{}{}".format(self._config.api_base, path)
        sign_path = "/v{}".format(path)

        headers = self._auth.get_auth_headers(
            method=method, url_path=sign_path, params=params, data=data
        )
        if not authenticated:
            headers.pop("Authorization", None)

        kwargs = {"headers": headers}
        if params:
            kwargs["params"] = params
        if data is not None:
            kwargs["json"] = data

        dbg.log_request(method, url, params=params, body=data)
        t0 = time.time()

        resp = self._session.request(method, url, **kwargs)
        elapsed_ms = (time.time() - t0) * 1000

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        dbg.log_response(resp.status_code, url, body=body, elapsed_ms=elapsed_ms)
        resp.raise_for_status()

        if isinstance(body, dict):
            code = body.get("code", 0)
            if code == -2:
                raise FnosApiError(-2, "Token 过期，请重新登录 (quark-cli media login)")
            if code != 0:
                raise FnosApiError(code, body.get("msg", "unknown error"))
            return body.get("data")
        return body

    def get(self, path, authenticated=True, params=None):
        return self._request("GET", path, authenticated=authenticated, params=params)

    def post(self, path, authenticated=True, data=None):
        return self._request("POST", path, authenticated=authenticated, data=data)

    def delete(self, path, authenticated=True, data=None):
        return self._request("DELETE", path, authenticated=authenticated, data=data)

    # ── 认证 ──

    def login(self, username, password):
        # type: (str, str) -> str
        payload = {"username": username, "password": password, "app_name": "trimemedia-web"}
        result = self.post("/api/v1/login", authenticated=False, data=payload)
        token = result.get("token", "") if isinstance(result, dict) else ""
        self._auth.set_token(token)
        self._config.token = token
        return token

    def get_system_config(self):
        data = self.get("/api/v1/sys/config")
        return data if isinstance(data, dict) else {}

    def get_user_info(self):
        data = self.get("/api/v1/user/info")
        return data if isinstance(data, dict) else {}

    # ── 媒体库 ──

    def get_mediadb_list(self):
        data = self.get("/api/v1/mediadb/list")
        if isinstance(data, list):
            return data
        return data.get("list", []) if isinstance(data, dict) else []

    def get_mediadb_sum(self):
        data = self.get("/api/v1/mediadb/sum")
        return data if isinstance(data, dict) else {}

    # ── 影片 ──

    def get_item_list(
        self,
        ancestor_guid="",
        page_size=50,
        page_num=1,
        types=None,
    ):
        _types = types or ["TV", "Movie", "Directory", "Video"]
        payload = {
            "ancestor_guid": ancestor_guid,
            "page_size": page_size,
            "page": page_num,
            "tags": {"type": _types},
        }
        data = self.post("/api/v1/item/list", data=payload)
        return data if isinstance(data, dict) else {"list": [], "total": 0}

    def search_items(
        self,
        keyword="",
        page_size=20,
        page_num=1,
        ancestor_guid="",
        types=None,
    ):
        """客户端侧关键字过滤搜索"""
        kw = (keyword or "").strip()
        if not kw:
            return {"list": [], "total": 0}

        kw_lower = kw.lower()
        fetch_size = 100
        scan_page = 1
        total_all = None
        max_pages = None
        matches = []

        while True:
            resp = self.get_item_list(
                ancestor_guid=ancestor_guid,
                page_size=fetch_size,
                page_num=scan_page,
                types=types,
            )
            items = resp.get("list", [])
            if total_all is None:
                total_all = int(resp.get("total", 0) or 0)
                max_pages = (total_all + fetch_size - 1) // fetch_size if total_all else 0

            for item in items:
                hay = "{} {}".format(item.get("title", ""), item.get("name", "")).strip()
                if kw in hay or kw_lower in hay.lower():
                    matches.append(item)

            if not items:
                break
            if max_pages is not None and scan_page >= max_pages:
                break
            scan_page += 1

        start = max(0, (page_num - 1) * page_size)
        end = start + page_size
        return {"list": matches[start:end], "total": len(matches)}

    def get_item_detail(self, guid):
        data = self.get("/api/v1/item/{}".format(guid))
        return data if isinstance(data, dict) else {}

    # ── 季 & 剧集 ──

    def get_season_list(self, guid):
        data = self.get("/api/v1/season/list/{}".format(guid))
        return data if isinstance(data, list) else []

    def get_episode_list(self, guid):
        data = self.get("/api/v1/episode/list/{}".format(guid))
        return data if isinstance(data, list) else []

    # ── 播放记录 ──

    def get_play_list(self):
        data = self.get("/api/v1/play/list")
        if isinstance(data, list):
            return data
        return data.get("list", []) if isinstance(data, dict) else []

    def delete_play_record(self, item_guid):
        self.delete("/api/v1/play/record", data={"item_guid": item_guid})

    # ── 演职人员 ──

    def get_person_list(self, guid):
        data = self.post("/api/v1/person/list/{}".format(guid), data={})
        return data if isinstance(data, dict) else {"list": []}

    # ── 图片 ──

    def get_image_url(self, image_path):
        # type: (str) -> str
        """
        根据 API 返回的图片路径构造完整 URL。

        图片路径示例: "/ee/12/RXFg9Y...webp"
        完整 URL:     "{base_url}/v/api/v1/sys/img/ee/12/RXFg9Y...webp"
        """
        if not image_path:
            return ""
        # 去掉开头的斜杠（img_base 已以 / 结尾或不结尾都要兼容）
        path = image_path.lstrip("/")
        return "{}/{}".format(self._config.img_base, path)

    def _image_auth_headers(self, image_path):
        # type: (str) -> Dict[str, str]
        """为图片请求生成认证 header (authx + Authorization)"""
        sign_path = "/v/api/v1/sys/img/{}".format(image_path.lstrip("/"))
        return self._auth.get_auth_headers(
            method="GET", url_path=sign_path, params=None, data=None,
        )

    def fetch_image(self, image_path):
        # type: (str) -> tuple
        """
        带认证获取图片二进制内容。
        返回 (content_bytes, content_type)
        """
        if not image_path:
            return b"", ""
        url = self.get_image_url(image_path)
        headers = self._image_auth_headers(image_path)

        dbg.log_request("GET", url)
        t0 = time.time()

        resp = self._session.get(url, headers=headers, allow_redirects=True)
        elapsed_ms = (time.time() - t0) * 1000

        dbg.log_response(
            resp.status_code, url,
            body="<binary {} bytes>".format(len(resp.content)),
            elapsed_ms=elapsed_ms,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        return resp.content, content_type

    def download_image(self, url, output_path=""):
        # type: (str, str) -> bytes
        """下载图片，支持保存到文件。自动带认证 header。"""
        from pathlib import Path

        # 从完整 URL 中提取图片路径用于签名
        img_base = self._config.img_base
        if url.startswith(img_base):
            relative_path = url[len(img_base):]
            headers = self._image_auth_headers(relative_path)
        else:
            # fallback: 仍然尝试带 token
            headers = {"Authorization": self._auth.token} if self._auth.token else {}

        dbg.log_request("GET", url)
        t0 = time.time()

        resp = self._session.get(url, headers=headers, allow_redirects=True)
        elapsed_ms = (time.time() - t0) * 1000

        dbg.log_response(resp.status_code, url, body="<binary {} bytes>".format(len(resp.content)), elapsed_ms=elapsed_ms)
        resp.raise_for_status()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(resp.content)

        return resp.content
