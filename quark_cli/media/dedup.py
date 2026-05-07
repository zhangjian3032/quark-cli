"""
飞牛影视媒体库 — 同名多版本去重检测模块

功能:
  扫描飞牛影视媒体库中的所有影片, 找出同一影片的多个画质版本,
  按画质评分排序, 辅助用户决定保留哪个版本。

去重策略:
  1. 按 (标准化标题, 年份) 分组
  2. 对同组内的每个条目, 从 extra 字段中提取文件名/画质信息
  3. 使用 parser 模块解析分辨率/编码/来源/HDR 等标签
  4. 计算综合画质评分, 输出排序后的重复组

使用方式:
  from quark_cli.media.dedup import find_duplicates, DuplicateGroup
  groups = find_duplicates(provider, library_guid="xxx")
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from quark_cli.media.base import MediaItem, MediaProvider
from quark_cli.media.parser import ParsedMedia, parse_filename


# ═══════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════


@dataclass
class DuplicateEntry:
    """重复组中的单个条目"""
    item: MediaItem
    parsed: Optional[ParsedMedia] = None
    quality_score: float = 0.0
    size_bytes: int = 0
    is_best: bool = False  # 是否为推荐保留版本

    @property
    def quality_summary(self) -> str:
        """画质摘要字符串"""
        if not self.parsed:
            return "未知"
        return self.parsed.tags_str or "未识别"

    @property
    def size_human(self) -> str:
        """人类可读的文件大小"""
        if self.size_bytes <= 0:
            return "未知"
        gb = self.size_bytes / (1024 ** 3)
        if gb >= 1:
            return "{:.1f} GB".format(gb)
        mb = self.size_bytes / (1024 ** 2)
        return "{:.0f} MB".format(mb)


@dataclass
class DuplicateGroup:
    """一组重复的影片"""
    key: str                      # 分组 key: "标题 (年份)"
    title: str                    # 标准化标题
    year: str                     # 年份
    media_type: str               # Movie / TV
    entries: List[DuplicateEntry] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def best(self) -> Optional[DuplicateEntry]:
        """推荐保留的最佳版本"""
        for e in self.entries:
            if e.is_best:
                return e
        return self.entries[0] if self.entries else None

    @property
    def removable(self) -> List[DuplicateEntry]:
        """可考虑移除的版本 (非最佳)"""
        return [e for e in self.entries if not e.is_best]

    @property
    def total_size(self) -> int:
        """所有版本总占用空间"""
        return sum(e.size_bytes for e in self.entries)

    @property
    def saveable_size(self) -> int:
        """移除冗余版本可节省的空间"""
        best = self.best
        if not best:
            return 0
        return sum(e.size_bytes for e in self.entries if not e.is_best)

    def to_dict(self) -> dict:
        """序列化为可输出的 dict"""
        return {
            "key": self.key,
            "title": self.title,
            "year": self.year,
            "media_type": self.media_type,
            "count": self.count,
            "total_size": self.total_size,
            "saveable_size": self.saveable_size,
            "entries": [
                {
                    "guid": e.item.guid,
                    "title": e.item.title,
                    "quality": e.quality_summary,
                    "score": e.quality_score,
                    "size": e.size_human,
                    "size_bytes": e.size_bytes,
                    "is_best": e.is_best,
                }
                for e in self.entries
            ],
        }


# ═══════════════════════════════════════════
#  标题标准化
# ═══════════════════════════════════════════

# 匹配标题中的画质/版本标签 — 去掉这些才能正确分组
_QUALITY_TAGS_RE = re.compile(
    r"[\[\(（【]?"
    r"(?:2160[pP]|4[kK]|1080[pPiI]|720[pP]|480[pP]|"
    r"Remux|BDRemux|BluRay|Blu-Ray|WEB-DL|WEBDL|WEBRip|HDTV|HDRip|BDRip|"
    r"HEVC|H\.?265|[xX]265|H\.?264|[xX]264|AVC|AV1|"
    r"HDR10\+?|Dolby\s*Vision|DoVi|DV|HDR|HLG|"
    r"Atmos|TrueHD|DTS-HD|DTS|EAC3|DDP|DD[P+]?|AC3|AAC|FLAC|"
    r"中字|中文字幕|内封|双语|简繁)"
    r"[\]\)）】]?",
    re.IGNORECASE,
)

# 匹配制作组标签
_GROUP_SUFFIX_RE = re.compile(r"[-@][A-Za-z0-9][A-Za-z0-9\-_.]{1,30}$")

# 匹配常见分隔符/多余空白
_SEPARATORS_RE = re.compile(r"[\.\-_]+")


def normalize_title(title: str) -> str:
    """
    标准化影片标题, 用于分组匹配。

    处理:
      - 去除画质/编码标签
      - 去除制作组后缀
      - Unicode 标准化 (全角→半角)
      - 统一大小写
      - 去除多余空白和标点
    """
    if not title:
        return ""

    # Unicode NFKC 标准化 (全角字符→半角)
    s = unicodedata.normalize("NFKC", title)

    # 去除画质标签
    s = _QUALITY_TAGS_RE.sub(" ", s)

    # 去除制作组后缀
    s = _GROUP_SUFFIX_RE.sub("", s)

    # 分隔符转空格
    s = _SEPARATORS_RE.sub(" ", s)

    # 去除括号中的年份 (已由 year 字段处理)
    s = re.sub(r"[\(（]\s*(?:19|20)\d{2}\s*[\)）]", " ", s)

    # 统一小写、去首尾空白、压缩连续空格
    s = s.lower().strip()
    s = re.sub(r"\s{2,}", " ", s)

    return s


# ═══════════════════════════════════════════
#  画质评分
# ═══════════════════════════════════════════

# 分辨率分值
_RESOLUTION_SCORES = {
    "2160p": 100, "4k": 100, "4K": 100,
    "1080p": 70, "1080i": 65, "1080P": 70,
    "720p": 40, "720P": 40, "720i": 38,
    "576p": 20, "480p": 10,
}

# 来源分值
_SOURCE_SCORES = {
    "bdremux": 100, "remux": 95,
    "uhdbd": 90, "uhd": 85,
    "bluray": 80, "blu-ray": 80,
    "bdrip": 70,
    "web-dl": 60, "webdl": 60,
    "webrip": 50,
    "hdtv": 40, "hdrip": 35,
    "dvdrip": 20,
}

# 编码分值
_CODEC_SCORES = {
    "hevc": 30, "av1": 28, "avc": 15,
}

# HDR 分值
_HDR_SCORES = {
    "dolby vision": 40, "dovi": 40, "dv": 35,
    "hdr10+": 30, "hdr10": 25, "hdr": 20, "hlg": 15,
}

# 音频分值
_AUDIO_SCORES = {
    "atmos": 30, "truehd": 25, "dts-hd.ma": 22, "dts-hd ma": 22,
    "dts-hd": 20, "dts": 15, "eac3": 12, "ddp": 10, "dd+": 10,
    "dd": 8, "ac3": 7, "flac": 6, "aac": 4,
}


def calc_quality_score(parsed: ParsedMedia) -> float:
    """
    计算综合画质评分 (0~300+)

    权重:
      - 分辨率: 最重要
      - 来源: 次重要
      - HDR: 加分项
      - 编码: 加分项
      - 音频: 加分项
      - 文件大小: 参考加分
    """
    score = 0.0

    # 分辨率
    if parsed.resolution:
        score += _RESOLUTION_SCORES.get(parsed.resolution.lower(), 0)

    # 来源
    if parsed.source:
        score += _SOURCE_SCORES.get(parsed.source.lower(), 0)

    # 编码
    if parsed.codec:
        score += _CODEC_SCORES.get(parsed.codec.lower(), 0)

    # HDR
    if parsed.hdr:
        score += _HDR_SCORES.get(parsed.hdr.lower(), 0)

    # 音频
    if parsed.audio:
        score += _AUDIO_SCORES.get(parsed.audio.lower(), 0)

    # 文件大小加分 (越大一般画质越好, 但权重低)
    size_gb = parsed.size / (1024 ** 3) if parsed.size else 0
    if size_gb >= 50:
        score += 25
    elif size_gb >= 20:
        score += 20
    elif size_gb >= 8:
        score += 15
    elif size_gb >= 2:
        score += 8
    elif size_gb > 0:
        score += 3

    return round(score, 1)


# ═══════════════════════════════════════════
#  核心去重函数
# ═══════════════════════════════════════════

def find_duplicates(
    provider: MediaProvider,
    library_guid: str = "",
    min_group_size: int = 2,
    page_size: int = 100,
) -> List[DuplicateGroup]:
    """
    扫描媒体库, 找出同名多版本影片。

    Args:
        provider: MediaProvider 实例 (已登录)
        library_guid: 指定媒体库 GUID (空=扫描所有库)
        min_group_size: 最少几个版本才算重复 (默认 2)
        page_size: 分页大小

    Returns:
        重复组列表, 按可节省空间降序排列
    """
    # Step 1: 收集所有影片
    all_items = _collect_all_items(provider, library_guid, page_size)

    # Step 2: 按标准化标题+年份分组
    groups_map = {}  # key → [MediaItem, ...]
    for item in all_items:
        norm_title = normalize_title(item.title)
        if not norm_title:
            continue
        # 用标题+年份组合作为 key
        key = "{}|{}".format(norm_title, item.year or "")
        if key not in groups_map:
            groups_map[key] = []
        groups_map[key].append(item)

    # Step 3: 只保留有多个版本的组
    duplicate_groups = []
    for key, items in groups_map.items():
        if len(items) < min_group_size:
            continue

        # 从 key 恢复信息
        parts = key.split("|", 1)
        norm_title = parts[0]
        year = parts[1] if len(parts) > 1 else ""

        # 使用第一个 item 的原始标题作为展示用标题
        display_title = items[0].title

        group = DuplicateGroup(
            key=key,
            title=display_title,
            year=year,
            media_type=items[0].media_type or "Movie",
        )

        # Step 4: 解析每个条目的画质信息并评分
        for item in items:
            # 尝试从 extra 中获取文件名和文件大小
            file_name = _extract_filename(item)
            file_size = _extract_file_size(item)

            # 如果没有独立文件名, 用影片标题来解析
            parse_target = file_name if file_name else item.title
            parsed = parse_filename(parse_target, file_size)

            quality_score = calc_quality_score(parsed)

            entry = DuplicateEntry(
                item=item,
                parsed=parsed,
                quality_score=quality_score,
                size_bytes=file_size,
            )
            group.entries.append(entry)

        # Step 5: 按评分排序, 标记最佳版本
        group.entries.sort(key=lambda e: e.quality_score, reverse=True)
        if group.entries:
            group.entries[0].is_best = True

        duplicate_groups.append(group)

    # 按可节省空间降序排列
    duplicate_groups.sort(key=lambda g: g.saveable_size, reverse=True)

    return duplicate_groups


def _collect_all_items(
    provider: MediaProvider,
    library_guid: str,
    page_size: int,
) -> List[MediaItem]:
    """遍历所有媒体库, 收集全部影片"""
    all_items = []

    if library_guid:
        guids = [library_guid]
    else:
        libs = provider.get_libraries()
        guids = [lib.guid for lib in libs]

    for guid in guids:
        page = 1
        while True:
            result = provider.get_items(
                library_guid=guid,
                page=page,
                page_size=page_size,
            )
            if not result.items:
                break
            all_items.extend(result.items)
            if len(result.items) < page_size:
                break
            page += 1

    return all_items


def _extract_filename(item: MediaItem) -> str:
    """
    从 MediaItem.extra 中提取源文件名。
    fnOS API 可能在 extra 中包含 file_name / filename / path 等字段。
    """
    extra = item.extra or {}

    # 尝试多种可能的字段名
    for key in ("file_name", "filename", "original_filename", "path"):
        val = extra.get(key, "")
        if val and isinstance(val, str):
            # 如果是路径, 取最后一段
            if "/" in val:
                val = val.rsplit("/", 1)[-1]
            return val

    return ""


def _extract_file_size(item: MediaItem) -> int:
    """从 MediaItem.extra 中提取文件大小"""
    extra = item.extra or {}

    for key in ("size", "file_size", "total_size"):
        val = extra.get(key)
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass

    return 0


# ═══════════════════════════════════════════
#  输出格式化
# ═══════════════════════════════════════════

def format_report(groups: List[DuplicateGroup], verbose: bool = False) -> str:
    """
    格式化去重检测报告

    Args:
        groups: find_duplicates() 返回的重复组列表
        verbose: 是否显示详细信息

    Returns:
        格式化的文本报告
    """
    if not groups:
        return "未发现重复影片。"

    lines = []
    total_saveable = sum(g.saveable_size for g in groups)

    lines.append("=" * 60)
    lines.append("  飞牛影视 — 同名多版本去重检测报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append("  发现 {} 组重复影片, 可节省空间: {:.1f} GB".format(
        len(groups), total_saveable / (1024 ** 3)
    ))
    lines.append("")

    for idx, group in enumerate(groups, 1):
        lines.append("-" * 50)
        year_str = " ({})".format(group.year) if group.year else ""
        lines.append("#{} {}{} — {} 个版本".format(
            idx, group.title, year_str, group.count
        ))

        for i, entry in enumerate(group.entries):
            marker = " ★ 推荐保留" if entry.is_best else " ✗ 可移除"
            lines.append("  [{}] {} | 评分: {:.0f} | 大小: {}{}".format(
                i + 1,
                entry.quality_summary,
                entry.quality_score,
                entry.size_human,
                marker,
            ))
            if verbose:
                lines.append("      GUID: {}".format(entry.item.guid))
                lines.append("      标题: {}".format(entry.item.title))

        if group.saveable_size > 0:
            lines.append("  → 可节省: {:.1f} GB".format(
                group.saveable_size / (1024 ** 3)
            ))
        lines.append("")

    lines.append("=" * 60)
    lines.append("  总计可节省: {:.1f} GB".format(total_saveable / (1024 ** 3)))
    lines.append("=" * 60)

    return "\n".join(lines)
