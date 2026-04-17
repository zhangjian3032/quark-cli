"""
CLI 输出格式化工具
"""

import sys
from datetime import datetime


# ANSI 颜色码
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


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Color.RESET}"


def success(msg: str):
    print(colorize(f"  ✔ {msg}", Color.GREEN))


def error(msg: str):
    print(colorize(f"  ✖ {msg}", Color.RED), file=sys.stderr)


def warning(msg: str):
    print(colorize(f"  ⚠ {msg}", Color.YELLOW))


def info(msg: str):
    print(colorize(f"  ℹ {msg}", Color.CYAN))


def header(msg: str):
    width = max(len(msg) + 6, 50)
    print()
    print(colorize("=" * width, Color.BOLD + Color.BLUE))
    print(colorize(f"   {msg}", Color.BOLD + Color.WHITE))
    print(colorize("=" * width, Color.BOLD + Color.BLUE))
    print()


def subheader(msg: str):
    print(colorize(f"\n── {msg} ──", Color.BOLD + Color.CYAN))


def kvline(key: str, value: str, key_width: int = 14):
    print(f"  {colorize(key.ljust(key_width), Color.DIM)}  {value}")


def divider():
    print(colorize("  " + "─" * 46, Color.DIM))


def table_header(cols: list, widths: list):
    """打印表头"""
    line = "  "
    for col, w in zip(cols, widths):
        line += colorize(col.ljust(w), Color.BOLD + Color.CYAN)
    print(line)
    print("  " + colorize("─" * sum(widths), Color.DIM))


def table_row(vals: list, widths: list, colors: list = None):
    """打印表行"""
    line = "  "
    for i, (val, w) in enumerate(zip(vals, widths)):
        text = str(val)[:w - 1].ljust(w)
        if colors and i < len(colors) and colors[i]:
            text = colorize(text, colors[i])
        line += text
    print(line)


def file_icon(item: dict) -> str:
    """根据文件类型返回图标"""
    if item.get("dir") or item.get("file_type") == 0:
        return "📁"
    cat = item.get("obj_category", "")
    icons = {
        "video": "🎬",
        "image": "🖼 ",
        "audio": "🎵",
        "doc": "📄",
        "archive": "📦",
    }
    return icons.get(cat, "📃")


def format_size(size_bytes) -> str:
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
    return f"{size:.1f}{units[i]}"


def format_time(ts) -> str:
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


def progress_bar(current: int, total: int, width: int = 30) -> str:
    """进度条"""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:.1f}%"
