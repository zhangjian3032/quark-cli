"""
通用辅助函数 - 提供各命令模块共享的工具方法
"""

from quark_cli.api import QuarkAPI
from quark_cli.config import ConfigManager
from quark_cli.display import error


def get_client(args) -> QuarkAPI:
    """从配置中获取初始化的 API 客户端"""
    cfg = ConfigManager(getattr(args, "config", None))
    cookies = cfg.get_cookies()
    if not cookies:
        error("未配置 Cookie，请先执行: quark-cli config set-cookie <cookie>")
        raise SystemExit(1)
    return QuarkAPI(cookies[0])


def get_config(args) -> ConfigManager:
    """获取配置管理器"""
    return ConfigManager(getattr(args, "config", None))
