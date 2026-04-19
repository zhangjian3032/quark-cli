"""
media 子命令处理模块 - 影视媒体中心操作
支持 fnOS / Emby / Jellyfin 等多种 Provider
支持 TMDB 元数据查询与高分影视推荐
"""

import json
import sys

from quark_cli.display import (
    Color, colorize, success, error, warning, info,
    header, subheader, kvline, divider, table_header, table_row,
    format_size, format_time,
    is_json_mode, json_out,
)
from quark_cli.media.base import MediaProvider, MediaProviderError


# ──────────────────────────────────────────────
# Provider 创建辅助
# ──────────────────────────────────────────────

def _get_media_config(args):
    """从 quark-cli 统一配置中加载 media 配置段"""
    from quark_cli.commands.helpers import get_config
    cfg = get_config(args)
    return cfg.data.get("media", {})


def _save_media_config(args, media_cfg):
    """保存 media 配置到 quark-cli 统一配置（确保先加载完整配置再写入）"""
    from quark_cli.commands.helpers import get_config
    cfg = get_config(args)
    data = cfg.data  # 触发 load(), 确保已有配置（cookie 等）被加载
    data["media"] = media_cfg
    cfg.save()


def _get_provider(args):
    """根据配置创建 Media Provider 实例"""
    from quark_cli.media.registry import create_provider

    media_cfg = _get_media_config(args)
    provider_name = media_cfg.get("provider", "fnos")

    if provider_name == "fnos":
        from quark_cli.media.fnos.config import FnosConfig
        fnos_data = media_cfg.get("fnos", {})
        config = FnosConfig.from_dict(fnos_data)
        config = FnosConfig.from_env(config)
        config.validate()
        return create_provider("fnos", config)
    else:
        raise ValueError("未知的 media provider: {}".format(provider_name))


def _get_tmdb_source(args):
    """根据配置创建 TMDB 数据源实例"""
    from quark_cli.media.discovery.tmdb import TmdbSource, TmdbError

    media_cfg = _get_media_config(args)
    discovery_cfg = media_cfg.get("discovery", {})
    api_key = discovery_cfg.get("tmdb_api_key", "")

    if not api_key:
        raise TmdbError(0, "TMDB API Key 未配置。请运行:\n  quark-cli media config --tmdb-key <your_key>\n\n  获取方式: https://www.themoviedb.org/settings/api")

    language = discovery_cfg.get("language", "zh-CN")
    region = discovery_cfg.get("region", "CN")

    return TmdbSource(api_key=api_key, language=language, region=region)


def _get_douban_source():
    """创建豆瓣数据源实例 (无需配置)"""
    from quark_cli.media.discovery.douban import DoubanSource
    return DoubanSource()


def _get_discovery_source(args, source_name="auto"):
    """
    根据 source 名称创建数据源实例。
    source_name: "auto" / "tmdb" / "douban"
    返回 (source_instance, actual_source_name)
    """
    if source_name == "douban":
        return _get_douban_source(), "douban"
    elif source_name == "tmdb":
        from quark_cli.media.discovery.tmdb import TmdbError
        try:
            return _get_tmdb_source(args), "tmdb"
        except TmdbError:
            raise
    else:
        # auto: 优先 TMDB, 无 key 回退豆瓣
        try:
            src = _get_tmdb_source(args)
            return src, "tmdb"
        except Exception:
            info("TMDB 不可用，自动切换到豆瓣数据源")
            return _get_douban_source(), "douban"


def _looks_like_guid(value):
    v = (value or "").strip()
    if len(v) != 32:
        return False
    return all(c in "0123456789abcdef" for c in v.lower())


def _resolve_guid(provider, name_or_guid):
    """如果传入的不是 GUID 则按名称搜索"""
    raw = name_or_guid.strip()
    if _looks_like_guid(raw):
        return raw
    result = provider.search_items(keyword=raw, page=1, page_size=50)
    if not result.items:
        raise MediaProviderError(-6, "未找到名称包含 '{}' 的影片".format(raw))
    exact = next((it for it in result.items if it.title.strip() == raw), None)
    chosen = exact or result.items[0]
    info("根据名称 '{}' 匹配到影片 GUID: {}".format(raw, chosen.guid))
    return chosen.guid


def _item_to_dict(item):
    """将 MediaItem 转为 JSON 可序列化的 dict"""
    return {
        "guid": item.guid,
        "title": item.title,
        "year": item.year or "",
        "rating": item.rating,
        "media_type": item.media_type or "",
        "original_title": getattr(item, "original_title", ""),
        "overview": getattr(item, "overview", ""),
    }


# ──────────────────────────────────────────────
# 子命令实现
# ──────────────────────────────────────────────

def _handle_login(args):
    """media login"""
    media_cfg = _get_media_config(args)
    provider_name = media_cfg.get("provider", "fnos")

    if provider_name == "fnos":
        from quark_cli.media.fnos.config import FnosConfig, _normalize_host_port_ssl

        fnos_data = media_cfg.get("fnos", {})
        config = FnosConfig.from_dict(fnos_data)

        if getattr(args, "host", None):
            config.host = args.host
        if getattr(args, "port", None):
            config.port = args.port

        config.host, config.port, config.ssl = _normalize_host_port_ssl(
            config.host, config.port, config.ssl
        )

        if not config.host:
            error("请指定 NAS 地址: --host <ip/域名>")
            sys.exit(1)

        username = getattr(args, "username", None)
        password = getattr(args, "password", None)
        if not username:
            error("请指定用户名: -u <username>")
            sys.exit(1)
        if not password:
            import getpass
            password = getpass.getpass("密码: ")

        from quark_cli.media.fnos.client import FnosClient, FnosApiError
        client = FnosClient(config)
        try:
            token = client.login(username, password)
        except FnosApiError as e:
            error("登录失败: {}".format(e.msg))
            sys.exit(1)
        except Exception as e:
            error("连接失败: {}".format(e))
            info("目标地址: {}".format(config.base_url))
            sys.exit(1)

        config.token = token
        fnos_data = config.to_dict()
        media_cfg["provider"] = "fnos"
        media_cfg["fnos"] = fnos_data
        _save_media_config(args, media_cfg)

        if is_json_mode():
            json_out({"status": "ok", "username": username, "base_url": config.base_url})
        else:
            success("登录成功! Token 已保存")
            kvline("用户", username)
            kvline("地址", config.base_url)
    else:
        error("Provider '{}' 暂不支持 login".format(provider_name))


def _handle_status(args):
    """media status"""
    try:
        provider = _get_provider(args)
        user_info = provider.get_user_info()
        if is_json_mode():
            json_out({
                "status": "ok",
                "provider": provider.provider_name,
                "base_url": provider.base_url,
                "user": user_info,
            })
        else:
            success("连接正常")
            kvline("Provider", provider.provider_name)
            kvline("地址", provider.base_url)
            kvline("用户", user_info.get("username", ""))
            kvline("设备", user_info.get("device", ""))
    except MediaProviderError as e:
        if e.code == -2:
            error("Token 已过期，请重新运行 quark-cli media login")
        else:
            error("检查失败: {}".format(e.message))
        sys.exit(1)
    except ValueError as e:
        error(str(e))
        sys.exit(1)
    except Exception as e:
        error("连接失败: {}".format(e))
        sys.exit(1)


def _handle_config_show(args):
    """media config --show"""
    media_cfg = _get_media_config(args)
    if not media_cfg:
        warning("未配置 media，请先运行 quark-cli media login")
        return
    display = media_cfg.copy()
    for pname in ("fnos", "emby", "jellyfin"):
        if pname in display and isinstance(display[pname], dict) and "token" in display[pname]:
            t = display[pname]["token"]
            display[pname]["token"] = "***{}".format(t[-8:]) if len(t) > 8 else "***"
    # 脱敏 TMDB key
    disc = display.get("discovery", {})
    if isinstance(disc, dict) and disc.get("tmdb_api_key"):
        k = disc["tmdb_api_key"]
        disc["tmdb_api_key"] = "***{}".format(k[-6:]) if len(k) > 6 else "***"
    print(json.dumps(display, ensure_ascii=False, indent=2))


def _handle_config_set(args):
    """media config --provider / --host / --port / --token / --tmdb-key / --tmdb-lang"""
    media_cfg = _get_media_config(args)
    changed = False

    if getattr(args, "provider", None):
        media_cfg["provider"] = args.provider
        changed = True

    provider_name = media_cfg.get("provider", "fnos")
    provider_cfg = media_cfg.get(provider_name, {})

    if getattr(args, "host", None):
        provider_cfg["host"] = args.host
        changed = True
    if getattr(args, "port", None):
        provider_cfg["port"] = args.port
        changed = True
    if getattr(args, "token", None):
        provider_cfg["token"] = args.token
        changed = True

    if changed:
        media_cfg[provider_name] = provider_cfg

    # TMDB / discovery 配置
    tmdb_key = getattr(args, "tmdb_key", None)
    tmdb_lang = getattr(args, "tmdb_lang", None)
    if tmdb_key or tmdb_lang:
        disc = media_cfg.get("discovery", {})
        if tmdb_key:
            disc["tmdb_api_key"] = tmdb_key
            disc.setdefault("source", "tmdb")
            disc.setdefault("language", "zh-CN")
            disc.setdefault("region", "CN")
            changed = True
        if tmdb_lang:
            disc["language"] = tmdb_lang
            changed = True
        media_cfg["discovery"] = disc

    if changed:
        _save_media_config(args, media_cfg)
        success("配置已保存")
    else:
        _handle_config_show(args)


def _handle_lib_list(args):
    """media lib list"""
    try:
        provider = _get_provider(args)
        libs = provider.get_libraries()
    except Exception as e:
        error("获取媒体库列表失败: {}".format(e))
        sys.exit(1)

    if not libs:
        warning("暂无媒体库")
        return

    if is_json_mode():
        json_out([{"guid": l.guid, "title": l.title, "category": l.category, "count": l.count} for l in libs])
        return

    header("媒体库列表")
    cols = ["名称", "类型", "影片数", "GUID"]
    widths = [22, 12, 8, 36]
    table_header(cols, widths)
    for lib in libs:
        table_row(
            [lib.title, lib.category or "-", str(lib.count), lib.guid],
            widths,
            colors=[Color.CYAN, Color.MAGENTA, Color.GREEN, Color.DIM],
        )


def _handle_lib_show(args):
    """media lib show <name>"""
    name = args.lib_name
    page = getattr(args, "page", 1) or 1
    size = getattr(args, "size", 20) or 20

    try:
        provider = _get_provider(args)
        libs = provider.get_libraries()
        target = None
        for lib in libs:
            if lib.title == name or lib.guid.startswith(name):
                target = lib
                break
        if not target:
            error("未找到媒体库: {}".format(name))
            sys.exit(1)

        result = provider.get_items(library_guid=target.guid, page=page, page_size=size)
    except Exception as e:
        error("获取影片列表失败: {}".format(e))
        sys.exit(1)

    if is_json_mode():
        json_out({
            "library": target.title,
            "total": result.total,
            "page": page,
            "items": [_item_to_dict(it) for it in result.items],
        })
        return

    subheader("\U0001f4c1 {}".format(target.title))
    if not result.items:
        warning("暂无影片")
        return

    cols = ["#", "名称", "年份", "评分", "GUID"]
    widths = [5, 30, 7, 7, 36]
    table_header(cols, widths)
    for i, item in enumerate(result.items, start=(page - 1) * size + 1):
        table_row(
            [str(i), item.title, item.year or "-", str(item.rating) if item.rating else "-", item.guid],
            widths,
            colors=[Color.DIM, Color.CYAN, Color.GREEN, Color.YELLOW, Color.DIM],
        )
    print("\n  共 {} 部 | 第 {} 页".format(result.total, page))


def _handle_search(args):
    """media search <keyword>"""
    keyword = args.keyword
    page = getattr(args, "page", 1) or 1
    size = getattr(args, "size", 20) or 20

    try:
        provider = _get_provider(args)
        result = provider.search_items(keyword=keyword, page=page, page_size=size)
    except Exception as e:
        error("搜索失败: {}".format(e))
        sys.exit(1)

    if is_json_mode():
        json_out({
            "keyword": keyword,
            "total": result.total,
            "page": page,
            "items": [_item_to_dict(it) for it in result.items],
        })
        return

    if not result.items:
        warning("未找到匹配 '{}' 的影片".format(keyword))
        return

    subheader("搜索结果: {}".format(keyword))
    cols = ["#", "名称", "年份", "评分", "GUID"]
    widths = [5, 30, 7, 7, 36]
    table_header(cols, widths)
    for i, item in enumerate(result.items, start=1):
        table_row(
            [str(i), item.title, item.year or "-", str(item.rating) if item.rating else "-", item.guid],
            widths,
            colors=[Color.DIM, Color.CYAN, Color.GREEN, Color.YELLOW, Color.DIM],
        )
    print("\n  共 {} 条结果 | 第 {} 页".format(result.total, page))


def _handle_info(args):
    """media info <guid_or_name>"""
    guid_or_name = args.guid
    show_seasons = getattr(args, "seasons", False)
    show_cast = getattr(args, "cast", False)

    try:
        provider = _get_provider(args)
        guid = _resolve_guid(provider, guid_or_name)
        detail = provider.get_item_detail(guid)
    except MediaProviderError as e:
        if e.code == -2:
            error("Token 已过期，请重新运行 quark-cli media login")
        elif e.code in (404, -6):
            warning("未找到与 '{}' 匹配的影片".format(guid_or_name))
        else:
            error("获取详情失败: {}".format(e.message))
        sys.exit(1)
    except Exception as e:
        error("获取详情失败: {}".format(e))
        sys.exit(1)

    if is_json_mode():
        data = _item_to_dict(detail)
        if show_seasons:
            try:
                seasons = provider.get_seasons(guid)
                data["seasons"] = [
                    {"guid": s.guid, "title": s.title, "season_number": s.season_number, "episode_count": s.episode_count}
                    for s in seasons
                ]
            except Exception:
                data["seasons"] = []
        if show_cast:
            try:
                persons = provider.get_persons(guid)
                data["cast"] = [{"name": p.name, "role": p.role} for p in persons]
            except Exception:
                data["cast"] = []
        json_out(data)
        return

    # 基本信息
    header("\U0001f3ac {}".format(detail.title))
    if detail.original_title:
        print(colorize("  {}".format(detail.original_title), Color.DIM))
    kvline("年份", detail.year or "未知")
    kvline("评分", str(detail.rating) if detail.rating else "暂无")
    kvline("类型", detail.media_type or "未知")
    kvline("GUID", detail.guid)
    if detail.overview:
        print()
        print(colorize("  \U0001f4dd 简介:", Color.BOLD))
        ov = detail.overview
        while ov:
            print("  {}".format(ov[:70]))
            ov = ov[70:]

    if show_seasons:
        try:
            seasons = provider.get_seasons(guid)
            if seasons:
                subheader("\U0001f4fa 季列表")
                cols = ["季", "名称", "集数", "GUID"]
                widths = [5, 26, 7, 36]
                table_header(cols, widths)
                for s in seasons:
                    table_row(
                        [str(s.season_number), s.title, str(s.episode_count) if s.episode_count else "-", s.guid],
                        widths,
                        colors=[Color.CYAN, None, Color.GREEN, Color.DIM],
                    )
        except Exception:
            pass

    if show_cast:
        try:
            persons = provider.get_persons(guid)
            if persons:
                subheader("\U0001f465 演职人员")
                cols = ["姓名", "角色"]
                widths = [24, 30]
                table_header(cols, widths)
                for p in persons:
                    table_row(
                        [p.name, p.role or "-"],
                        widths,
                        colors=[Color.CYAN, None],
                    )
        except Exception:
            pass


def _handle_poster(args):
    """media poster <guid_or_name> - 下载海报和背景图"""
    guid_or_name = args.guid
    output = getattr(args, "output", ".") or "."

    try:
        provider = _get_provider(args)
        guid = _resolve_guid(provider, guid_or_name)
        saved_paths = provider.download_poster(guid, output_dir=output)
        if is_json_mode():
            json_out({"status": "ok", "files": saved_paths, "guid": guid})
        else:
            for p in saved_paths:
                success("已保存: {}".format(p))
    except Exception as e:
        error("下载海报失败: {}".format(e))
        sys.exit(1)


def _handle_export(args):
    """media export"""
    output = getattr(args, "output", "export.json") or "export.json"
    fmt = getattr(args, "format", "json") or "json"
    lib_name = getattr(args, "lib", None)

    try:
        provider = _get_provider(args)
        result_path = provider.export_items(
            library_name=lib_name or "",
            fmt=fmt,
            output_path=output,
        )
        if is_json_mode():
            json_out({"status": "ok", "path": result_path})
        else:
            success("导出完成: {}".format(result_path))
    except Exception as e:
        error("导出失败: {}".format(e))
        sys.exit(1)


def _handle_playing(args):
    """media playing - 查看继续观看列表"""
    try:
        provider = _get_provider(args)
        records = provider.get_play_records()
    except Exception as e:
        error("获取播放记录失败: {}".format(e))
        sys.exit(1)

    if not records:
        if is_json_mode():
            json_out([])
        else:
            warning("暂无播放记录")
        return

    if is_json_mode():
        items = []
        for r in records:
            title = r.tv_title or r.title
            if r.season_number or r.episode_number:
                title += " S{:02d}E{:02d}".format(r.season_number or 0, r.episode_number or 0)
            items.append({
                "guid": r.guid,
                "title": title,
                "media_type": r.media_type or "",
                "duration": r.duration,
            })
        json_out(items)
        return

    subheader("\u25b6 继续观看")
    cols = ["#", "名称", "类型", "进度(s)", "GUID"]
    widths = [5, 32, 10, 10, 36]
    table_header(cols, widths)
    for i, r in enumerate(records, start=1):
        title = r.tv_title or r.title
        if r.season_number or r.episode_number:
            title += " S{:02d}E{:02d}".format(r.season_number or 0, r.episode_number or 0)
        table_row(
            [str(i), title, r.media_type or "-", "{:.0f}".format(r.duration), r.guid],
            widths,
            colors=[Color.DIM, Color.CYAN, Color.MAGENTA, Color.GREEN, Color.DIM],
        )


# ──────────────────────────────────────────────
# media meta (影视元数据查询 — TMDB / 豆瓣)
# ──────────────────────────────────────────────

def _handle_meta(args):
    """media meta - 查询影视元数据 (TMDB / 豆瓣)"""
    from quark_cli.media.discovery.naming import (
        suggest_search_keywords,
        suggest_save_path,
        format_meta_summary,
    )

    query = getattr(args, "query", None)
    tmdb_id = getattr(args, "tmdb", None)
    imdb_id = getattr(args, "imdb", None)
    douban_id = getattr(args, "douban", None)
    source_name = getattr(args, "source", "auto") or "auto"
    media_type = getattr(args, "type", "movie") or "movie"
    year = getattr(args, "year", None)
    base_path = getattr(args, "base_path", "/媒体") or "/媒体"

    # 根据指定的 ID 自动决定 source
    if douban_id:
        source_name = "douban"
    elif tmdb_id or imdb_id:
        if source_name == "auto":
            source_name = "tmdb"

    if not query and not tmdb_id and not imdb_id and not douban_id:
        error("请指定搜索关键词、--tmdb ID、--imdb ID 或 --douban ID\n"
              "  用法: quark-cli media meta \"流浪地球2\"\n"
              "        quark-cli media meta --douban 36104Mo\n"
              "        quark-cli media meta -s douban \"流浪地球\"")
        sys.exit(1)

    try:
        source, actual_source = _get_discovery_source(args, source_name)
    except Exception as e:
        error(str(e))
        sys.exit(1)

    is_douban = actual_source == "douban"
    source_label = "豆瓣" if is_douban else "TMDB"

    try:
        # 直接通过 ID 获取
        if douban_id:
            item = source.get_detail(douban_id, media_type)
        elif tmdb_id:
            item = source.get_detail(tmdb_id, media_type)
        elif imdb_id:
            item = source.find_by_external_id(imdb_id, "imdb_id")
        else:
            # 先搜索，取最匹配的结果；搜不到则自动 fallback 另一类型
            result = source.search(query, media_type=media_type, page=1, year=year)
            fallback_type = None
            if not result.items:
                alt = "tv" if media_type == "movie" else "movie"
                result = source.search(query, media_type=alt, page=1, year=year)
                if result.items:
                    fallback_type = alt
                    media_type = alt

            if not result.items:
                if is_json_mode():
                    json_out({"error": "未找到匹配 '{}' 的影视作品 (已同时搜索 movie 和 tv)".format(query),
                              "source": actual_source, "results": []})
                else:
                    warning("[{}] 未找到匹配 '{}' 的影视作品 (已同时搜索 movie 和 tv)".format(source_label, query))
                return

            if fallback_type and not is_json_mode():
                alt_label = "剧集" if fallback_type == "tv" else "电影"
                info("在 {} 中未找到，已自动切换为 {} 搜索".format(
                    "电影" if fallback_type == "tv" else "剧集", alt_label
                ))

            # 如果有多个结果，先展示列表让用户了解，然后取第一个的详情
            first = result.items[0]
            item = source.get_detail(first.source_id, media_type)

            # 如果有多个搜索结果，在非 JSON 模式下提示
            if len(result.items) > 1 and not is_json_mode():
                info("搜索到 {} 个结果，显示最佳匹配。其他结果:".format(result.total))
                id_label = "豆瓣" if is_douban else "TMDB"
                for i, it in enumerate(result.items[1:6], start=2):
                    print("    {}. {} ({})  {}:{}  \u2605{}".format(
                        i, it.title, it.year, id_label, it.source_id, it.rating
                    ))
                print()

    except Exception as e:
        error("{} 查询失败: {}".format(source_label, e))
        sys.exit(1)

    # resolve genre_ids → names (TMDB 列表页只有 id)
    if not is_douban and item.genres and isinstance(item.genres[0], int):
        try:
            item.genres = source.resolve_genre_names(item.genres, media_type)
        except Exception:
            pass

    # 生成建议
    keywords = suggest_search_keywords(item)
    paths = suggest_save_path(item, base_path=base_path)
    summary = format_meta_summary(item)

    # 补充海报 URL
    poster_url = ""
    backdrop_url = ""
    if item.poster_path:
        poster_url = source.get_poster_url(item.poster_path)
        summary["poster_url"] = poster_url
    if item.backdrop_path:
        backdrop_url = source.get_poster_url(item.backdrop_path, "w1280")
        summary["backdrop_url"] = backdrop_url

    # JSON 输出加 source 字段
    summary["source"] = actual_source
    summary["source_id"] = item.source_id

    if is_json_mode():
        json_out({
            "source": actual_source,
            "meta": summary,
            "search_keywords": keywords,
            "save_paths": paths,
        })
        return

    # ── 终端输出 ──
    header("\U0001f3ac {}".format(item.title))
    if item.original_title and item.original_title != item.title:
        print(colorize("  {}".format(item.original_title), Color.DIM))
    if item.tagline:
        print(colorize("  \"{}\"".format(item.tagline), Color.DIM))

    print()
    kvline("数据源", source_label)
    if is_douban:
        kvline("豆瓣 ID", item.source_id)
        kvline("豆瓣链接", "https://movie.douban.com/subject/{}/".format(item.source_id))
    else:
        kvline("TMDB ID", item.source_id)
        if item.imdb_id:
            kvline("IMDb ID", item.imdb_id)
    kvline("类型", "{} / {}".format(
        "电影" if media_type == "movie" else "剧集",
        " / ".join(item.genres) if item.genres else "未知",
    ))
    kvline("年份", item.year or "未知")
    kvline("评分", "\u2605 {} ({} 票)".format(item.rating, item.vote_count) if item.rating else "暂无")
    if item.runtime:
        kvline("片长", "{} 分钟".format(item.runtime))
    if item.status:
        kvline("状态", item.status)

    # 主创
    if item.credits:
        directors = [c["name"] for c in item.credits.get("crew", []) if c.get("job") == "Director"]
        if directors:
            kvline("导演", " / ".join(directors))
        cast = item.credits.get("cast", [])[:6]
        if cast:
            cast_str = " / ".join("{} ({})".format(c["name"], c.get("character", "")) for c in cast)
            kvline("主演", cast_str)

    if item.overview:
        print()
        print(colorize("  \U0001f4dd 简介:", Color.BOLD))
        ov = item.overview
        while ov:
            print("  {}".format(ov[:70]))
            ov = ov[70:]

    # 搜索关键词建议
    if keywords:
        subheader("\U0001f50d 搜索关键词建议")
        for i, kw in enumerate(keywords, start=1):
            print("  {}. {}".format(
                colorize(str(i), Color.CYAN),
                colorize(kw, Color.GREEN),
            ))
        print(colorize("  \n  \u25b6 用法: quark-cli search query \"{}\"".format(keywords[0]), Color.DIM))

    # 保存路径建议
    if paths:
        subheader("\U0001f4c1 保存路径建议")
        for i, p in enumerate(paths, start=1):
            print("  {}. {}".format(
                colorize(str(i), Color.CYAN),
                colorize(p["path"], Color.GREEN),
            ))
            print("     {}".format(colorize(p["description"], Color.DIM)))
        print(colorize("  \n  \u25b6 用法: quark-cli share save <url> \"{}\"".format(paths[0]["path"]), Color.DIM))

    # 海报 URL
    if poster_url:
        print()
        kvline("海报", poster_url)
    if backdrop_url:
        kvline("背景图", backdrop_url)


# ──────────────────────────────────────────────
# media discover (高分影视推荐 — TMDB / 豆瓣)
# ──────────────────────────────────────────────

def _handle_discover(args):
    """media discover - 高分影视推荐 (TMDB / 豆瓣)"""
    list_type = getattr(args, "list_type", "top_rated") or "top_rated"
    source_name = getattr(args, "source", "auto") or "auto"
    media_type = getattr(args, "type", "movie") or "movie"
    page = getattr(args, "page", 1) or 1
    min_rating = getattr(args, "min_rating", None)
    genre_arg = getattr(args, "genre", None)
    tag_arg = getattr(args, "tag", None)
    year = getattr(args, "year", None)
    country = getattr(args, "country", None)
    sort_by = getattr(args, "sort_by", "vote_average.desc")
    min_votes = getattr(args, "min_votes", 50) or 50
    window = getattr(args, "window", "week") or "week"

    # 指定了 --tag 则强制 douban
    if tag_arg and source_name == "auto":
        source_name = "douban"

    try:
        source, actual_source = _get_discovery_source(args, source_name)
    except Exception as e:
        error(str(e))
        sys.exit(1)

    is_douban = actual_source == "douban"
    source_label = "豆瓣" if is_douban else "TMDB"

    try:
        if is_douban:
            result, list_label = _discover_douban(
                source, list_type, media_type, page,
                tag_arg, genre_arg, sort_by, min_rating,
                window,
            )
        else:
            result, list_label = _discover_tmdb(
                source, list_type, media_type, page,
                genre_arg, sort_by, min_rating, min_votes,
                year, country, window,
            )
    except Exception as e:
        error("{} 查询失败: {}".format(source_label, e))
        sys.exit(1)

    if not result.items:
        if is_json_mode():
            json_out({"items": [], "total": 0, "page": page, "source": actual_source})
        else:
            warning("[{}] 未找到符合条件的影视作品".format(source_label))
        return

    # resolve genre_ids → names for display (TMDB only)
    if not is_douban:
        for it in result.items:
            if it.genres and isinstance(it.genres[0], int):
                try:
                    it.genres = source.resolve_genre_names(it.genres, media_type)
                except Exception:
                    pass

    # ── JSON 输出 ──
    if is_json_mode():
        items = []
        id_key = "douban_id" if is_douban else "tmdb_id"
        for it in result.items:
            entry = {
                id_key: it.source_id,
                "title": it.title,
                "original_title": it.original_title,
                "year": it.year,
                "rating": it.rating,
                "vote_count": it.vote_count,
                "genres": it.genres,
                "overview": it.overview[:200] if it.overview else "",
            }
            poster = source.get_poster_url(it.poster_path) if it.poster_path else ""
            if poster:
                entry["poster_url"] = poster
            items.append(entry)
        json_out({
            "source": actual_source,
            "list_type": list_type,
            "media_type": media_type,
            "page": result.page,
            "total_pages": result.total_pages,
            "total": result.total,
            "items": items,
        })
        return

    # ── 终端输出 ──
    type_label = "电影" if media_type == "movie" else "剧集"
    header("\u2b50 [{}] {} {} 推荐".format(source_label, type_label, list_label))

    # 附加筛选条件提示
    filters_desc = []
    if min_rating is not None:
        filters_desc.append("\u2265 {} 分".format(min_rating))
    if genre_arg:
        filters_desc.append("类型: {}".format(genre_arg))
    if tag_arg:
        filters_desc.append("标签: {}".format(tag_arg))
    if year:
        filters_desc.append("年份: {}".format(year))
    if country:
        filters_desc.append("地区: {}".format(country))
    if filters_desc:
        info("筛选条件: {}".format(" | ".join(filters_desc)))
        print()

    id_col = "豆瓣" if is_douban else "TMDB"
    cols = ["#", "名称", "年份", "评分", "票数", "类型", id_col]
    widths = [4, 28, 6, 6, 7, 16, 9]
    table_header(cols, widths)

    start_idx = (page - 1) * 20 + 1
    for i, it in enumerate(result.items, start=start_idx):
        genre_str = "/".join(it.genres[:2]) if isinstance(it.genres, list) and it.genres and isinstance(it.genres[0], str) else ""
        table_row(
            [
                str(i),
                it.title,
                it.year or "-",
                str(it.rating) if it.rating else "-",
                str(it.vote_count),
                genre_str,
                it.source_id,
            ],
            widths,
            colors=[Color.DIM, Color.CYAN, Color.GREEN, Color.YELLOW, Color.DIM, Color.MAGENTA, Color.DIM],
        )

    print()
    print("  共 {} 部 | 第 {}/{} 页".format(result.total, result.page, result.total_pages))

    # 提示下一步操作
    if is_douban:
        print(colorize("  \u25b6 查看详情: quark-cli media meta --douban <豆瓣ID>", Color.DIM))
    else:
        print(colorize("  \u25b6 查看详情: quark-cli media meta --tmdb <TMDB_ID>", Color.DIM))
    if result.page < result.total_pages:
        next_cmd = "quark-cli media discover -s {} --list {} -t {} -p {}".format(
            actual_source, list_type, media_type, page + 1
        )
        if tag_arg:
            next_cmd += " --tag \"{}\"".format(tag_arg)
        print(colorize("  \u25b6 下一页: {}".format(next_cmd), Color.DIM))

    # 豆瓣模式: 提示可用标签
    if is_douban and hasattr(source, "get_available_tags"):
        tags = source.get_available_tags(media_type)
        if tags:
            print()
            print(colorize("  可用标签: {}".format(" / ".join(tags[:15])), Color.DIM))


def _discover_tmdb(source, list_type, media_type, page,
                   genre_arg, sort_by, min_rating, min_votes,
                   year, country, window):
    """TMDB 发现逻辑 (从原 _handle_discover 提取)"""
    # 处理 genre 参数: 支持中文名如 "动作,科幻"
    genre_ids = None
    if genre_arg:
        parts = [g.strip() for g in genre_arg.split(",")]
        if all(p.isdigit() for p in parts):
            genre_ids = genre_arg
        else:
            genre_ids = source.resolve_genre_ids(parts, media_type)
            if not genre_ids:
                warning("未匹配到有效类型: {}".format(genre_arg))
                genres_map = source.get_genres(media_type)
                info("可用类型: {}".format(
                    ", ".join("{} ({})".format(v, k) for k, v in sorted(genres_map.items()))
                ))
                from quark_cli.media.discovery.base import DiscoveryResult
                return DiscoveryResult(), "筛选"

    if list_type == "popular":
        result = source.get_popular(media_type, page)
        return result, "热门"
    elif list_type == "top_rated":
        result = source.get_top_rated(media_type, page)
        return result, "高分"
    elif list_type == "trending":
        result = source.get_trending(media_type, window)
        return result, "趋势 ({})".format("本周" if window == "week" else "今日")
    else:
        filters = {"sort_by": sort_by, "min_votes": min_votes}
        if min_rating is not None:
            filters["min_rating"] = min_rating
        if genre_ids:
            filters["genre"] = genre_ids
        if year:
            filters["year"] = year
        if country:
            filters["country"] = country
        result = source.discover(media_type, page, **filters)
        return result, "筛选"


def _discover_douban(source, list_type, media_type, page,
                     tag_arg, genre_arg, sort_by, min_rating,
                     window):
    """豆瓣发现逻辑"""
    if list_type == "popular":
        result = source.get_popular(media_type, page)
        return result, "热门"
    elif list_type == "top_rated":
        result = source.get_top_rated(media_type, page)
        return result, "高分"
    elif list_type == "trending":
        result = source.get_trending(media_type, window)
        return result, "趋势"
    else:
        # discover — 使用豆瓣标签浏览
        # sort_by: 豆瓣支持 recommend / time / rank
        douban_sort = sort_by
        if sort_by.startswith("vote_average"):
            douban_sort = "rank"
        elif sort_by in ("recommend", "time", "rank"):
            douban_sort = sort_by

        filters = {"sort": douban_sort}

        # --tag 优先; 否则 --genre 映射为 tag
        if tag_arg:
            filters["tag"] = tag_arg
        elif genre_arg:
            filters["tag"] = genre_arg

        if min_rating is not None:
            filters["min_rating"] = min_rating

        result = source.discover(media_type, page, **filters)
        label = "筛选"
        if tag_arg:
            label = "标签: {}".format(tag_arg)
        return result, label


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# media auto-save (自动搜索转存)
# ──────────────────────────────────────────────

def _handle_auto_save(args):
    """media auto-save - 自动搜索+排序+转存 全流程"""
    from quark_cli.commands.helpers import get_client, get_config
    from quark_cli.search import PanSearch
    from quark_cli.media.autosave import auto_save_pipeline, rank_results, filter_quark_links

    name = args.name
    save_path = getattr(args, "save_path", None)
    no_tmdb = getattr(args, "no_tmdb", False)
    media_type = getattr(args, "type", "movie") or "movie"
    year = getattr(args, "year", None)
    pattern = getattr(args, "pattern", ".*") or ".*"
    replace = getattr(args, "replace", "") or ""
    max_attempts = getattr(args, "max_attempts", 10) or 10
    base_path = getattr(args, "base_path", "/媒体") or "/媒体"
    manual_keywords = getattr(args, "keyword", None)
    dry_run = getattr(args, "dry_run", False)

    # ── Step 1: 生成搜索关键词和保存路径 ──
    keywords = []
    tmdb_item = None

    if manual_keywords:
        keywords = list(manual_keywords)
        if not is_json_mode():
            info("使用手动关键词: {}".format(", ".join(keywords)))
    elif no_tmdb:
        keywords = [name]
        if year:
            keywords.append("{} {}".format(name, year))
    else:
        # 尝试 TMDB 元数据
        try:
            from quark_cli.media.discovery.tmdb import TmdbError
            from quark_cli.media.discovery.naming import suggest_search_keywords, suggest_save_path

            source = _get_tmdb_source(args)

            if not is_json_mode():
                info("正在查询 TMDB 元数据: {}".format(name))

            result = source.search(name, media_type=media_type, page=1, year=year)
            # fallback
            if not result.items:
                alt = "tv" if media_type == "movie" else "movie"
                result = source.search(name, media_type=alt, page=1, year=year)
                if result.items:
                    media_type = alt

            if result.items:
                first = result.items[0]
                tmdb_item = source.get_detail(first.source_id, media_type)
                # resolve genres
                if tmdb_item.genres and isinstance(tmdb_item.genres[0], int):
                    try:
                        tmdb_item.genres = source.resolve_genre_names(tmdb_item.genres, media_type)
                    except Exception:
                        pass

                keywords = suggest_search_keywords(tmdb_item)
                if not save_path:
                    paths = suggest_save_path(tmdb_item, base_path=base_path)
                    if paths:
                        save_path = paths[0]["path"]

                if not is_json_mode():
                    success("TMDB 匹配: {} ({}) ★{}".format(
                        tmdb_item.title, tmdb_item.year, tmdb_item.rating
                    ))
            else:
                if not is_json_mode():
                    warning("TMDB 未找到匹配，使用原始名称搜索")
        except Exception as e:
            if not is_json_mode():
                warning("TMDB 查询跳过: {}".format(e))

        # fallback: 直接用名字
        if not keywords:
            keywords = [name]
            if year:
                keywords.append("{} {}".format(name, year))

    # 保存路径 fallback
    if not save_path:
        type_folder = "电影" if media_type == "movie" else "剧集"
        title_folder = "{} ({})".format(name, year) if year else name
        save_path = "/{}/{}/{}".format(base_path.strip("/"), type_folder, title_folder)

    if not is_json_mode():
        header("\U0001f680 自动搜索转存")
        kvline("名称", name)
        kvline("关键词", " | ".join(keywords))
        kvline("保存路径", save_path)
        kvline("最大尝试", str(max_attempts))
        if pattern != ".*":
            kvline("文件过滤", pattern)
        if dry_run:
            kvline("模式", colorize("DRY RUN (仅搜索排序)", Color.YELLOW))
        print()

    # ── Step 2: 搜索 ──
    cfg = get_config(args)
    search_engine = PanSearch(config=cfg)

    if not is_json_mode():
        info("正在搜索网盘资源...")

    all_results = []
    for kw in keywords:
        result = search_engine.search_all(kw)
        if result.get("success") and result.get("results"):
            all_results.extend(result["results"])

    # 去重
    seen_urls = set()
    unique = []
    for r in all_results:
        u = r.get("url", "")
        if u not in seen_urls:
            seen_urls.add(u)
            unique.append(r)

    quark_results = filter_quark_links(unique)

    if not quark_results:
        if is_json_mode():
            json_out({"success": False, "error": "未搜索到夸克网盘链接", "keywords": keywords})
        else:
            error("未搜索到夸克网盘链接")
        sys.exit(1)

    ranked = rank_results(quark_results, keywords)
    candidates = ranked[:max_attempts]

    if not is_json_mode():
        success("找到 {} 个夸克链接 (共搜到 {})".format(len(quark_results), len(unique)))
        print()
        subheader("\U0001f3af 候选排名 (Top {})".format(len(candidates)))
        cols = ["#", "评分", "名称", "大小", "画质"]
        widths = [4, 6, 40, 8, 8]
        table_header(cols, widths)
        for i, c in enumerate(candidates, start=1):
            sd = c.get("score_detail", {})
            size_str = "{:.1f}G".format(sd.get("size_gb", 0)) if sd.get("size_gb") else "?"
            quality = str(sd.get("quality", 0))
            table_row(
                [str(i), str(c.get("score", 0)), c.get("title", "")[:38], size_str, quality],
                widths,
                colors=[Color.DIM, Color.YELLOW, Color.CYAN, Color.GREEN, Color.MAGENTA],
            )
        print()

    # ── Dry run: 到此为止 ──
    if dry_run:
        if is_json_mode():
            json_out({
                "dry_run": True,
                "keywords": keywords,
                "save_path": save_path,
                "candidates": [
                    {
                        "title": c.get("title", ""),
                        "url": c.get("url", ""),
                        "score": c.get("score", 0),
                        "score_detail": c.get("score_detail", {}),
                    }
                    for c in candidates
                ],
            })
        else:
            info("DRY RUN 完成，未执行转存")
        return

    # ── Step 3: 逐个尝试转存 ──
    quark_client = get_client(args)
    account_info = quark_client.init()
    if not account_info:
        error("夸克账号验证失败，请检查 Cookie")
        sys.exit(1)

    if not is_json_mode():
        info("夸克账号: {}".format(quark_client.nickname))
        info("开始逐个尝试链接...")
        print()

    def on_progress(event, data):
        if is_json_mode():
            return
        if event == "try_start":
            info("[{}/{}] 尝试: {} (评分 {})".format(
                data.get("index", "?"), len(candidates),
                data.get("title", "")[:50], data.get("score", 0)
            ))
        elif event == "try_fail":
            warning("  ✗ 失败: {}".format(data.get("error", "未知")))
        elif event == "save_success":
            success("  ✔ 转存成功! {} 个文件".format(data.get("saved_count", 0)))

    pipeline_result = auto_save_pipeline(
        quark_client=quark_client,
        search_engine=search_engine,
        keywords=keywords,
        save_path=save_path,
        pattern=pattern,
        replace=replace,
        max_attempts=max_attempts,
        on_progress=on_progress,
        media_title=tmdb_item.title if tmdb_item else '',
        media_year=tmdb_item.year if tmdb_item else None,
        media_type=media_type if media_type else 'movie',
    )

    if is_json_mode():
        if tmdb_item:
            pipeline_result["tmdb"] = {
                "id": tmdb_item.source_id,
                "title": tmdb_item.title,
                "year": tmdb_item.year,
                "rating": tmdb_item.rating,
            }
        json_out(pipeline_result)
        return

    print()
    if pipeline_result["success"]:
        header("\u2705 转存完成!")
        kvline("来源", pipeline_result.get("saved_from_title", ""))
        kvline("链接", pipeline_result.get("saved_from", ""))
        kvline("文件数", str(pipeline_result.get("saved_count", 0)))
        kvline("保存到", pipeline_result.get("save_path", ""))
        kvline("尝试次数", "{}/{}".format(pipeline_result.get("attempts", 0), len(candidates)))
    else:
        error("转存失败: {}".format(pipeline_result.get("error", "")))
        if pipeline_result.get("errors"):
            subheader("失败详情")
            for err in pipeline_result["errors"]:
                print("  ✗ {} → {}".format(err.get("title", "")[:40], err.get("error", "")))


def handle(args):
    """media 命令分发"""
    action = getattr(args, "media_action", None)

    if action == "login":
        _handle_login(args)
    elif action == "status":
        _handle_status(args)
    elif action == "config":
        if getattr(args, "show", False):
            _handle_config_show(args)
        else:
            _handle_config_set(args)
    elif action == "lib":
        lib_action = getattr(args, "lib_action", None)
        if lib_action == "list":
            _handle_lib_list(args)
        elif lib_action == "show":
            _handle_lib_show(args)
        else:
            error("用法: quark-cli media lib {list|show}")
    elif action == "search":
        _handle_search(args)
    elif action == "info":
        _handle_info(args)
    elif action == "poster":
        _handle_poster(args)
    elif action == "export":
        _handle_export(args)
    elif action == "playing":
        _handle_playing(args)
    elif action == "meta":
        _handle_meta(args)
    elif action == "discover":
        _handle_discover(args)
    elif action == "auto-save":
        _handle_auto_save(args)
    else:
        error("用法: quark-cli media {login|status|config|lib|search|info|poster|export|playing|meta|discover|auto-save}")
        print()
        print("  影视媒体中心管理 (支持 fnOS / Emby / Jellyfin / TMDB / 豆瓣)")
        print()
        print("  子命令:")
        print("    login     登录媒体中心")
        print("    status    检查连接状态")
        print("    config    查看/修改媒体配置")
        print("    lib       媒体库管理 (list / show)")
        print("    search    搜索影片")
        print("    info      查看影片详情")
        print("    poster    下载海报")
        print("    export    导出影片列表")
        print("    playing   查看继续观看列表")
        print("    meta      查询影视元数据 (TMDB/豆瓣)")
        print("    discover  高分影视推荐 (TMDB/豆瓣)")
        print("    auto-save 自动搜索+转存 (一键全流程)")
