"""
媒体文件名解析与智能选择模块

功能:
  1. 从网盘分享的杂乱文件名中提取: 年份、分辨率、编码、集数、语言等
  2. 智能选择最佳文件 (最大的视频文件 / 最匹配的版本)
  3. 根据 TMDB 元数据 + 原始标签 生成规范文件名

命名规范:
  电影: {title} ({year})/{title} ({year}) [{resolution}] [{codec}].{ext}
  剧集: {title} ({year})/Season {season}/{title} - S{season}E{episode} [{resolution}].{ext}
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional, List


# ═══════════════════════════════════════════
#  视频文件扩展名
# ═══════════════════════════════════════════

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".rmvb", ".rm", ".flv", ".wmv",
    ".mov", ".ts", ".m2ts", ".mpg", ".mpeg", ".vob",
    ".iso", ".bdmv", ".3gp", ".webm", ".m4v", ".f4v",
}

SUBTITLE_EXTENSIONS = {
    ".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt",
}

# ═══════════════════════════════════════════
#  正则表达式库
# ═══════════════════════════════════════════

# 年份: (2023), [2023], .2023., 2023
RE_YEAR = re.compile(
    r"(?:[\(\[\.\s])((?:19|20)\d{2})(?:[\)\]\.\s]|$)"
)

# 分辨率
RE_RESOLUTION = re.compile(
    r"\b(2160[pP]|4[kK]|1080[pPiI]|720[pPiI]|480[pP]|576[pP])\b"
)

# 编码
RE_CODEC = re.compile(
    r"\b(H\.?265|[xX]\.?265|HEVC|H\.?264|[xX]\.?264|AVC|AV1|VP9|MPEG-?[24])\b",
    re.IGNORECASE,
)

# 音频编码 — findall，按优先级排列
RE_AUDIO_ALL = re.compile(
    r"\b(Atmos|TrueHD\d*\.?\d?|DTS-HD\.?MA|DTS-HD|DTS"
    r"|EAC3|DDP\d*\.?\d?|DD[P+]?\d*\.?\d?|AC3|AAC|FLAC|LPCM)\b",
    re.IGNORECASE,
)

# 音频优先级 (越大越好)
_AUDIO_PRIORITY = {
    "atmos": 100, "truehd": 90, "dts-hd.ma": 85, "dts-hd ma": 85,
    "dts-hd": 80, "dts": 70, "eac3": 60, "ddp": 55, "dd+": 55,
    "dd": 50, "ac3": 45, "flac": 40, "aac": 30, "lpcm": 25,
}

# HDR — findall，HDR10+ 在前防止被 HDR10 先吃掉
RE_HDR_ALL = re.compile(
    r"\b(HDR10\+|Dolby\s*Vision|DoVi|HDR10|HDR|HLG|DV)(?=[\.\s\-_\]\)]|$)",
    re.IGNORECASE,
)

# HDR 优先级
_HDR_PRIORITY = {
    "dolby vision": 100, "dovi": 100, "dv": 90,
    "hdr10+": 80, "hdr10": 70, "hdr": 60, "hlg": 50,
}

# 来源/版本 — findall，按优先级排序取最佳
RE_SOURCE_ALL = re.compile(
    r"\b(BDRemux|Remux|Blu-?Ray|BluRay|UHDBD|UHD|BDRip|WEB-?DL|WEBRip|HDTV|HDRip|DVDRip)\b",
    re.IGNORECASE,
)

# 来源优先级
_SOURCE_PRIORITY = {
    "bdremux": 100, "remux": 95,
    "uhdbd": 90, "uhd": 75,
    "bluray": 80, "blu-ray": 80,
    "bdrip": 70,
    "web-dl": 60, "webdl": 60,
    "webrip": 50,
    "hdtv": 40, "hdrip": 35,
    "dvdrip": 20,
}

# 剧集编号: S01E02, S1E2
RE_EPISODE_SE = re.compile(
    r"[sS](\d{1,2})\s*[eE](\d{1,4})"
)

RE_EPISODE_E_ONLY = re.compile(
    r"(?:^|[\.\s\-_\[])(?:EP?)(\d{1,4})(?:[\.\s\-_\]]|$)",
    re.IGNORECASE,
)

RE_EPISODE_CN = re.compile(
    r"第\s*(\d{1,4})\s*[集话期]"
)

RE_EPISODE_RANGE = re.compile(
    r"(?:[eE][pP]?|第?)(\d{1,4})\s*[-~至]\s*(?:[eE][pP]?|第?)(\d{1,4})",
    re.IGNORECASE,
)

# 季度: Season 1, S01, 第一季, 第1季
RE_SEASON = re.compile(
    r"(?:[sS](?:eason\s*)?(\d{1,2}))"
)

RE_SEASON_CN = re.compile(
    r"第\s*([一二三四五六七八九十百\d]+)\s*季"
)

_CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
}

# 字幕标签
RE_SUBTITLE_TAG = re.compile(
    r"(中[英日韩]双语|[简繁]中|中[字幕]|内[封嵌]|[简繁]体|双语字幕|中文字幕|字幕组)",
    re.IGNORECASE,
)

# 制作组 / 发布标签 — 通常在末尾 [-GroupName] 或 @GroupName
RE_GROUP = re.compile(
    r"[-@]([A-Za-z0-9][A-Za-z0-9\-_.]{1,30})(?:\.[a-zA-Z]{2,4})?$"
)


# ═══════════════════════════════════════════
#  解析结果
# ═══════════════════════════════════════════

@dataclass
class ParsedMedia:
    """媒体文件名解析结果"""
    original: str = ""              # 原始文件名
    ext: str = ""                   # 扩展名 (.mkv)
    is_video: bool = False
    is_subtitle: bool = False

    year: Optional[int] = None
    resolution: Optional[str] = None     # "2160p", "1080p" 等
    codec: Optional[str] = None          # "HEVC", "AVC" 等
    audio: Optional[str] = None          # 最佳音频: "Atmos", "TrueHD" 等
    audio_all: List[str] = field(default_factory=list)  # 所有音频标签
    hdr: Optional[str] = None            # 最佳 HDR: "HDR10+", "DV" 等
    hdr_all: List[str] = field(default_factory=list)    # 所有 HDR 标签
    source: Optional[str] = None         # 最佳来源: "Remux", "BluRay" 等

    season: Optional[int] = None
    episode: Optional[int] = None
    episode_end: Optional[int] = None    # 合集: E01-E12 → episode=1, episode_end=12
    is_collection: bool = False          # 是否合集/全集

    subtitle_tags: List[str] = field(default_factory=list)
    group: Optional[str] = None

    # 用于评分
    size: int = 0                        # 文件大小 (bytes)

    @property
    def resolution_priority(self) -> int:
        """分辨率优先级 (越大越好)"""
        mapping = {
            "2160p": 90, "4k": 90, "4K": 90,
            "1080p": 70, "1080i": 65, "1080P": 70,
            "720p": 40, "720P": 40, "720i": 38,
            "576p": 20, "480p": 10,
        }
        return mapping.get(self.resolution or "", 0)

    @property
    def source_priority(self) -> int:
        """来源优先级"""
        return _SOURCE_PRIORITY.get((self.source or "").lower(), 0)

    @property
    def tags_str(self) -> str:
        """组合标签字符串"""
        parts = []
        if self.resolution:
            parts.append(_normalize_resolution(self.resolution))
        if self.source:
            parts.append(self.source)
        if self.codec:
            parts.append(self.codec)
        if self.hdr:
            parts.append(self.hdr)
        if self.audio:
            parts.append(self.audio)
        return " ".join(parts) if parts else ""


# ═══════════════════════════════════════════
#  解析函数
# ═══════════════════════════════════════════

def _pick_best(matches, priority_map):
    """从匹配列表中按优先级选最佳项"""
    if not matches:
        return None
    best = None
    best_pri = -1
    for m in matches:
        pri = priority_map.get(m.lower().replace(" ", ""), 0)
        if pri > best_pri:
            best = m
            best_pri = pri
    return best or matches[0]


def parse_filename(filename: str, file_size: int = 0) -> ParsedMedia:
    """
    解析单个文件名，提取媒体元信息。

    Args:
        filename: 文件名 (含扩展名)
        file_size: 文件大小 (bytes)，可选

    Returns:
        ParsedMedia
    """
    result = ParsedMedia(original=filename, size=file_size)

    # 扩展名
    base, ext = os.path.splitext(filename)
    result.ext = ext.lower()
    result.is_video = result.ext in VIDEO_EXTENSIONS
    result.is_subtitle = result.ext in SUBTITLE_EXTENSIONS

    text = base

    # 年份
    m = RE_YEAR.search(text)
    if m:
        result.year = int(m.group(1))

    # 分辨率
    m = RE_RESOLUTION.search(text)
    if m:
        result.resolution = m.group(1)

    # 编码
    m = RE_CODEC.search(text)
    if m:
        raw = m.group(1)
        normalized = raw.upper().replace(".", "")
        if normalized in ("H265", "X265", "HEVC"):
            result.codec = "HEVC"
        elif normalized in ("H264", "X264", "AVC"):
            result.codec = "AVC"
        else:
            result.codec = raw

    # 音频 — 收集所有匹配, 选优先级最高的
    audio_matches = RE_AUDIO_ALL.findall(text)
    if audio_matches:
        result.audio_all = audio_matches
        result.audio = _pick_best(audio_matches, _AUDIO_PRIORITY)

    # HDR — 收集所有匹配, 选优先级最高的
    hdr_matches = RE_HDR_ALL.findall(text)
    if hdr_matches:
        result.hdr_all = hdr_matches
        result.hdr = _pick_best(hdr_matches, _HDR_PRIORITY)

    # 来源 — 收集所有匹配, 选优先级最高的
    source_matches = RE_SOURCE_ALL.findall(text)
    if source_matches:
        result.source = _pick_best(source_matches, _SOURCE_PRIORITY)

    # 季度
    m = RE_SEASON.search(text)
    if m:
        result.season = int(m.group(1))
    else:
        m = RE_SEASON_CN.search(text)
        if m:
            cn = m.group(1)
            result.season = _CN_NUM_MAP.get(cn) or _try_parse_int(cn)

    # 集数
    m = RE_EPISODE_RANGE.search(text)
    if m:
        result.episode = int(m.group(1))
        result.episode_end = int(m.group(2))
        result.is_collection = True
    else:
        m = RE_EPISODE_SE.search(text)
        if m:
            if result.season is None:
                result.season = int(m.group(1))
            result.episode = int(m.group(2))
        else:
            m = RE_EPISODE_CN.search(text)
            if m:
                result.episode = int(m.group(1))
            else:
                m = RE_EPISODE_E_ONLY.search(text)
                if m:
                    result.episode = int(m.group(1))

    # 判断合集
    if re.search(r"(全\d+集|全集|合集|完结|E\d+-E\d+|EP\d+-EP\d+)", text, re.IGNORECASE):
        result.is_collection = True

    # 字幕标签
    for m in RE_SUBTITLE_TAG.finditer(text):
        result.subtitle_tags.append(m.group(1))

    # 制作组
    m = RE_GROUP.search(text)
    if m:
        result.group = m.group(1)

    return result


def _try_parse_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════
#  智能文件选择
# ═══════════════════════════════════════════

def select_best_files(
    file_list: list,
    media_type: str = "movie",
    prefer_resolution: str = "",
) -> list:
    """
    从分享链接的文件列表中智能选择最佳文件。

    策略:
      - 电影: 选最大的单个视频文件 (排除样片/预告/花絮)
      - 剧集: 选所有剧集文件 (按集数排序)

    Args:
        file_list: 夸克分享详情中的 file list
            每个 item: {"fid": str, "file_name": str, "size": int, "file": bool, "dir": bool, ...}
        media_type: "movie" 或 "tv"
        prefer_resolution: 偏好分辨率 ("4k", "1080p", "720p"), 空=自动

    Returns:
        选中的文件列表 (已排序), 每个文件附加 parsed: ParsedMedia
    """
    # 递归收集所有文件 (扁平化子目录)
    all_files = _flatten_files(file_list)

    # 解析所有文件名
    for f in all_files:
        f["parsed"] = parse_filename(f.get("file_name", ""), f.get("size", 0))

    # 只保留视频文件
    videos = [f for f in all_files if f["parsed"].is_video]
    if not videos:
        # 没有识别到视频扩展名 → 退回按大小排序
        videos = [f for f in all_files if f.get("file", True) and f.get("size", 0) > 50 * 1024 * 1024]

    if not videos:
        return []

    # 排除样片/预告/花絮
    videos = _filter_junk_videos(videos)

    if media_type == "movie":
        return _select_movie(videos, prefer_resolution)
    else:
        return _select_tv(videos, prefer_resolution)


def _flatten_files(file_list: list) -> list:
    """扁平化: 如果列表中只有一个文件夹, 展开其内容"""
    result = []
    for f in file_list:
        if f.get("dir"):
            children = f.get("children", [])
            if children:
                result.extend(_flatten_files(children))
            else:
                result.append(f)
        else:
            result.append(f)
    return result


def _filter_junk_videos(videos: list) -> list:
    """过滤样片/预告/花絮/广告"""
    junk_patterns = re.compile(
        r"(?:sample|trailer|preview|花絮|预告|彩蛋|幕后|featurette|extra|bonus|interview|deleted)"
        r"|(?:\.txt$|\.nfo$|\.jpg$|\.png$)",
        re.IGNORECASE,
    )
    filtered = [v for v in videos if not junk_patterns.search(v.get("file_name", ""))]
    return filtered or videos


def _select_movie(videos: list, prefer_resolution: str) -> list:
    """电影: 选最佳单文件"""

    def movie_score(f):
        p = f["parsed"]
        score = 0

        # 文件大小 (核心指标)
        size_gb = f.get("size", 0) / (1024 ** 3)
        if size_gb >= 20:
            score += 90
        elif size_gb >= 8:
            score += 75
        elif size_gb >= 2:
            score += 50
        elif size_gb >= 0.5:
            score += 25
        else:
            score += 5

        # 分辨率
        score += p.resolution_priority * 0.5
        # 来源
        score += p.source_priority * 0.3
        # 偏好分辨率
        if prefer_resolution and p.resolution:
            if prefer_resolution.lower() in p.resolution.lower():
                score += 30
        # 合集扣分
        if p.is_collection:
            score -= 50
        # 有集数扣分
        if p.episode is not None:
            score -= 30

        return score

    videos.sort(key=movie_score, reverse=True)
    return [videos[0]] if videos else []


def _select_tv(videos: list, prefer_resolution: str) -> list:
    """剧集: 选所有有效集数文件, 按集数排序"""
    episodic = [v for v in videos if v["parsed"].episode is not None]

    if episodic:
        best_per_ep = {}
        for v in episodic:
            ep = v["parsed"].episode
            if ep not in best_per_ep or v.get("size", 0) > best_per_ep[ep].get("size", 0):
                best_per_ep[ep] = v
        return sorted(best_per_ep.values(), key=lambda v: v["parsed"].episode or 0)

    return sorted(videos, key=lambda v: v.get("size", 0), reverse=True)


# ═══════════════════════════════════════════
#  规范化重命名
# ═══════════════════════════════════════════

def generate_rename(
    parsed: ParsedMedia,
    title: str,
    year: Optional[int] = None,
    media_type: str = "movie",
    season: Optional[int] = None,
) -> str:
    """
    根据解析结果和 TMDB 元数据生成规范文件名。

    电影: {title} ({year}) [2160p BluRay HEVC HDR10].mkv
    剧集: {title} - S01E03 [1080p WEB-DL HEVC].mkv
    """
    ext = parsed.ext or ".mkv"

    # 标签
    tags = []
    if parsed.resolution:
        tags.append(_normalize_resolution(parsed.resolution))
    if parsed.source:
        tags.append(parsed.source)
    if parsed.codec:
        tags.append(parsed.codec)
    if parsed.hdr:
        tags.append(parsed.hdr)
    if parsed.audio:
        tags.append(parsed.audio)

    tag_str = " ".join(tags)
    tag_part = " [{}]".format(tag_str) if tag_str else ""

    # 年份
    use_year = year or parsed.year
    year_part = " ({})".format(use_year) if use_year else ""

    if media_type == "movie":
        return "{title}{year}{tags}{ext}".format(
            title=_safe_filename(title),
            year=year_part,
            tags=tag_part,
            ext=ext,
        )
    else:
        s = season if season is not None else (parsed.season or 1)
        e = parsed.episode

        if e is not None:
            if parsed.episode_end is not None and parsed.episode_end > e:
                ep_str = "S{:02d}E{:02d}-E{:02d}".format(s, e, parsed.episode_end)
            else:
                ep_str = "S{:02d}E{:02d}".format(s, e)
        else:
            ep_str = "S{:02d}".format(s)

        return "{title}{year} - {ep}{tags}{ext}".format(
            title=_safe_filename(title),
            year=year_part,
            ep=ep_str,
            tags=tag_part,
            ext=ext,
        )


def generate_save_dir(
    title: str,
    year: Optional[int] = None,
    media_type: str = "movie",
    season: Optional[int] = None,
    base_path: str = "/媒体",
) -> str:
    """
    生成保存目录路径。

    电影: /媒体/电影/{title} ({year})/
    剧集: /媒体/剧集/{title} ({year})/Season {season}/
    """
    safe_title = _safe_filename(title)
    year_part = " ({})".format(year) if year else ""

    if media_type == "movie":
        return "{base}/电影/{title}{year}".format(
            base=base_path.rstrip("/"),
            title=safe_title,
            year=year_part,
        )
    else:
        s = season or 1
        return "{base}/剧集/{title}{year}/Season {season:02d}".format(
            base=base_path.rstrip("/"),
            title=safe_title,
            year=year_part,
            season=s,
        )


def _normalize_resolution(res: str) -> str:
    """标准化分辨率"""
    r = res.lower().strip()
    if r in ("4k",):
        return "2160p"
    if r.endswith("i"):
        return r[:-1] + "p"
    return r


def _safe_filename(name: str) -> str:
    """清理文件名中不合法的字符"""
    cleaned = re.sub(r'[/\\:*?"<>|]', '', name)
    cleaned = cleaned.strip(" .")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned or "Unknown"
