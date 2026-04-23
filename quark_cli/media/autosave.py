"""
media auto-save 自动搜索转存引擎

流程:
  1. 名称 → (可选) TMDB 元数据查询 → 生成搜索关键词和保存路径
  2. 搜索网盘资源 → 找到夸克链接 → 智能排序 (名称匹配度/大小/画质)
  3. 逐个检查链接有效性 → 智能选择最佳文件 → 转存 + 规范重命名
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
            score = 60
            ratio = len(kw) / max(len(title), 1)
            score += int(ratio * 40)
            best_score = max(best_score, score)
        else:
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
    """对单个搜索结果进行综合评分。"""
    title = result.get("title", "") or result.get("note", "")

    name_score = _calc_name_match_score(title, keywords)
    quality_score = _calc_quality_score(title)
    size_gb = _extract_size_gb(title)
    codec_bonus = _calc_codec_bonus(title)
    sub_bonus = _calc_sub_bonus(title)

    if size_gb >= 80:
        size_score = 70
    elif size_gb >= 20:
        size_score = 90
    elif size_gb >= 8:
        size_score = 80
    elif size_gb >= 2:
        size_score = 50
    elif size_gb > 0:
        size_score = 20
    else:
        size_score = 30

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
    """对搜索结果列表进行评分排序。"""
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
    media_title="",
    media_year=None,
    media_type="movie",
):
    """
    自动搜索 + 排序 + 校验 + 智能选择 + 转存 + 重命名 流水线。

    Args:
        quark_client:  QuarkAPI 实例 (已登录)
        search_engine: PanSearch 实例
        keywords:      list[str] 搜索关键词列表
        save_path:     str 保存路径
        pattern:       str 正则过滤文件名 (兼容旧逻辑)
        replace:       str 正则替换文件名 (兼容旧逻辑)
        max_attempts:  int 最大尝试链接数
        on_progress:   callable(event, data) 进度回调
        media_title:   str TMDB 标准标题, 用于智能重命名 (空=不重命名)
        media_year:    int 年份
        media_type:    str "movie" 或 "tv"

    Returns:
        dict with success, saved_from, saved_count, saved_fids, save_path,
        attempts, renamed, candidates, errors
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

    # ─ Step 3: 逐个尝试 ─
    errors = []
    for idx, candidate in enumerate(candidates):
        url = candidate["url"]
        title = candidate.get("title", "")
        score = candidate.get("score", 0)

        emit("try_start", {"index": idx + 1, "url": url, "title": title, "score": score})
        dbg.log("AutoSave", "[{}/{}] 尝试: {} (score={})".format(idx + 1, len(candidates), url, score))

        try:
            result = _try_save_one(
                quark_client, url, save_path,
                pattern=pattern, replace=replace,
                media_title=media_title,
                media_year=media_year,
                media_type=media_type,
            )
            if result["success"]:
                emit("save_success", {
                    "index": idx + 1,
                    "url": url,
                    "title": title,
                    "saved_count": result["saved_count"],
                    "renamed": result.get("renamed", []),
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
                    "renamed": result.get("renamed", []),
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


def _collect_share_files(quark_client, pwd_id, stoken, pdir_fid, max_depth=5):
    """
    递归获取分享链接下所有文件 (展平子目录)。
    解决分享中存在 S01/ 等子文件夹导致文件无法被识别和选择的问题。

    Returns:
        list: 所有非目录文件的列表
    """
    if max_depth <= 0:
        return []

    detail = quark_client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        return []

    items = detail["data"]["list"]
    result = []
    for item in items:
        if item.get("dir"):
            # 递归进入子目录
            sub_files = _collect_share_files(
                quark_client, pwd_id, stoken, item["fid"], max_depth - 1
            )
            result.extend(sub_files)
        else:
            result.append(item)
    return result


def _try_save_one(
    quark_client, share_url, save_path,
    pattern=".*", replace="",
    media_title="", media_year=None, media_type="movie",
):
    """
    尝试从一个分享链接转存。

    智能选择逻辑 (当 media_title 非空时):
      - 电影: 只选最大的视频文件，重命名为规范格式
      - 剧集: 选所有识别到集数的文件，按集数排序重命名

    Returns:
        dict: {"success": bool, "saved_count": int, "saved_fids": list,
               "renamed": list, "error": str}
    """
    from quark_cli.api import QuarkAPI
    import re as _re

    _empty = {"success": False, "saved_count": 0, "saved_fids": [], "renamed": []}

    pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(share_url)
    if not pwd_id:
        return dict(_empty, error="无法解析链接")

    # check 有效性
    resp = quark_client.get_stoken(pwd_id, passcode)
    if resp.get("status") != 200:
        return dict(_empty, error=resp.get("message", "链接失效"))

    stoken = resp["data"]["stoken"]
    detail = quark_client.get_share_detail(pwd_id, stoken, pdir_fid)
    if detail.get("code") != 0:
        return dict(_empty, error=detail.get("message", "获取详情失败"))

    file_list = detail["data"]["list"]
    if not file_list:
        return dict(_empty, error="分享中无文件")

    # 递归展开所有子目录 (解决 S01/ 等嵌套目录结构)
    has_dirs = any(f.get("dir") for f in file_list)
    if has_dirs:
        dbg.log("AutoSave", "分享中包含子目录, 递归展开获取所有文件")
        all_flat_files = []
        for f in file_list:
            if f.get("dir"):
                sub_files = _collect_share_files(
                    quark_client, pwd_id, stoken, f["fid"], max_depth=4
                )
                all_flat_files.extend(sub_files)
            else:
                all_flat_files.append(f)
        if all_flat_files:
            file_list = all_flat_files
            dbg.log("AutoSave", "展开后共 {} 个文件".format(len(file_list)))

    # ── 智能选择 (如果提供了 media_title) ──
    use_smart = bool(media_title)
    rename_plan = []  # [(原始文件名, 新文件名)]

    if use_smart:
        try:
            from quark_cli.media.parser import select_best_files, generate_rename, parse_filename

            selected = select_best_files(file_list, media_type=media_type)
            if not selected:
                dbg.log("AutoSave", "智能选择未找到合适文件, 回退到正则模式")
                use_smart = False
            else:
                for f in selected:
                    parsed = f.get("parsed") or parse_filename(
                        f.get("file_name", ""), f.get("size", 0)
                    )
                    new_name = generate_rename(
                        parsed,
                        title=media_title,
                        year=media_year,
                        media_type=media_type,
                    )
                    rename_plan.append((f.get("file_name", ""), new_name))
                    dbg.log("AutoSave", "选择: {} ({:.1f}MB) → {}".format(
                        f.get("file_name", ""),
                        f.get("size", 0) / 1048576,
                        new_name,
                    ))
                filtered = selected
        except ImportError:
            dbg.log("AutoSave", "media.parser 不可用, 回退到正则模式")
            use_smart = False

    if not use_smart:
        # 旧逻辑: 正则过滤
        filtered = [f for f in file_list if _re.search(pattern, f.get("file_name", ""))]
        if not filtered:
            return dict(_empty, error="无匹配文件 (pattern={})".format(pattern))

    # 确保保存目录存在
    save_path_norm = _re.sub(r"/{2,}", "/", "/{}".format(save_path))
    fids = quark_client.get_fids([save_path_norm])
    if fids:
        to_pdir_fid = fids[0]["fid"]
    else:
        mkdir_resp = quark_client.mkdir(save_path_norm)
        if mkdir_resp.get("code") != 0:
            return dict(_empty, error="创建目录失败: {}".format(mkdir_resp.get("message")))
        to_pdir_fid = mkdir_resp["data"]["fid"]

    # 检查已存在的文件 (原始名和新名都检查)
    dir_resp = quark_client.ls_dir(to_pdir_fid)
    existing = set()
    if dir_resp.get("code") == 0:
        existing = {f["file_name"] for f in dir_resp["data"]["list"]}

    new_names_map = dict(rename_plan) if rename_plan else {}

    to_save = []
    for f in filtered:
        orig_name = f.get("file_name", "")
        if orig_name in existing:
            continue
        new_name = new_names_map.get(orig_name)
        if new_name and new_name in existing:
            continue
        to_save.append(f)

    if not to_save:
        return {"success": True, "saved_count": 0, "saved_fids": [], "renamed": [], "note": "文件已存在"}

    # 批量转存
    all_fids = []
    for i in range(0, len(to_save), 100):
        batch = to_save[i:i + 100]
        fid_list = [f["fid"] for f in batch]
        token_list = [f["share_fid_token"] for f in batch]
        save_resp = quark_client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)
        if save_resp.get("code") != 0:
            return dict(_empty, error="转存失败: {}".format(save_resp.get("message")))
        task_id = save_resp["data"]["task_id"]
        task_resp = quark_client.query_task(task_id)
        if task_resp.get("code") != 0 or task_resp.get("data", {}).get("status") != 2:
            return dict(_empty, error="转存任务异常")
        new_fids = task_resp["data"]["save_as"]["save_as_top_fids"]
        all_fids.extend(new_fids)

    # ── 重命名 ──
    renamed_results = []

    if use_smart and rename_plan:
        for idx, f in enumerate(to_save):
            if idx < len(all_fids):
                orig_name = f.get("file_name", "")
                new_name = new_names_map.get(orig_name)
                if new_name and new_name != orig_name:
                    try:
                        quark_client.rename(all_fids[idx], new_name)
                        renamed_results.append({"from": orig_name, "to": new_name})
                        dbg.log("AutoSave", "重命名: {} → {}".format(orig_name, new_name))
                    except Exception as e:
                        dbg.log("AutoSave", "重命名失败: {} — {}".format(new_name, e))
    elif replace:
        for idx, f in enumerate(to_save):
            if idx < len(all_fids):
                new_name = _re.sub(pattern, replace, f["file_name"])
                if new_name != f["file_name"]:
                    try:
                        quark_client.rename(all_fids[idx], new_name)
                        renamed_results.append({"from": f["file_name"], "to": new_name})
                    except Exception:
                        pass

    return {
        "success": True,
        "saved_count": len(all_fids),
        "saved_fids": all_fids,
        "renamed": renamed_results,
    }
