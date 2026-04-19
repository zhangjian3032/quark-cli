"""资源搜索 + 分享转存 API 路由"""

from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(tags=["search"])


@router.get("/search/query")
def search_query(
    keyword: str = Query(..., min_length=1),
    source: str = Query(None, description="搜索源名称，不传则搜索全部"),
):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.search(keyword, source=source)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/sources")
def search_sources():
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        return svc.list_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/check")
def share_check(url: str = Query(..., min_length=5)):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_check(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/list")
def share_list(url: str = Query(..., min_length=5)):
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_list(url)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/subdir")
def share_subdir(
    url: str = Query(..., min_length=5),
    pdir_fid: str = Query(..., min_length=1),
):
    """列出分享链接中某个子目录的文件"""
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        result = svc.share_subdir(url, pdir_fid)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share/save")
def share_save(data: dict = Body(...)):
    """
    转存分享链接
    Body: {url, save_path, password?,
           fid_list?, fid_token_list?,
           rename_pattern?, rename_replace?}
    """
    from quark_cli.web.deps import get_search_service
    url = data.get("url", "")
    save_path = data.get("save_path", "")
    password = data.get("password", "")
    fid_list = data.get("fid_list")
    fid_token_list = data.get("fid_token_list")
    rename_pattern = data.get("rename_pattern", "")
    rename_replace = data.get("rename_replace", "")

    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    if not save_path:
        raise HTTPException(status_code=400, detail="缺少 save_path 参数")

    try:
        svc = get_search_service()
        result = svc.share_save(
            url, save_path, password=password,
            fid_list=fid_list, fid_token_list=fid_token_list,
            rename_pattern=rename_pattern, rename_replace=rename_replace,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 正则重命名 ──

@router.get("/rename/presets")
def rename_presets():
    """获取可用的正则预设和魔法变量"""
    from quark_cli.web.deps import get_search_service
    try:
        svc = get_search_service()
        return svc.rename_presets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename/preview")
def rename_preview(data: dict = Body(...)):
    """预览正则替换效果 (不实际操作)

    Body: {url, pattern, replace}
    """
    from quark_cli.web.deps import get_search_service
    url = data.get("url", "")
    pattern = data.get("pattern", "")
    replace = data.get("replace", "")

    if not url:
        raise HTTPException(status_code=400, detail="缺少 url 参数")
    if not pattern and not replace:
        raise HTTPException(status_code=400, detail="缺少 pattern 或 replace 参数")

    try:
        svc = get_search_service()
        result = svc.rename_preview(url, pattern, replace)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 批量转存 ──

@router.post("/batch-save")
def batch_save(data: dict = Body(...)):
    """
    批量搜索+转存多部影视

    Body: {
        names: ["流浪地球2", "三体", ...],
        media_type?: "movie" | "tv",
        base_path?: "/媒体",
        max_attempts?: 10,
        dry_run?: false
    }
    """
    from quark_cli.web.deps import get_config_path
    from quark_cli.config import ConfigManager
    from quark_cli.api import QuarkAPI
    from quark_cli.search import PanSearch
    from quark_cli.media.autosave import auto_save_pipeline, filter_quark_links, rank_results

    names = data.get("names", [])
    media_type = data.get("media_type", "movie")
    base_path = data.get("base_path", "/媒体")
    max_attempts = data.get("max_attempts", 10)
    dry_run = data.get("dry_run", False)

    if not names:
        raise HTTPException(status_code=400, detail="缺少 names 参数")
    if len(names) > 50:
        raise HTTPException(status_code=400, detail="单次最多 50 部")

    config_path = get_config_path()
    cfg = ConfigManager(config_path)
    cfg.load()

    search_engine = PanSearch(config=cfg)

    # TMDB 源 (可选)
    tmdb_source = None
    try:
        from quark_cli.web.deps import get_tmdb_source
        tmdb_source = get_tmdb_source()
    except Exception:
        pass

    # 夸克客户端
    quark_client = None
    if not dry_run:
        cookies = cfg.data.get("cookies", [])
        if not cookies:
            raise HTTPException(status_code=400, detail="未配置夸克 Cookie")
        quark_client = QuarkAPI(cookies[0])
        account = quark_client.init()
        if not account:
            raise HTTPException(status_code=400, detail="夸克 Cookie 无效或过期")

    results = []
    for name in names:
        keywords = [name]
        save_path = ""

        # TMDB 元数据
        if tmdb_source:
            try:
                from quark_cli.media.discovery.naming import suggest_search_keywords, suggest_save_path
                sr = tmdb_source.search(name, media_type=media_type, page=1)
                if not sr.items:
                    alt = "tv" if media_type == "movie" else "movie"
                    sr = tmdb_source.search(name, media_type=alt, page=1)
                if sr.items:
                    first = sr.items[0]
                    detail = tmdb_source.get_detail(first.source_id, media_type)
                    keywords = suggest_search_keywords(detail)
                    paths = suggest_save_path(detail, base_path=base_path)
                    if paths:
                        save_path = paths[0]["path"]
            except Exception:
                pass

        if not save_path:
            type_folder = "电影" if media_type == "movie" else "剧集"
            save_path = "/{}/{}/{}".format(base_path.strip("/"), type_folder, name)

        if dry_run:
            all_results = []
            for kw in keywords:
                sr = search_engine.search_all(kw)
                if sr.get("success") and sr.get("results"):
                    all_results.extend(sr["results"])
            quark_results = filter_quark_links(all_results)
            ranked = rank_results(quark_results, keywords)
            results.append({
                "name": name,
                "candidates": len(quark_results),
                "top_score": ranked[0].get("score", 0) if ranked else 0,
                "save_path": save_path,
                "dry_run": True,
            })
        else:
            try:
                pr = auto_save_pipeline(
                    quark_client=quark_client,
                    search_engine=search_engine,
                    keywords=keywords,
                    save_path=save_path,
                    max_attempts=max_attempts,
                    media_title=name,
                    media_type=media_type,
                )
                results.append({
                    "name": name,
                    "success": pr.get("success", False),
                    "saved_count": pr.get("saved_count", 0),
                    "save_path": save_path,
                    "attempts": pr.get("attempts", 0),
                    "error": pr.get("error", ""),
                })
            except Exception as e:
                results.append({
                    "name": name,
                    "success": False,
                    "error": str(e),
                    "save_path": save_path,
                })

    ok_count = sum(1 for r in results if r.get("success"))
    return {
        "total": len(names),
        "success_count": ok_count,
        "fail_count": len(names) - ok_count,
        "dry_run": dry_run,
        "results": results,
    }
