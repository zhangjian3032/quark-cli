"""
account 子命令 - 账号管理、签到、空间查询
"""

import json
from quark_cli import display
from quark_cli.display import is_json_mode, json_out
from quark_cli.commands.helpers import get_client, get_config


def handle(args):
    action = getattr(args, "account_action", None)

    if action == "info":
        _account_info(args)
    elif action == "sign":
        _sign(args)
    elif action == "verify":
        _verify(args)
    elif action == "space":
        _space(args)
    else:
        display.info("用法: quark-cli account {info|sign|verify|space}")


def _account_info(args):
    """查看账号信息"""
    client = get_client(args)
    info = client.get_account_info()
    if not info:
        display.error("获取账号信息失败，Cookie 可能已失效")
        return

    growth = client.get_growth_info()

    if is_json_mode():
        data = {"account": info}
        if growth:
            data["growth"] = growth
        json_out(data)
        return

    display.header("账号信息")
    display.kvline("昵称", info.get("nickname", "N/A"))
    display.kvline("会员类型", info.get("member_type", "N/A"))
    display.kvline("手机号", info.get("phone", "N/A"))
    display.kvline("超级会员", "是" if info.get("super_vip") else "否")

    if growth:
        VIP_MAP = {
            "NORMAL": "普通用户",
            "EXP_SVIP": "88VIP",
            "SUPER_VIP": "SVIP",
            "Z_VIP": "SVIP+",
        }
        display.divider()
        display.kvline("会员状态", VIP_MAP.get(growth["member_type"], growth["member_type"]))
        display.kvline("总空间", client.format_bytes(growth["total_capacity"]))
        cap_comp = growth.get("cap_composition", {})
        display.kvline("签到累计获得", client.format_bytes(cap_comp.get("sign_reward", 0)))


def _verify(args):
    """验证 Cookie 有效性"""
    client = get_client(args)
    info = client.get_account_info()
    if is_json_mode():
        json_out({"valid": bool(info), "nickname": info.get("nickname") if info else None})
        return
    if info:
        display.success("Cookie 有效 \u2714 - 昵称: {}".format(info.get("nickname")))
    else:
        display.error("Cookie 无效或已过期 \u2716")


def _sign(args):
    """每日签到"""
    client = get_client(args)
    if not client.mparam:
        display.warning("Cookie 中未包含移动端参数（kps/sign/vcode），无法签到")
        display.info("请从夸克网盘 APP 抓取包含完整参数的 Cookie")
        return

    info = client.init()
    if not info:
        display.error("账号验证失败")
        return

    growth = client.get_growth_info()
    if not growth:
        display.error("获取签到信息失败")
        return

    cap_sign = growth.get("cap_sign", {})
    result_data = {}

    if cap_sign.get("sign_daily"):
        reward_mb = int(cap_sign.get("sign_daily_reward", 0) / 1024 / 1024)
        progress = cap_sign.get("sign_progress", 0)
        target = cap_sign.get("sign_target", 0)
        result_data = {"already_signed": True, "reward_mb": reward_mb, "progress": progress, "target": target}
        if not is_json_mode():
            display.header("签到 - {}".format(client.nickname))
            display.success("今日已签到 +{}MB".format(reward_mb))
            display.info("连签进度: {}/{}".format(progress, target))
    else:
        ok, result = client.sign_in()
        if ok:
            reward_mb = int(result / 1024 / 1024)
            progress = cap_sign.get("sign_progress", 0) + 1
            target = cap_sign.get("sign_target", 0)
            result_data = {"already_signed": False, "success": True, "reward_mb": reward_mb, "progress": progress, "target": target}
            if not is_json_mode():
                display.header("签到 - {}".format(client.nickname))
                display.success("签到成功 +{}MB".format(reward_mb))
                display.info("连签进度: {}/{}".format(progress, target))
        else:
            result_data = {"already_signed": False, "success": False, "error": str(result)}
            if not is_json_mode():
                display.header("签到 - {}".format(client.nickname))
                display.error("签到失败: {}".format(result))

    if is_json_mode():
        result_data["member_type"] = growth.get("member_type", "")
        result_data["total_capacity"] = growth.get("total_capacity", 0)
        json_out(result_data)
        return

    VIP_MAP = {
        "NORMAL": "普通用户",
        "EXP_SVIP": "88VIP",
        "SUPER_VIP": "SVIP",
        "Z_VIP": "SVIP+",
    }
    display.divider()
    display.kvline("会员", VIP_MAP.get(growth["member_type"], growth["member_type"]))
    display.kvline("总空间", client.format_bytes(growth["total_capacity"]))


def _space(args):
    """查看网盘空间信息"""
    client = get_client(args)
    growth = client.get_growth_info()
    if not growth:
        display.error("获取空间信息失败")
        return

    if is_json_mode():
        json_out(growth)
        return

    display.header("网盘空间")
    VIP_MAP = {
        "NORMAL": "普通用户",
        "EXP_SVIP": "88VIP",
        "SUPER_VIP": "SVIP",
        "Z_VIP": "SVIP+",
    }
    display.kvline("会员类型", VIP_MAP.get(growth["member_type"], growth["member_type"]))
    display.kvline("总空间", client.format_bytes(growth["total_capacity"]))
    cap = growth.get("cap_composition", {})
    display.kvline("签到奖励", client.format_bytes(cap.get("sign_reward", 0)))
    display.kvline("活动奖励", client.format_bytes(cap.get("other_reward", 0)))
