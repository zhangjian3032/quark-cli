"""账号 + 配置管理 API 路由"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["account"])


# ── 账号 ──

@router.get("/account/info")
def account_info():
    from quark_cli.web.deps import get_account_service
    try:
        svc = get_account_service()
        result = svc.get_info()
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/verify")
def account_verify():
    from quark_cli.web.deps import get_account_service
    try:
        svc = get_account_service()
        return svc.verify()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/sign")
def account_sign():
    from quark_cli.web.deps import get_account_service
    try:
        svc = get_account_service()
        result = svc.sign_in()
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 配置读写 ──

@router.get("/config")
def config_read():
    """读取所有配置（敏感信息脱敏）"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        data = cfg.data

        # Cookie 列表（脱敏）
        raw_cookies = data.get("cookie", [])
        if isinstance(raw_cookies, list):
            cookies_masked = []
            for c in raw_cookies:
                if c and len(c) > 30:
                    cookies_masked.append("{}...{}".format(c[:20], c[-10:]))
                elif c:
                    cookies_masked.append("***")
                else:
                    cookies_masked.append("")
            cookies = cookies_masked
        else:
            cookies = []

        # fnOS 配置
        media_cfg = data.get("media", {})
        fnos_data = media_cfg.get("fnos", {})
        fnos = {
            "host": fnos_data.get("host", ""),
            "port": fnos_data.get("port", 5666),
            "ssl": fnos_data.get("ssl", False),
            "token": "***" if fnos_data.get("token") else "",
            "api_key": fnos_data.get("api_key", ""),
            "timeout": fnos_data.get("timeout", 30),
        }

        # TMDB / Discovery 配置
        disc = media_cfg.get("discovery", {})
        tmdb_key_raw = disc.get("tmdb_api_key", "")
        tmdb = {
            "api_key": "***{}".format(tmdb_key_raw[-6:]) if len(tmdb_key_raw) > 6 else ("***" if tmdb_key_raw else ""),
            "language": disc.get("language", "zh-CN"),
            "region": disc.get("region", "CN"),
        }

        # Proxy 配置
        proxy_cfg = data.get("proxy", {})
        proxy = {
            "url": proxy_cfg.get("url", ""),
            "targets": proxy_cfg.get("targets", []),
        }

        return {
            "cookies": cookies,
            "cookie_count": len([c for c in (data.get("cookie", []) if isinstance(data.get("cookie", []), list) else []) if c]),
            "fnos": fnos,
            "tmdb": tmdb,
            "proxy": proxy,
            "config_path": cfg.get_config_path(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Proxy 配置 ──

@router.get("/config/proxy")
def config_proxy_read():
    """读取代理配置"""
    from quark_cli.web.deps import get_config
    cfg = get_config()
    cfg.load()
    proxy_cfg = cfg.data.get("proxy", {})
    return {
        "url": proxy_cfg.get("url", ""),
        "targets": proxy_cfg.get("targets", []),
    }


@router.put("/config/proxy")
def config_proxy_update(data: dict = Body(...)):
    """更新代理配置"""
    from quark_cli.web.deps import get_config, set_config_path, get_config_path
    cfg = get_config()
    cfg.load()

    proxy_url = data.get("url", "").strip()
    targets = data.get("targets", [])

    # 验证 targets
    valid_targets = {"tmdb", "douban", "rss"}
    targets = [t for t in targets if t in valid_targets]

    # 验证 proxy URL 格式
    if proxy_url and not proxy_url.startswith(("http://", "https://", "socks5://", "socks4://")):
        raise HTTPException(status_code=400, detail="代理地址需以 http://, https://, socks5://, socks4:// 开头")

    cfg._data["proxy"] = {
        "url": proxy_url,
        "targets": targets,
    }
    cfg.save()

    # 清除缓存以便下次请求使用新代理
    config_path = get_config_path()
    set_config_path(config_path)

    return {"status": "saved", "url": proxy_url, "targets": targets}


class CookieSetBody(BaseModel):
    cookie: str
    index: int = 0


@router.put("/config/cookie")
def config_set_cookie(body: CookieSetBody):
    """设置 Cookie"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        cfg.set_cookie(body.cookie, body.index)

        # 验证
        from quark_cli.api import QuarkAPI
        client = QuarkAPI(body.cookie)
        info = client.get_account_info()
        if info:
            return {"success": True, "nickname": info.get("nickname", "")}
        return {"success": True, "warning": "Cookie 已保存但验证失败，请检查是否正确"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CookieRemoveBody(BaseModel):
    index: int = 0


@router.delete("/config/cookie")
def config_remove_cookie(body: CookieRemoveBody):
    """移除 Cookie"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        cfg.remove_cookie(body.index)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FnosConfigBody(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    ssl: Optional[bool] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None


@router.put("/config/fnos")
def config_set_fnos(body: FnosConfigBody):
    """更新 fnOS 配置。如果传了 username+password 则尝试登录获取 token"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        data = cfg.data
        media_cfg = data.get("media", {})
        fnos_data = media_cfg.get("fnos", {})

        if body.host is not None:
            fnos_data["host"] = body.host
        if body.port is not None:
            fnos_data["port"] = body.port
        if body.ssl is not None:
            fnos_data["ssl"] = body.ssl
        if body.api_key is not None:
            fnos_data["api_key"] = body.api_key
        if body.timeout is not None:
            fnos_data["timeout"] = body.timeout

        # 如果提供了用户名密码，尝试登录
        login_result = None
        if body.username and body.password:
            from quark_cli.media.fnos.config import FnosConfig
            from quark_cli.media.fnos.client import FnosClient
            test_config = FnosConfig.from_dict(fnos_data)
            test_config.validate()
            client = FnosClient(test_config)
            try:
                token = client.login(body.username, body.password)
                fnos_data["token"] = token
                login_result = {"logged_in": True, "username": body.username}
            except Exception as e:
                raise HTTPException(status_code=400, detail="登录失败: {}".format(str(e)))

        media_cfg["fnos"] = fnos_data
        media_cfg.setdefault("provider", "fnos")
        data["media"] = media_cfg
        cfg.save()

        result = {"success": True}
        if login_result:
            result["login"] = login_result
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TmdbConfigBody(BaseModel):
    api_key: Optional[str] = None
    language: Optional[str] = None
    region: Optional[str] = None


@router.put("/config/tmdb")
def config_set_tmdb(body: TmdbConfigBody):
    """更新 TMDB 配置"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        data = cfg.data
        media_cfg = data.get("media", {})
        disc = media_cfg.get("discovery", {})

        if body.api_key is not None:
            disc["tmdb_api_key"] = body.api_key
            disc.setdefault("source", "tmdb")
            disc.setdefault("language", "zh-CN")
            disc.setdefault("region", "CN")
        if body.language is not None:
            disc["language"] = body.language
        if body.region is not None:
            disc["region"] = body.region

        media_cfg["discovery"] = disc
        data["media"] = media_cfg
        cfg.save()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 飞书机器人配置 ──

class FeishuBotConfigBody(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    base_path: Optional[str] = None
    notify_open_id: Optional[str] = None
    api_base: Optional[str] = None


@router.get("/config/bot")
def config_bot_read():
    """读取飞书机器人配置（脱敏）"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        bot_cfg = cfg.data.get("bot", {}).get("feishu", {})

        app_id = bot_cfg.get("app_id", "")
        app_secret = bot_cfg.get("app_secret", "")
        notify_open_id = bot_cfg.get("notify_open_id", "")
        api_base = bot_cfg.get("api_base", "")

        return {
            "app_id": "{}***".format(app_id[:6]) if len(app_id) > 6 else ("***" if app_id else ""),
            "app_secret": "***{}".format(app_secret[-6:]) if len(app_secret) > 6 else ("***" if app_secret else ""),
            "base_path": bot_cfg.get("base_path", "/媒体"),
            "notify_open_id": notify_open_id,
            "api_base": api_base,
            "configured": bool(app_id and app_secret),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/bot")
def config_bot_set(body: FeishuBotConfigBody):
    """更新飞书机器人配置"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        data = cfg.data
        bot_cfg = data.get("bot", {})
        feishu = bot_cfg.get("feishu", {})

        if body.app_id is not None:
            feishu["app_id"] = body.app_id
        if body.app_secret is not None:
            feishu["app_secret"] = body.app_secret
        if body.base_path is not None:
            feishu["base_path"] = body.base_path
        if body.notify_open_id is not None:
            feishu["notify_open_id"] = body.notify_open_id
        if body.api_base is not None:
            feishu["api_base"] = body.api_base

        bot_cfg["feishu"] = feishu
        data["bot"] = bot_cfg
        cfg.save()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 配置导出 / 导入 ──

@router.get("/config/export")
def config_export():
    """导出完整配置 (含明文 Cookie / Token，仅限本地使用)"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        import copy
        data = copy.deepcopy(cfg.data)
        # 注入元信息
        data["_export_meta"] = {
            "version": "2.3.0",
            "exported_at": __import__("datetime").datetime.now().isoformat(),
        }
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/import")
def config_import(body: dict):
    """
    导入配置 (合并模式)

    支持两种传入方式:
      1. 完整 config.json (含 cookie/media/sync/scheduler 等)
      2. 部分配置 (只传 sync / scheduler 等特定 key)

    导入策略: 深度合并，已有字段被覆盖，新字段追加。
    Cookie 列表采用追加模式 (不覆盖已有 Cookie)。
    """
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()

        # 移除导出元信息
        body.pop("_export_meta", None)

        # Cookie 特殊处理: 追加而非覆盖
        import_cookies = body.pop("cookie", None)
        if import_cookies and isinstance(import_cookies, list):
            existing = cfg.data.get("cookie", [])
            if not isinstance(existing, list):
                existing = [existing] if existing else []
            # 去重追加
            existing_set = set(existing)
            for c in import_cookies:
                if c and c not in existing_set and not c.startswith("请替换"):
                    existing.append(c)
            cfg._data["cookie"] = existing

        # 深度合并其余配置
        _deep_merge(cfg._data, body)

        cfg.save()

        return {
            "success": True,
            "message": "配置导入成功",
            "keys_imported": list(body.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _deep_merge(base: dict, override: dict):
    """递归合并 dict，override 覆盖 base"""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


# ── Cookie 保活 ──

@router.get("/keepalive/status")
def keepalive_status():
    """获取 Cookie 保活状态"""
    from quark_cli.keepalive import get_keepalive
    try:
        ka = get_keepalive()
        return ka.status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keepalive/toggle")
def keepalive_toggle():
    """启用/禁用 Cookie 保活"""
    from quark_cli.web.deps import get_config
    from quark_cli.keepalive import get_keepalive
    try:
        cfg = get_config()
        cfg.load()
        ka_cfg = cfg._data.setdefault("keepalive", {})
        current = ka_cfg.get("enabled", True)
        ka_cfg["enabled"] = not current
        cfg.save()

        ka = get_keepalive()
        if ka_cfg["enabled"]:
            ka.start()
        else:
            ka.stop()

        return {"enabled": ka_cfg["enabled"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keepalive/trigger")
def keepalive_trigger():
    """手动触发一次保活检查"""
    from quark_cli.keepalive import get_keepalive
    try:
        ka = get_keepalive()
        return ka.trigger()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KeepAliveConfigBody(BaseModel):
    interval_hours: Optional[int] = None
    auto_sign: Optional[bool] = None
    enabled: Optional[bool] = None


@router.put("/keepalive/config")
def keepalive_config_update(body: KeepAliveConfigBody):
    """更新保活配置"""
    from quark_cli.web.deps import get_config
    from quark_cli.keepalive import get_keepalive
    try:
        cfg = get_config()
        cfg.load()
        ka_cfg = cfg._data.setdefault("keepalive", {})
        if body.interval_hours is not None:
            ka_cfg["interval_hours"] = max(body.interval_hours, 1)
        if body.auto_sign is not None:
            ka_cfg["auto_sign"] = body.auto_sign
        if body.enabled is not None:
            ka_cfg["enabled"] = body.enabled
            ka = get_keepalive()
            if body.enabled:
                ka.start()
            else:
                ka.stop()
        cfg.save()
        return {"success": True, "keepalive": ka_cfg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keepalive/config")
def keepalive_config_read():
    """读取保活配置"""
    from quark_cli.web.deps import get_config
    try:
        cfg = get_config()
        cfg.load()
        ka = cfg.data.get("keepalive", {"enabled": True, "interval_hours": 6, "auto_sign": True})
        return ka
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
