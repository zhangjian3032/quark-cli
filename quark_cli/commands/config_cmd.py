"""
config 子命令 - 配置管理
"""

from quark_cli.config import ConfigManager, DEFAULT_CONFIG
from quark_cli import display


def handle(args):
    cfg = ConfigManager(getattr(args, "config", None))
    action = getattr(args, "config_action", None)

    if action == "set-cookie":
        cfg.load()
        cfg.set_cookie(args.cookie, args.index)
        display.success(f"Cookie 已保存到账号 #{args.index + 1}")
        # 验证
        from quark_cli.api import QuarkAPI
        client = QuarkAPI(args.cookie)
        info = client.get_account_info()
        if info:
            display.success(f"验证通过 - 昵称: {info.get('nickname', 'N/A')}")
        else:
            display.warning("Cookie 验证失败，请检查是否正确")

    elif action == "show":
        cfg.load()
        display.header("当前配置")
        print(cfg.show_config())

    elif action == "path":
        display.info(f"配置文件路径: {cfg.get_config_path()}")

    elif action == "reset":
        cfg._data = DEFAULT_CONFIG.copy()
        cfg.save()
        display.success("配置已重置为默认值")

    elif action == "remove-cookie":
        cfg.load()
        cfg.remove_cookie(args.index)
        display.success(f"已移除账号 #{args.index + 1} 的 Cookie")

    else:
        display.info("用法: quark-cli config {set-cookie|show|path|reset|remove-cookie}")
