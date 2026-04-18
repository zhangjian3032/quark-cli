"""
夸克网盘 Cookie 保活模块

原理: 定期调用夸克 API (get_account_info) 维持 Cookie 会话活性，
防止长时间不使用导致 Cookie 过期失效。

同时支持自动签到（如果 Cookie 含移动端参数 kps/sign/vcode）。

配置 (config.json):
  {
    "keepalive": {
      "enabled": true,
      "interval_hours": 6,
      "auto_sign": true
    }
  }
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quark_cli.keepalive")

# 默认配置
DEFAULT_KEEPALIVE = {
    "enabled": True,
    "interval_hours": 6,
    "auto_sign": True,
}


class CookieKeepAlive:
    """Cookie 保活守护线程"""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self._running = False
        self._thread = None
        self._last_check = None       # type: Optional[datetime]
        self._results = []             # type: List[Dict[str, Any]]
        self._check_count = 0

    @property
    def status(self):
        """返回当前保活状态"""
        return {
            "running": self._running,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "check_count": self._check_count,
            "results": self._results,
        }

    def start(self):
        """启动保活线程（非阻塞）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Cookie 保活已启动")

    def stop(self):
        """停止保活"""
        self._running = False
        logger.info("Cookie 保活已停止")

    def _load_config(self):
        """读取保活配置"""
        from quark_cli.config import ConfigManager
        cfg = ConfigManager(self.config_path)
        cfg.load()
        ka = cfg.data.get("keepalive", {})
        merged = dict(DEFAULT_KEEPALIVE)
        merged.update(ka)
        return merged, cfg

    def _loop(self):
        """主循环"""
        # 启动后先等 10 秒，避免与其他初始化冲突
        time.sleep(10)

        # 首次立即执行一轮
        self._do_check()

        while self._running:
            try:
                ka_cfg, _ = self._load_config()
                interval = max(ka_cfg.get("interval_hours", 6), 1) * 3600

                # 休眠（每 60s 醒来检查一次是否该执行）
                elapsed = 0
                while elapsed < interval and self._running:
                    time.sleep(60)
                    elapsed += 60

                if not self._running:
                    break

                self._do_check()

            except Exception:
                logger.exception("保活循环异常")
                time.sleep(300)  # 异常后等 5 分钟重试

    def _do_check(self):
        """执行一轮保活检查"""
        try:
            ka_cfg, cfg = self._load_config()
            if not ka_cfg.get("enabled", True):
                return

            cookies = cfg.get_cookies()
            if not cookies:
                logger.info("保活: 无 Cookie 配置，跳过")
                return

            auto_sign = ka_cfg.get("auto_sign", True)
            results = []
            now = datetime.now()

            for i, cookie in enumerate(cookies):
                result = self._check_one(cookie, index=i, auto_sign=auto_sign)
                results.append(result)

            self._results = results
            self._last_check = now
            self._check_count += 1

            # 汇总日志
            valid = sum(1 for r in results if r.get("valid"))
            signed = sum(1 for r in results if r.get("signed"))
            logger.info(
                "保活检查完成: %d/%d 有效, %d 已签到 (第 %d 次)",
                valid, len(results), signed, self._check_count,
            )

        except Exception:
            logger.exception("保活检查异常")

    def _check_one(self, cookie, index=0, auto_sign=True):
        """检查单个 Cookie"""
        from quark_cli.api import QuarkAPI

        tag = "Cookie#{}".format(index)
        result = {
            "index": index,
            "valid": False,
            "nickname": "",
            "signed": False,
            "sign_msg": "",
            "checked_at": datetime.now().isoformat(),
        }

        try:
            client = QuarkAPI(cookie)
            info = client.get_account_info()

            if not info:
                logger.warning("保活: %s 无效或已过期", tag)
                result["error"] = "Cookie 无效或已过期"
                return result

            nickname = info.get("nickname", "")
            result["valid"] = True
            result["nickname"] = nickname
            logger.info("保活: %s (%s) 有效 ✓", tag, nickname)

            # 自动签到
            if auto_sign and client.mparam:
                try:
                    growth = client.get_growth_info()
                    if growth:
                        cap_sign = growth.get("cap_sign", {}) or {}
                        if cap_sign.get("sign_daily"):
                            result["signed"] = True
                            result["sign_msg"] = "今日已签到"
                        else:
                            ok, sign_result = client.sign_in()
                            if ok:
                                result["signed"] = True
                                reward = QuarkAPI.format_bytes(sign_result) if sign_result else ""
                                result["sign_msg"] = "签到成功 +{}".format(reward)
                                logger.info("保活: %s 自动签到成功 +%s", tag, reward)
                            else:
                                result["sign_msg"] = "签到失败: {}".format(sign_result)
                except Exception as e:
                    result["sign_msg"] = "签到异常: {}".format(str(e))
                    logger.warning("保活: %s 签到异常: %s", tag, e)

        except Exception as e:
            result["error"] = str(e)
            logger.warning("保活: %s 检查异常: %s", tag, e)

        return result

    def trigger(self):
        """手动触发一次检查"""
        t = threading.Thread(target=self._do_check, daemon=True)
        t.start()
        return {"triggered": True}


# ── 全局单例 ──

_keepalive_instance = None


def get_keepalive(config_path=None):
    """获取/创建保活单例"""
    global _keepalive_instance
    if _keepalive_instance is None:
        _keepalive_instance = CookieKeepAlive(config_path)
    return _keepalive_instance


def try_start_keepalive(config_path=None):
    """尝试启动保活，未启用则跳过"""
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path)
    cfg.load()
    ka = cfg.data.get("keepalive", {})
    enabled = ka.get("enabled", True)  # 默认启用

    if not enabled:
        logger.info("Cookie 保活: 已禁用，跳过")
        return None

    cookies = cfg.get_cookies()
    if not cookies:
        logger.info("Cookie 保活: 无 Cookie 配置，跳过")
        return None

    instance = get_keepalive(config_path)
    instance.start()
    return instance
