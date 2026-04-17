"""
Debug 日志模块 - 统一管理全局 debug 输出
"""

import sys
import json
import time
from typing import Any, Optional

# 全局 debug 开关
_debug_enabled = False


def set_debug(enabled: bool):
    """设置全局 debug 开关"""
    global _debug_enabled
    _debug_enabled = enabled


def is_debug() -> bool:
    return _debug_enabled


def log(tag: str, message: str, data: Any = None):
    """打印 debug 日志"""
    if not _debug_enabled:
        return
    ts = time.strftime("%H:%M:%S")
    prefix = f"\033[35m[DEBUG {ts}]\033[0m \033[36m[{tag}]\033[0m"
    print(f"{prefix} {message}", file=sys.stderr)
    if data is not None:
        _print_data(data)


def log_request(method: str, url: str, params: dict = None, body: Any = None):
    """打印 HTTP 请求"""
    if not _debug_enabled:
        return
    ts = time.strftime("%H:%M:%S")
    prefix = f"\033[35m[DEBUG {ts}]\033[0m"
    print(f"{prefix} \033[33m→ {method} {url}\033[0m", file=sys.stderr)
    if params:
        print(f"{prefix}   params: {_compact_json(params)}", file=sys.stderr)
    if body:
        print(f"{prefix}   body: {_compact_json(body)}", file=sys.stderr)


def log_response(status_code: int, url: str, body: Any = None, elapsed_ms: float = 0):
    """打印 HTTP 响应"""
    if not _debug_enabled:
        return
    ts = time.strftime("%H:%M:%S")
    prefix = f"\033[35m[DEBUG {ts}]\033[0m"
    color = "\033[32m" if 200 <= status_code < 300 else "\033[31m"
    elapsed_str = f" ({elapsed_ms:.0f}ms)" if elapsed_ms else ""
    print(f"{prefix} {color}← {status_code}{elapsed_str}\033[0m {url}", file=sys.stderr)
    if body is not None:
        _print_data(body, max_length=2000)


def _compact_json(obj: Any) -> str:
    """将对象转为紧凑 JSON 字符串"""
    try:
        if isinstance(obj, str):
            return obj[:500]
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))[:500]
    except (TypeError, ValueError):
        return str(obj)[:500]


def _print_data(data: Any, max_length: int = 2000):
    """打印数据内容，自动截断"""
    try:
        if isinstance(data, (dict, list)):
            text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            text = str(data)

        if len(text) > max_length:
            text = text[:max_length] + f"\n  ... (truncated, total {len(text)} chars)"

        for line in text.split("\n"):
            print(f"         {line}", file=sys.stderr)
    except Exception:
        print(f"         {str(data)[:500]}", file=sys.stderr)
