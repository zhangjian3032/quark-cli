"""Service 层 - 夸克账号管理 (三端共用)"""

from quark_cli.api import QuarkAPI


class AccountService:
    """夸克网盘账号管理 Service"""

    VIP_MAP = {
        "NORMAL": "普通用户",
        "EXP_SVIP": "88VIP",
        "SUPER_VIP": "SVIP",
        "Z_VIP": "SVIP+",
    }

    def __init__(self, client):
        # type: (QuarkAPI) -> None
        self._client = client

    def get_info(self):
        """获取账号基本信息 + 空间 + 签到状态"""
        info = self._client.get_account_info()
        if not info:
            return {"error": "Cookie 无效或已过期，请重新配置"}

        result = {
            "nickname": info.get("nickname", ""),
            "phone": info.get("phone", ""),
            "avatar": info.get("avatar_url", ""),
            "member_type": info.get("member_type", ""),
            "super_vip": bool(info.get("super_vip")),
            "cookie_valid": True,
        }

        # 成长信息（空间 + 签到）
        growth = self._client.get_growth_info()
        if growth:
            member_type = growth.get("member_type", "")
            total_cap = growth.get("total_capacity", 0)
            use_cap = growth.get("use_capacity", 0)
            cap_comp = growth.get("cap_composition", {}) or {}
            cap_sign = growth.get("cap_sign", {}) or {}

            result["vip_type"] = self.VIP_MAP.get(member_type, member_type)
            result["total_capacity"] = total_cap
            result["use_capacity"] = use_cap
            result["total_fmt"] = QuarkAPI.format_bytes(total_cap)
            result["used_fmt"] = QuarkAPI.format_bytes(use_cap)
            result["used_pct"] = round(use_cap / total_cap * 100, 1) if total_cap > 0 else 0
            result["sign_reward"] = cap_comp.get("sign_reward", 0)
            result["sign_reward_fmt"] = QuarkAPI.format_bytes(cap_comp.get("sign_reward", 0))
            result["other_reward"] = cap_comp.get("other_reward", 0)
            result["other_reward_fmt"] = QuarkAPI.format_bytes(cap_comp.get("other_reward", 0))

            # 签到状态
            result["signed_today"] = bool(cap_sign.get("sign_daily"))
            result["sign_progress"] = cap_sign.get("sign_progress", 0)
            result["sign_target"] = cap_sign.get("sign_target", 0)
            result["sign_daily_reward"] = cap_sign.get("sign_daily_reward", 0)
            result["sign_daily_reward_fmt"] = QuarkAPI.format_bytes(
                cap_sign.get("sign_daily_reward", 0)
            )
            # 移动端参数检查
            result["can_sign"] = bool(self._client.mparam)

        return result

    def verify(self):
        """验证 Cookie 有效性"""
        info = self._client.get_account_info()
        if info:
            return {"valid": True, "nickname": info.get("nickname", "")}
        return {"valid": False}

    def sign_in(self):
        """每日签到"""
        if not self._client.mparam:
            return {"error": "Cookie 缺少移动端参数 (kps/sign/vcode)，无法签到。请从夸克 APP 抓取完整 Cookie。"}

        info = self._client.init()
        if not info:
            return {"error": "账号验证失败"}

        growth = self._client.get_growth_info()
        if not growth:
            return {"error": "获取签到信息失败"}

        cap_sign = growth.get("cap_sign", {}) or {}

        if cap_sign.get("sign_daily"):
            reward = cap_sign.get("sign_daily_reward", 0)
            return {
                "success": True,
                "already_signed": True,
                "reward": reward,
                "reward_fmt": QuarkAPI.format_bytes(reward),
                "progress": cap_sign.get("sign_progress", 0),
                "target": cap_sign.get("sign_target", 0),
            }

        ok, result = self._client.sign_in()
        if ok:
            progress = cap_sign.get("sign_progress", 0) + 1
            return {
                "success": True,
                "already_signed": False,
                "reward": result,
                "reward_fmt": QuarkAPI.format_bytes(result),
                "progress": progress,
                "target": cap_sign.get("sign_target", 0),
            }
        return {"success": False, "error": str(result)}
