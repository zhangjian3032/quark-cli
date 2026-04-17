#!/usr/bin/env python3
"""
Quark Drive Agent - 可直接被 Agent 框架加载的工具入口

兼容:
  - OpenAI Codex / Assistants function calling
  - Anthropic Claude Tool Use
  - LangChain / LangGraph Tool
  - 任意支持 JSON Schema tool 的 Agent 框架

Usage:
  # 作为独立服务运行
  python agent/main.py

  # 被 Agent 框架作为模块导入
  from agent.main import QuarkDriveAgent
  agent = QuarkDriveAgent()
  result = agent.call("quark_sign", {})
"""

import os
import sys
import json
import re
from typing import Any, Dict, Optional

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quark_cli.api import QuarkAPI
from quark_cli.config import ConfigManager


class QuarkDriveAgent:
    """
    夸克网盘 Agent — 提供 tool-use 兼容接口

    所有 tool 方法返回 dict，可直接作为 function calling 的 output。
    """

    def __init__(self, cookie: str = None, config_path: str = None):
        cfg_path = config_path or os.environ.get("QUARK_CONFIG")
        self.config = ConfigManager(cfg_path)
        self.config.load()

        cookie = cookie or os.environ.get("QUARK_COOKIE")
        if not cookie:
            cookies = self.config.get_cookies()
            cookie = cookies[0] if cookies else ""
        self.client = QuarkAPI(cookie)

    # ======================== Tools ========================

    def quark_sign(self, **kwargs) -> dict:
        """每日签到"""
        if not self.client.mparam:
            return {"success": False, "error": "Cookie 缺少移动端参数 (kps/sign/vcode)"}

        info = self.client.init()
        if not info:
            return {"success": False, "error": "Cookie 无效或已过期"}

        growth = self.client.get_growth_info()
        if not growth:
            return {"success": False, "error": "获取签到信息失败"}

        cap_sign = growth.get("cap_sign", {})
        if cap_sign.get("sign_daily"):
            return {
                "success": True,
                "already_signed": True,
                "reward_mb": int(cap_sign.get("sign_daily_reward", 0) / 1024 / 1024),
                "progress": f"{cap_sign.get('sign_progress', 0)}/{cap_sign.get('sign_target', 0)}",
            }

        ok, result = self.client.sign_in()
        if ok:
            return {
                "success": True,
                "already_signed": False,
                "reward_mb": int(result / 1024 / 1024),
                "progress": f"{cap_sign.get('sign_progress', 0) + 1}/{cap_sign.get('sign_target', 0)}",
            }
        return {"success": False, "error": str(result)}

    def quark_account_info(self, **kwargs) -> dict:
        """获取账号信息"""
        info = self.client.get_account_info()
        if not info:
            return {"success": False, "error": "获取账号信息失败"}

        result = {
            "success": True,
            "nickname": info.get("nickname"),
            "member_type": info.get("member_type"),
            "is_vip": info.get("super_vip", False),
        }

        growth = self.client.get_growth_info()
        if growth:
            result["total_space"] = QuarkAPI.format_bytes(growth["total_capacity"])
            result["sign_reward"] = QuarkAPI.format_bytes(
                growth.get("cap_composition", {}).get("sign_reward", 0)
            )
        return result

    def quark_share_check(self, url: str = "", **kwargs) -> dict:
        """检查分享链接有效性"""
        pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"success": False, "error": "无法解析分享链接"}

        resp = self.client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {
                "success": False,
                "valid": False,
                "error": resp.get("message", "分享链接无效"),
            }

        stoken = resp["data"]["stoken"]
        detail = self.client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
        file_list = detail.get("data", {}).get("list", [])

        return {
            "success": True,
            "valid": True,
            "pwd_id": pwd_id,
            "file_count": len(file_list),
            "total_size": QuarkAPI.format_bytes(
                sum(f.get("size", 0) for f in file_list if not f.get("dir"))
            ),
        }

    def quark_share_list(self, url: str = "", **kwargs) -> dict:
        """列出分享链接中的文件"""
        pwd_id, passcode, pdir_fid, _ = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"success": False, "error": "无法解析分享链接"}

        resp = self.client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {"success": False, "error": resp.get("message")}

        stoken = resp["data"]["stoken"]
        detail = self.client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
        if detail.get("code") != 0:
            return {"success": False, "error": detail.get("message")}

        file_list = detail["data"]["list"]
        return {
            "success": True,
            "files": [
                {
                    "name": f.get("file_name"),
                    "size": QuarkAPI.format_bytes(f.get("size", 0)) if not f.get("dir") else None,
                    "is_dir": f.get("dir", False),
                    "fid": f.get("fid"),
                }
                for f in file_list
            ],
        }

    def quark_share_save(
        self,
        url: str = "",
        savepath: str = "/来自分享",
        pattern: str = ".*",
        replace: str = "",
        **kwargs,
    ) -> dict:
        """转存分享链接中的文件"""
        pwd_id, passcode, pdir_fid, _ = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"success": False, "error": "无法解析分享链接"}

        info = self.client.init()
        if not info:
            return {"success": False, "error": "Cookie 无效"}

        resp = self.client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {"success": False, "error": resp.get("message")}
        stoken = resp["data"]["stoken"]

        detail = self.client.get_share_detail(pwd_id, stoken, pdir_fid)
        if detail.get("code") != 0:
            return {"success": False, "error": detail.get("message")}

        file_list = detail["data"]["list"]
        if not file_list:
            return {"success": False, "error": "分享中没有文件"}

        # 自动进入单文件夹
        if len(file_list) == 1 and file_list[0].get("dir"):
            detail = self.client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
            if detail.get("code") == 0:
                file_list = detail["data"]["list"]

        # 正则过滤
        filtered = [f for f in file_list if re.search(pattern, f["file_name"])]
        if not filtered:
            return {"success": False, "error": "没有匹配正则的文件"}

        # 确保目录
        savepath_n = re.sub(r"/{2,}", "/", f"/{savepath}")
        fids = self.client.get_fids([savepath_n])
        if fids:
            to_pdir_fid = fids[0]["fid"]
        else:
            mk = self.client.mkdir(savepath_n)
            if mk.get("code") != 0:
                return {"success": False, "error": f"创建目录失败: {mk.get('message')}"}
            to_pdir_fid = mk["data"]["fid"]

        # 过滤已存在
        dir_resp = self.client.ls_dir(to_pdir_fid)
        existing = (
            [f["file_name"] for f in dir_resp["data"]["list"]]
            if dir_resp.get("code") == 0
            else []
        )
        to_save = [f for f in filtered if f["file_name"] not in existing]
        if not to_save:
            return {"success": True, "saved_count": 0, "message": "没有需要转存的新文件"}

        # 转存
        fid_list = [f["fid"] for f in to_save]
        token_list = [f["share_fid_token"] for f in to_save]
        save_resp = self.client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)
        if save_resp.get("code") != 0:
            return {"success": False, "error": save_resp.get("message")}

        task_id = save_resp["data"]["task_id"]
        task_resp = self.client.query_task(task_id)

        saved_count = len(task_resp.get("data", {}).get("save_as", {}).get("save_as_top_fids", []))
        return {
            "success": True,
            "saved_count": saved_count,
            "total_matched": len(filtered),
            "skipped_existing": len(filtered) - len(to_save),
            "savepath": savepath_n,
        }

    def quark_drive_ls(self, path: str = "/", **kwargs) -> dict:
        """列出网盘目录"""
        if path == "/":
            pdir_fid = "0"
        else:
            path_n = re.sub(r"/{2,}", "/", f"/{path}")
            fids = self.client.get_fids([path_n])
            if not fids:
                return {"success": False, "error": f"目录不存在: {path}"}
            pdir_fid = fids[0]["fid"]

        resp = self.client.ls_dir(pdir_fid)
        if resp.get("code") != 0:
            return {"success": False, "error": resp.get("message")}

        return {
            "success": True,
            "path": path,
            "files": [
                {
                    "name": f.get("file_name"),
                    "size": QuarkAPI.format_bytes(f.get("size", 0))
                    if not (f.get("dir") or f.get("file_type") == 0)
                    else None,
                    "is_dir": bool(f.get("dir") or f.get("file_type") == 0),
                    "fid": f.get("fid"),
                }
                for f in resp["data"]["list"]
            ],
        }

    def quark_drive_search(self, keyword: str = "", path: str = "/", **kwargs) -> dict:
        """搜索网盘文件"""
        ls_result = self.quark_drive_ls(path=path)
        if not ls_result["success"]:
            return ls_result

        results = [
            f for f in ls_result["files"]
            if keyword.lower() in f["name"].lower()
        ]
        return {
            "success": True,
            "keyword": keyword,
            "results": results,
            "count": len(results),
        }

    def quark_resource_search(self, keyword: str = "", source: str = "pansou", **kwargs) -> dict:
        """通过搜索引擎搜索网盘资源"""
        from quark_cli.search import PanSearch
        searcher = PanSearch(self.config)
        return searcher.search(keyword, source)

    def quark_task_list(self, **kwargs) -> dict:
        """查看任务列表"""
        tasks = self.config.get_tasklist()
        return {
            "success": True,
            "count": len(tasks),
            "tasks": [
                {
                    "index": i + 1,
                    "name": t.get("taskname"),
                    "shareurl": t.get("shareurl"),
                    "savepath": t.get("savepath"),
                    "pattern": t.get("pattern", ".*"),
                    "enddate": t.get("enddate", ""),
                    "banned": t.get("shareurl_ban", ""),
                }
                for i, t in enumerate(tasks)
            ],
        }

    def quark_task_run(self, **kwargs) -> dict:
        """执行全部任务"""
        tasks = self.config.get_tasklist()
        if not tasks:
            return {"success": True, "message": "暂无任务"}

        info = self.client.init()
        if not info:
            return {"success": False, "error": "账号验证失败"}

        results = []
        for i, task in enumerate(tasks):
            try:
                r = self.quark_share_save(
                    url=task["shareurl"],
                    savepath=task["savepath"],
                    pattern=task.get("pattern", ".*"),
                    replace=task.get("replace", ""),
                )
                results.append({"index": i + 1, "name": task["taskname"], **r})
            except Exception as e:
                results.append({"index": i + 1, "name": task["taskname"], "success": False, "error": str(e)})

        return {
            "success": True,
            "total": len(tasks),
            "results": results,
        }

    # ======================== Dispatcher ========================

    TOOL_MAP = {
        "quark_sign": "quark_sign",
        "quark_account_info": "quark_account_info",
        "quark_share_check": "quark_share_check",
        "quark_share_list": "quark_share_list",
        "quark_share_save": "quark_share_save",
        "quark_drive_ls": "quark_drive_ls",
        "quark_drive_search": "quark_drive_search",
        "quark_resource_search": "quark_resource_search",
        "quark_task_list": "quark_task_list",
        "quark_task_run": "quark_task_run",
    }

    def call(self, tool_name: str, params: Dict[str, Any] = None) -> dict:
        """
        统一调用入口 — 兼容 OpenAI function calling / Claude tool_use

        Args:
            tool_name: 工具名称，如 "quark_sign"
            params: 工具参数字典

        Returns:
            dict: 工具执行结果
        """
        method_name = self.TOOL_MAP.get(tool_name)
        if not method_name:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        method = getattr(self, method_name, None)
        if not method:
            return {"success": False, "error": f"Method not implemented: {method_name}"}

        return method(**(params or {}))

    def get_openai_tools(self) -> list:
        """
        导出 OpenAI function calling 格式的 tools 定义
        可直接传入 openai.chat.completions.create(tools=...)
        """
        agent_def = self._load_agent_json()
        tools = []
        for t in agent_def.get("tools", []):
            properties = {}
            required = []
            for pname, pdef in t.get("parameters", {}).items():
                properties[pname] = {
                    "type": pdef.get("type", "string"),
                    "description": pdef.get("description", ""),
                }
                if pdef.get("default") is not None:
                    properties[pname]["default"] = pdef["default"]
                if pdef.get("required"):
                    required.append(pname)

            tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return tools

    def get_anthropic_tools(self) -> list:
        """
        导出 Anthropic Claude tool_use 格式的 tools 定义
        可直接传入 anthropic.messages.create(tools=...)
        """
        agent_def = self._load_agent_json()
        tools = []
        for t in agent_def.get("tools", []):
            properties = {}
            required = []
            for pname, pdef in t.get("parameters", {}).items():
                properties[pname] = {
                    "type": pdef.get("type", "string"),
                    "description": pdef.get("description", ""),
                }
                if pdef.get("required"):
                    required.append(pname)

            tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return tools

    def _load_agent_json(self) -> dict:
        agent_path = os.path.join(os.path.dirname(__file__), "agent.json")
        with open(agent_path, "r", encoding="utf-8") as f:
            return json.load(f)


# ======================== Standalone Entry ========================

def main():
    """CLI 模式运行 Agent（读取 stdin JSON 调用）"""
    import argparse

    parser = argparse.ArgumentParser(description="Quark Drive Agent")
    parser.add_argument("tool", nargs="?", help="Tool name to call")
    parser.add_argument("--params", default="{}", help="JSON params")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    parser.add_argument("--openai-schema", action="store_true", help="Print OpenAI tools schema")
    parser.add_argument("--anthropic-schema", action="store_true", help="Print Anthropic tools schema")
    args = parser.parse_args()

    agent = QuarkDriveAgent()

    if args.list_tools:
        for name in agent.TOOL_MAP:
            method = getattr(agent, name, None)
            doc = method.__doc__.strip() if method and method.__doc__ else ""
            print(f"  {name:30s} {doc}")
        return

    if args.openai_schema:
        print(json.dumps(agent.get_openai_tools(), ensure_ascii=False, indent=2))
        return

    if args.anthropic_schema:
        print(json.dumps(agent.get_anthropic_tools(), ensure_ascii=False, indent=2))
        return

    if not args.tool:
        parser.print_help()
        return

    params = json.loads(args.params)
    result = agent.call(args.tool, params)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
