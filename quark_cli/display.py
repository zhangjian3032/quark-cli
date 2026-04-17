"""
CLI 输出格式化工具
"""

import json as _json
import sys
import unicodedata
from datetime import datetime


# ── 全局 JSON 输出模式 ──

_JSON_MODE = False
_JSON_BUFFER = []  # 收集 JSON 模式下的结构化数据


def set_json_mode(enabled=True):
    global _JSON_MODE
    _JSON_MODE = enabled


def is_json_mode():
    return _JSON_MODE


def json_out(data):
    """JSON 模式下直接输出数据并退出，或收集到 buffer"""
    if _JSON_MODE:
        print(_json.dumps(data, ensure_ascii=False, indent=2))


def json_append(item):
    """收集一条记录到 JSON buffer"""
    _JSON_BUFFER.append(item)


def json_flush():
    """输出收集的 JSON buffer"""
    if _JSON_MODE and _JSON_BUFFER:
        print(_json.dumps(_JSON_BUFFER, ensure_ascii=False, indent=2))
        _JSON_BUFFER.clear()


# ── 字符串显示宽度计算（CJK 字符占 2 列）──

def _display_width(s):
    """计算字符串在终端中的显示宽度"""
    w = 0
    for ch in s:
        cat = unicodedata.east_asian_width(ch)
        if cat in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def _pad(text, width):
    """将 text 填充到指定显示宽度（右填空格）"""
    dw = _display_width(text)
    if dw >= width:
        return text
    return text + " " * (width - dw)


def _truncate_display(text, max_width):
    """按显示宽度截断字符串"""
    w = 0
    result = []
    for ch in text:
        cat = unicodedata.east_asian_width(ch)
        cw = 2 if cat in ("W", "F") else 1
        if w + cw > max_width:
            break
        result.append(ch)
        w += cw
    return "".join(result)


# ── ANSI 颜色码 ──

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def colorize(text, color):
    if _JSON_MODE:
        return text  # JSON 模式不输出颜色
    if not color:
        return text
    return "{}{}{}".format(color, text, Color.RESET)


def success(msg):
    if _JSON_MODE:
        return
    print(colorize("  \u2714 {}".format(msg), Color.GREEN))


def error(msg):
    if _JSON_MODE:
        json_out({"error": msg})
        return
    print(colorize("  \u2716 {}".format(msg), Color.RED), file=sys.stderr)


def warning(msg):
    if _JSON_MODE:
        return
    print(colorize("  \u26a0 {}".format(msg), Color.YELLOW))


def info(msg):
    if _JSON_MODE:
        return
    print(colorize("  \u2139 {}".format(msg), Color.CYAN))


def header(msg):
    if _JSON_MODE:
        return
    width = max(_display_width(msg) + 6, 50)
    print()
    print(colorize("=" * width, Color.BOLD + Color.BLUE))
    print(colorize("   {}".format(msg), Color.BOLD + Color.WHITE))
    print(colorize("=" * width, Color.BOLD + Color.BLUE))
    print()


def subheader(msg):
    if _JSON_MODE:
        return
    print(colorize("\n\u2500\u2500 {} \u2500\u2500".format(msg), Color.BOLD + Color.CYAN))


def kvline(key, value, key_width=14):
    if _JSON_MODE:
        return
    print("  {}  {}".format(colorize(_pad(key, key_width), Color.DIM), value))


def divider():
    if _JSON_MODE:
        return
    print(colorize("  " + "\u2500" * 46, Color.DIM))


def table_header(cols, widths):
    """打印表头（使用显示宽度对齐）"""
    if _JSON_MODE:
        return
    line = "  "
    for col, w in zip(cols, widths):
        line += colorize(_pad(col, w), Color.BOLD + Color.CYAN)
    print(line)
    total_w = sum(widths)
    print("  " + colorize("\u2500" * total_w, Color.DIM))


def table_row(vals, widths, colors=None):
    """打印表行（使用显示宽度对齐）"""
    if _JSON_MODE:
        return
    line = "  "
    for i, (val, w) in enumerate(zip(vals, widths)):
        text = str(val)
        # 按显示宽度截断
        if _display_width(text) > w - 1:
            text = _truncate_display(text, w - 2) + ".."
        text = _pad(text, w)
        if colors and i < len(colors) and colors[i]:
            text = colorize(text, colors[i])
        line += text
    print(line)


def file_icon(item):
    """根据文件类型返回图标"""
    if item.get("dir") or item.get("file_type") == 0:
        return "\U0001f4c1"
    cat = item.get("obj_category", "")
    icons = {
        "video": "\U0001f3ac",
        "image": "\U0001f5bc ",
        "audio": "\U0001f3b5",
        "doc": "\U0001f4c4",
        "archive": "\U0001f4e6",
    }
    return icons.get(cat, "\U0001f4c3")


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes is None:
        return "-"
    size_bytes = int(size_bytes)
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return "{:.1f}{}".format(size, units[i])


def format_time(ts):
    """格式化时间戳（毫秒）"""
    if not ts:
        return "-"
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        return str(ts)
    except Exception:
        return str(ts)


def progress_bar(current, total, width=30):
    """进度条"""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return "[{}] {:.1f}%".format(bar, pct * 100)
