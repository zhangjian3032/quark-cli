"""
media auto-save 自动搜索转存引擎

流程:
  1. 名称 → (可选) TMDB 元数据查询 → 生成搜索关键词和保存路径
  2. 搜索网盘资源 → 找到夸克链接 → 智能排序 (名称匹配度/大小/画质)
  3. 逐个检查链接有效性 → 转存到目标路径 (最大尝试 N 个)
"""

import re
import os
from quark_cli import debug as dbg


# ── 资源评分引擎 ──

# 画质关键词权重 (越高越好)
_QUALITY_KEYWORDS = {
    # 顶级
    "remux":    100,
    "bdremux":  100,
    "uhd":      95,
    "2160p":    90,
    "4k":       90,
    # 高清
    "1080p":    70,
    "bluray":   65,
    "blu-ray":  65,
    "bdrip":    60,
    "webdl":    55,
    "web-dl":   55,
    "webrip":   50,
    # 中等
    "720p":     40,
    "hdtv":     35,
    "hdrip":    30,
    # 低质
    "480p":     10,
    "ts":       5,
    "cam":      2,
    "枪版":      1,
}

# 编码加分
_CODEC_BONUS = {
    "hevc":   10,
    "h265":   10,
    "h.265":  10,
    "x265":   10,
    "hdr":    8,
    "dolby":  6,
    "atmos":  6,
    "dts":    5,
    "truehd": 5,
    "aac":    2,
}

# 中文字幕加分
_SUB_BONUS = {
    "中字":   15,
    "中文字幕": 15,
    "内嵌":   10,
    "简繁":   10,
    "双语":   8,
    "内封":   8,
}


def _extract_size_gb(title):
    """从标题中提取文件大小 (GB), 未找到返回 0"""
    # 匹配 "12.5G", "2.3GB", "800M", "800MB" 等
    m = re.search(r"(\d+(?:\.\d+)?)\s*(GB|G|TB|T)\b", title, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        unit = m.group(2).upper()
        if unit in ("TB", "T"):
            return val * 1024
        return val

    m = re.search(r"(\d+(?:\.\d+)?)\s*(MB|M)\b", title, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return val / 1024.0

    return 0


def _calc_name_match_score(title, keywords):
    """计算标题与搜索关键词的匹配度 (0~100)"""
    title_lower = title.lower()
    best_score = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            # 完全包含: 基础 60 分
            score = 60
            # 越短的标题匹配到 → 相关性越高
            ratio = len(kw) / max(len(title), 1)
            score += int(ratio * 40)
            best_score = max(best_score, score)
        else:
            # 逐词匹配
            kw_parts = re.split(r"[\s\-_\.]+", kw_lower)
            matched = sum(1 for p in kw_parts if p and p in title_lower)
            if kw_parts:
                ratio = matched / len(kw_parts)
                score = int(ratio * 50)
                best_score = max(best_score, score)
    return best_score


def _calc_quality_score(title):
    """计算画质评分 (0~100)"""
    title_lower = title.lower().replace(" ", "")
    score = 0
    for kw, pts in _QUALITY_KEYWORDS.items():
        if kw in title_lower:
            score = max(score, pts)
    return score


def _calc_codec_bonus(title):
    """计算编码加分 (0~50)"""
    title_lower = title.lower().replace(" ", "")
    bonus = 0
    for kw, pts in _CODEC_BONUS.items():
        if kw in title_lower:
            bonus += pts
    return min(bonus, 50)


def _calc_sub_bonus(title):
    """计算字幕加分 (0~15)"""
    bonus = 0
    for kw, pts in _SUB_BONUS.items():
        if kw in title:
            bonus += pts
    return min(bonus, 15)


def score_resource(result, keywords):
    """
    对单个搜索结果进行综合评分。

    Args:
        result: dict with 'title', 'url', etc.
        keywords: list[str] 搜索关键词列表

    Returns:
        dict: result 原字典附加 'score', 'score_detail' 字段
    """
    title = result.get("title", "") or result.get("note", "")

    name_score = _calc_name_match_score(title, keywords)
    quality_score = _calc_quality_score(title)
    size_gb = _extract_size_gb(title)
    codec_bonus = _calc_codec_bonus(title)
    sub_bonus = _calc_sub_bonus(title)

    # 大小评分: 4~80GB 最佳，越大画质越好（大概率）
    if size_gb >= 80:
        size_score = 70  # 合集或超大，可能不是单片
    elif size_gb >= 20:
        size_score = 90  # remux 级
    elif size_gb >= 8:
        size_score = 80  # 高清
    elif size_gb >= 2:
        size_score = 50  # 标清
    elif size_gb > 0:
        size_score = 20  # 过小，质量差
    else:
        size_score = 30  # 未知大小

    # 综合: 名称匹配 40% + 画质 25% + 大小 15% + 编码 10% + 字幕 10%
    total = (
        name_score * 0.40
        + quality_score * 0.25
        + size_score * 0.15
        + codec_bonus * 0.10
        + sub_bonus * 0.10
    )

    result["score"] = round(total, 1)
    result["score_detail"] = {
        "name_match": name_score,
        "quality": quality_score,
        "size_gb": round(size_gb, 2),
        "size_score": size_score,
        "codec_bonus": codec_bonus,
        "sub_bonus": sub_bonus,
    }
    return result


def rank_results(results, keywords):
    """
    对搜索结果列表进行评分排序。

    Returns:
        list: 按 score 降序排列的结果列表
    """
    for r in results:
        score_resource(r, keywords)
    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)


# ── 链接过滤 ──

def filter_quark_links(results):
    """只保留夸克网盘链接"""
    quark_pattern = re.compile(r"https?://pan\.quark\.cn/s/\w+")
    filtered = []
    for r in results:
        url = r.get("url", "")
        if quark_pattern.search(url):
            filtered.append(r)
    return filtered


# ── 自动转存 pipeline ──

def auto_save_pipeline(
    quark_client,
    search_engine,
    keywords,
    save_path,
    pattern=".*",
    replace="",
    max_attempts=10,
    on_progress=None,
):
    """
    自动搜索 + 排序 + 校验 + 转存 流水线。

    Args:
        quark_client:  QuarkAPI 实例 (已登录)
        search_engine: PanSearch 实例
        keywords:      list[str] 搜索关键词列表
        save_path:     str 保存路径 (如 /媒体/电影/科幻/流浪地球2 (2023))
        pattern:       str 正则过滤文件名
        replace:       str 正则替换文件名
        max_attempts:  int 最大尝试链接数
        on_progress:   callable(event, data) 进度回调

    Returns:
        dict: {
            "success": bool,
            "saved_from": str,          # 成功转存的来源链接
            "saved_count": int,         # 转存文件数
            "saved_fids": list,         # 新文件 fid 列表
            "save_path": str,           # 保存路径
            "attempts": int,            # 尝试了多少个链接
            "candidates": list,         # 所有候选 (含 score)
            "errors": list,             # 各候选的失败原因
        }
    """
    def emit(event, data=None):
        if on_progress:
            on_progress(event, data or {})

    # ─ Step 1: 搜索 ─
    emit("search_start", {"keywords": keywords})
    all_results = []
    for kw in keywords:
        dbg.log("AutoSave", "搜索关键词: {}".format(kw))
        result = search_engine.search_all(kw)
        if result.get("success") and result.get("results"):
            all_results.extend(result["results"])

    # 去重 (by URL)
    seen_urls = set()
    unique = []
    for r in all_results:
        u = r.get("url", "")
        if u not in seen_urls:
            seen_urls.add(u)
            unique.append(r)

    # 只保留夸克链接
    quark_results = filter_quark_links(unique)
    emit("search_done", {"total": len(unique), "quark": len(quark_results)})

    if not quark_results:
        return {
            "success": False,
            "error": "未搜索到夸克网盘链接",
            "keywords": keywords,
            "attempts": 0,
            "candidates": [],
            "errors": [],
        }

    # ─ Step 2: 排序 ─
    ranked = rank_results(quark_results, keywords)
    candidates = ranked[:max_attempts]
    emit("rank_done", {"candidates": len(candidates), "top_score": candidates[0].get("score", 0)})

    # ─ Step 3: 逐个尝试 check + save ─
    errors = []
    for idx, candidate in enumerate(candidates):
        url = candidate["url"]
        title = candidate.get("title", "")
        score = candidate.get("score", 0)

        emit("try_start", {"index": idx + 1, "url": url, "title": title, "score": score})
        dbg.log("AutoSave", "[{}/{}] 尝试: {} (score={})".format(idx + 1, len(candidates), url, score))

        try:
            result = _try_save_one(quark_client, url, save_path, pattern, replace)
            if result["success"]:
                emit("save_success", {
                    "index": idx + 1,
                    "url": url,
                    "title": title,
                    "saved_count": result["saved_count"],
                })
                return {
                    "success": True,
                    "saved_from": url,
                    "saved_from_title": title,
                    "saved_from_score": score,
                    "saved_count": result["saved_count"],
                    "saved_fids": result["saved_fids"],
                    "save_path": save_path,
                    "attempts": idx + 1,
                    "candidates": [
                        {"title": c.get("title", ""), "url": c.get("url", ""), "score": c.get("score", 0)}
                        for c in candidates
                    ],
                    "errors": errors,
                }
            else:
                reason = result.get("error", "未知错误")
                errors.append({"url": url, "title": title, "error": reason})
                emit("try_fail", {"index": idx + 1, "url": url, "error": reason})
        except Exception as e:
            reason = str(e)
            errors.append({"url": url, "title": title, "error": reason})
            emit("try_fail", {"index": idx + 1, "url": url, "error": reason})

    emit("all_failed", {"attempts": len(candidates)})
    return {
        "success": False,
        "error": "所有候选链接均不可用 (尝试 {} 个)".format(len(candidates)),
        "save_path": save_path,
        "attempts": len(candidates),
        "candidates": [
            {"title": c.get("title", ""), "url": c.get("url", ""), "score": c.get("score", 0)}
            for c in candidates
        ],
        "errors": errors,
    }


def _try_save_one(quark_client, share_url, save_path, pattern=".*", replace=""):
    """
    尝试从一个分享链接转存。

    Returns:
        dict: {"success": bool, "saved_count": int, "saved_fids": list, "error": str}
    """
    from quark_cli.api import QuarkAPI
    import re as _re

    pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(share_url)
    if not pwd_id:
        return {"success": False, "error": "无法解析链接", "saved_count": 0, "saved_fids": []}

    # check 有效性
    resp = quark_client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        msg = resp.get("message", "链接失效")
        return {"success": False, "error": msg, "saved_count": 0, "saved_fids": []}

    stoken = resp["data"]["stoken"]
    detail = quark_client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        return {"success": False, "error": detail.get("message", "获取详情失败"), "saved_count": 0, "saved_fids": []}

    file_list = detail["data"]["list"]
    if not file_list:
        return {"success": False, "error": "分享中无文件", "saved_count": 0, "saved_fids": []}

    # 若只有一个文件夹，自动进入
    if len(file_list) == 1 and file_list[0].get("dir"):
        sub = quark_client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
        if sub.get("code") == 0 and sub["data"]["list"]:
            file_list = sub["data"]["list"]

    # 正则过滤
    filtered = [f for f in file_list if _re.search(pattern, f.get("file_name", ""))]
    if not filtered:
        return {"success": False, "error": "无匹配文件 (pattern={})".format(pattern), "saved_count": 0, "saved_fids": []}

    # 确保保存目录存在
    save_path_norm = _re.sub(r"/{2,}", "/", "/{}".format(save_path))
    fids = quark_client.get_fids([save_path_norm])
    if fids:
        to_pdir_fid = fids[0]["fid"]
    else:
        mkdir_resp = quark_client.mkdir(save_path_norm)
        if mkdir_resp.get("code") != 0:
            return {"success": False, "error": "创建目录失败: {}".format(mkdir_resp.get("message")), "saved_count": 0, "saved_fids": []}
        to_pdir_fid = mkdir_resp["data"]["fid"]

    # 检查已存在的文件
    dir_resp = quark_client.ls_dir(to_pdir_fid)
    existing = set()
    if dir_resp.get("code") == 0:
        existing = {f["file_name"] for f in dir_resp["data"]["list"]}

    to_save = [f for f in filtered if f.get("file_name", "") not in existing]
    if not to_save:
        # 全部已存在也算成功
        return {"success": True, "saved_count": 0, "saved_fids": [], "note": "文件已存在"}

    # 批量转存
    all_fids = []
    for i in range(0, len(to_save), 100):
        batch = to_save[i:i + 100]
        fid_list = [f["fid"] for f in batch]
        token_list = [f["share_fid_token"] for f in batch]
        save_resp = quark_client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)
        if save_resp.get("code") != 0:
            return {"success": False, "error": "转存失败: {}".format(save_resp.get("message")), "saved_count": 0, "saved_fids": []}
        task_id = save_resp["data"]["task_id"]
        task_resp = quark_client.query_task(task_id)
        if task_resp.get("code") != 0 or task_resp.get("data", {}).get("status") != 2:
            return {"success": False, "error": "转存任务异常", "saved_count": 0, "saved_fids": []}
        new_fids = task_resp["data"]["save_as"]["save_as_top_fids"]
        all_fids.extend(new_fids)

    # 重命名 (可选)
    if replace:
        for idx, f in enumerate(to_save):
            if idx < len(all_fids):
                new_name = _re.sub(pattern, replace, f["file_name"])
                if new_name != f["file_name"]:
                    quark_client.rename(all_fids[idx], new_name)

    return {"success": True, "saved_count": len(all_fids), "saved_fids": all_fids}
