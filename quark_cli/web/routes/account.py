"""账号 + 配置管理 API 路由"""

from fastapi import APIRouter, HTTPException
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

        return {
            "cookies": cookies,
            "cookie_count": len([c for c in (data.get("cookie", []) if isinstance(data.get("cookie", []), list) else []) if c]),
            "fnos": fnos,
            "tmdb": tmdb,
            "config_path": cfg.get_config_path(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
