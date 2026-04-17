"""Service 层 - 网盘资源搜索 + 分享转存 (三端共用)"""

import re

from quark_cli.api import QuarkAPI
from quark_cli.search import PanSearch


class SearchService:
    """网盘资源搜索 + 分享链接转存 Service"""

    def __init__(self, client, searcher):
        # type: (QuarkAPI, PanSearch) -> None
        self._client = client
        self._searcher = searcher

    # ── 资源搜索 ──

    def search(self, keyword, source=None):
        """搜索网盘资源"""
        if source and source != "all":
            result = self._searcher.search(keyword, source)
        else:
            result = self._searcher.search_all(keyword)

        if not result.get("success"):
            return {"error": result.get("error", "搜索失败")}

        return {
            "keyword": keyword,
            "total": result.get("count", len(result.get("results", []))),
            "results": result.get("results", []),
            "errors": result.get("errors"),
        }

    def list_sources(self):
        """列出可用搜索源"""
        return self._searcher.list_sources()

    # ── 分享链接操作 ──

    def share_check(self, url):
        """检查分享链接有效性"""
        pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"error": "无法解析分享链接", "valid": False}

        resp = self._client.get_stoken(pwd_id, passcode)
        status = resp.get("status")
        result = {
            "url": url,
            "pwd_id": pwd_id,
            "passcode": passcode or "",
            "valid": status == 200,
        }

        if status == 200:
            stoken = resp["data"]["stoken"]
            detail = self._client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
            if detail.get("code") == 0:
                file_list = detail["data"]["list"]
                result["file_count"] = len(file_list)
                result["total_size"] = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
                result["total_size_fmt"] = QuarkAPI.format_bytes(result["total_size"])
        else:
            result["error"] = resp.get("message", "未知错误")

        return result

    def share_list(self, url):
        """列出分享链接中的文件"""
        pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"error": "无法解析分享链接"}

        resp = self._client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {"error": "分享链接无效: {}".format(resp.get("message", ""))}

        stoken = resp["data"]["stoken"]
        detail = self._client.get_share_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
        if detail.get("code") != 0:
            return {"error": "获取分享详情失败: {}".format(detail.get("message", ""))}

        file_list = detail["data"]["list"]
        items = []
        for f in file_list:
            is_dir = bool(f.get("dir"))
            items.append({
                "fid": f.get("fid", ""),
                "file_name": f.get("file_name", ""),
                "size": f.get("size", 0),
                "size_fmt": "<DIR>" if is_dir else QuarkAPI.format_bytes(f.get("size", 0)),
                "is_dir": is_dir,
                "share_fid_token": f.get("share_fid_token", ""),
            })

        total_size = sum(f.get("size", 0) for f in file_list if not f.get("dir"))
        return {
            "url": url,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "total": len(items),
            "total_size": total_size,
            "total_size_fmt": QuarkAPI.format_bytes(total_size),
            "items": items,
        }


    def share_subdir(self, url, pdir_fid):
        """列出分享链接中某个子目录的内容"""
        pwd_id, passcode, _, paths = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"error": "无法解析分享链接"}

        resp = self._client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {"error": "分享链接无效: {}".format(resp.get("message", ""))}

        stoken = resp["data"]["stoken"]
        detail = self._client.get_share_detail(pwd_id, stoken, pdir_fid)
        if detail.get("code") != 0:
            return {"error": "获取目录内容失败: {}".format(detail.get("message", ""))}

        file_list = detail["data"]["list"]
        items = []
        total_size = 0
        for f in file_list:
            is_dir = bool(f.get("dir"))
            size = f.get("size", 0)
            if not is_dir:
                total_size += size
            items.append({
                "fid": f.get("fid", ""),
                "file_name": f.get("file_name", ""),
                "size": size,
                "size_fmt": "<DIR>" if is_dir else QuarkAPI.format_bytes(size),
                "is_dir": is_dir,
                "share_fid_token": f.get("share_fid_token", ""),
            })

        return {
            "pdir_fid": pdir_fid,
            "total": len(items),
            "total_size": total_size,
            "total_size_fmt": QuarkAPI.format_bytes(total_size),
            "items": items,
        }

    def share_save(self, url, save_path, password="", fid_list=None, fid_token_list=None):
        """转存分享链接到指定目录

        Returns:
            dict: {saved, skipped, path, fids} or {error}
        """
        pwd_id, passcode, pdir_fid, paths = QuarkAPI.extract_share_url(url)
        if not pwd_id:
            return {"error": "无法解析分享链接"}
        if password:
            passcode = password

        # 验证账号
        info = self._client.init()
        if not info:
            return {"error": "账号验证失败，请检查 Cookie"}

        # 获取 stoken
        resp = self._client.get_stoken(pwd_id, passcode)
        if resp.get("status") != 200:
            return {"error": "分享链接无效: {}".format(resp.get("message", ""))}
        stoken = resp["data"]["stoken"]

        # 选择性转存: 如果传了 fid_list，直接用选中的文件
        if fid_list and fid_token_list and len(fid_list) == len(fid_token_list):
            # 构造虚拟 file_list 用于后续逻辑
            file_list = []
            for fid, token in zip(fid_list, fid_token_list):
                file_list.append({"fid": fid, "share_fid_token": token, "file_name": fid})
        else:
            # 获取文件列表
            detail = self._client.get_share_detail(pwd_id, stoken, pdir_fid)
            if detail.get("code") != 0:
                return {"error": "获取分享文件失败"}
            file_list = detail["data"]["list"]
            if not file_list:
                return {"error": "分享中没有文件"}

            # 如果只有一个文件夹，自动进入
            if len(file_list) == 1 and file_list[0].get("dir"):
                detail = self._client.get_share_detail(pwd_id, stoken, file_list[0]["fid"])
                if detail.get("code") == 0:
                    file_list = detail["data"]["list"]

        # 创建/获取目标目录
        save_path_n = re.sub(r"/{2,}", "/", "/{}".format(save_path))
        fids = self._client.get_fids([save_path_n])
        if fids:
            to_pdir_fid = fids[0]["fid"]
        else:
            mk = self._client.mkdir(save_path_n)
            if mk.get("code") != 0:
                return {"error": "创建目录失败: {}".format(mk.get("message", ""))}
            to_pdir_fid = mk["data"]["fid"]

        # 检查已存在文件，跳过
        dir_resp = self._client.ls_dir(to_pdir_fid)
        existing = set()
        if dir_resp.get("code") == 0:
            existing = {f["file_name"] for f in dir_resp["data"]["list"]}

        to_save = [f for f in file_list if f["file_name"] not in existing]
        skipped = len(file_list) - len(to_save)

        if not to_save:
            return {"saved": 0, "skipped": skipped, "path": save_path_n, "fids": []}

        # 分批转存
        saved_fids = []
        for i in range(0, len(to_save), 100):
            batch = to_save[i:i + 100]
            fid_list = [f["fid"] for f in batch]
            token_list = [f["share_fid_token"] for f in batch]
            save_resp = self._client.save_file(fid_list, token_list, to_pdir_fid, pwd_id, stoken)

            if save_resp.get("code") == 0:
                task_id = save_resp["data"]["task_id"]
                task_resp = self._client.query_task(task_id)
                if task_resp.get("code") == 0:
                    new_fids = task_resp["data"]["save_as"]["save_as_top_fids"]
                    saved_fids.extend(new_fids)

        return {
            "saved": len(saved_fids),
            "skipped": skipped,
            "path": save_path_n,
            "fids": saved_fids,
            "total_files": len(file_list),
        }
