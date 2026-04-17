"""
fnOS authx 签名算法
"""

import hashlib
import json
import random
import time
import urllib.parse
from typing import Any, Dict, Optional

SIGNATURE_SALT = "NDzZTVxnRKP8Z0jXg1VAMonaG8akvh"


def _md5(data: str) -> str:
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def _hash_signature_data(data: str = "") -> str:
    try:
        fixed = data.replace("%", "%25") if "%" in data else data
        decoded = urllib.parse.unquote(fixed)
        return _md5(decoded)
    except Exception:
        return _md5(data)


def _stringify_params(params: Dict[str, Any]) -> str:
    sorted_keys = sorted(params.keys())
    parts = []
    for key in sorted_keys:
        value = params[key]
        if value is not None:
            encoded_key = urllib.parse.quote(str(key), safe="")
            encoded_value = urllib.parse.quote(str(value), safe="")
            parts.append(f"{encoded_key}={encoded_value}")
    return "&".join(parts)


def generate_signature(
    method: str,
    url_path: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    api_key: str = "",
) -> str:
    """生成 fnOS authx 签名字符串"""
    is_get = method.upper() == "GET"
    url_clean = url_path.split("?")[0]
    url_query = {}
    if "?" in url_path:
        query_string = url_path.split("?", 1)[1]
        url_query = dict(urllib.parse.parse_qsl(query_string))

    if is_get:
        merged_params = {**(params or {}), **url_query}
        content_str = _stringify_params(merged_params)
    else:
        content_str = (
            json.dumps(data, separators=(",", ":"), ensure_ascii=False) if data else ""
        )

    content_hash = _hash_signature_data(content_str)
    nonce = str(random.randint(100000, 999999)).zfill(6)
    timestamp = str(int(time.time() * 1000))

    sign_parts = [SIGNATURE_SALT, url_clean, nonce, timestamp, content_hash, api_key]
    sign_raw = "_".join(sign_parts)
    sign = _md5(sign_raw)

    return f"nonce={nonce}&timestamp={timestamp}&sign={sign}"


class AuthManager:
    """fnOS 认证管理器"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.token = ""

    def set_token(self, token: str):
        self.token = token

    def get_auth_headers(
        self,
        method: str,
        url_path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        headers = {}
        authx = generate_signature(
            method=method,
            url_path=url_path,
            params=params,
            data=data,
            api_key=self.api_key,
        )
        headers["authx"] = authx
        if self.token:
            headers["Authorization"] = self.token
        return headers
