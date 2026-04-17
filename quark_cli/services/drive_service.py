"""Service 层 - 夸克网盘文件操作 (三端共用)"""

import re

from quark_cli.api import QuarkAPI


class DriveService:
    """夸克网盘文件管理 Service — CLI / API / Web 共享"""

    def __init__(self, client):
        # type: (QuarkAPI) -> None
        self._client = client

    # ── 目录浏览 ──

    def list_dir(self, path="/"):
        """列出目录内容，返回结构化数据"""
        pdir_fid = self._resolve_fid(path)
        if pdir_fid is None:
            return {"error": "目录不存在: {}".format(path)}

        resp = self._client.ls_dir(pdir_fid, fetch_full_path=1)
        if resp.get("code") != 0:
            return {"error": "列出目录失败: {}".format(resp.get("message", ""))}

        file_list = resp["data"]["list"]
        items = []
        total_size = 0
        for f in file_list:
            is_dir = bool(f.get("dir") or f.get("file_type") == 0)
            size = f.get("size", 0) or 0
            if not is_dir:
                total_size += size
            items.append({
                "fid": f.get("fid", ""),
                "file_name": f.get("file_name", ""),
                "size": size,
                "size_fmt": "<DIR>" if is_dir else QuarkAPI.format_bytes(size),
                "is_dir": is_dir,
                "updated_at": f.get("updated_at", ""),
                "file_type": f.get("file_type", 0),
                "format_type": f.get("format_type", ""),
                "obj_category": f.get("obj_category", ""),
            })

        dirs_count = sum(1 for i in items if i["is_dir"])
        files_count = len(items) - dirs_count

        return {
            "path": path,
            "fid": pdir_fid,
            "items": items,
            "total": len(items),
            "dirs_count": dirs_count,
            "files_count": files_count,
            "total_size": total_size,
            "total_size_fmt": QuarkAPI.format_bytes(total_size),
        }

    # ── 创建目录 ──

    def mkdir(self, path):
        path = re.sub(r"/{2,}", "/", "/{}".format(path))
        resp = self._client.mkdir(path)
        if resp.get("code") == 0:
            return {"path": path, "fid": resp["data"]["fid"]}
        return {"error": "创建目录失败: {}".format(resp.get("message", ""))}

    # ── 重命名 ──

    def rename(self, fid, new_name):
        resp = self._client.rename(fid, new_name)
        if resp.get("code") == 0:
            return {"fid": fid, "new_name": new_name}
        return {"error": "重命名失败: {}".format(resp.get("message", ""))}

    # ── 删除 ──

    def delete(self, fids):
        """删除文件/文件夹 (移入回收站)"""
        if not fids:
            return {"error": "请指定要删除的文件"}
        resp = self._client.delete(fids)
        if resp.get("code") == 0:
            task_id = resp["data"]["task_id"]
            task_resp = self._client.query_task(task_id)
            if task_resp.get("code") == 0:
                return {"deleted": len(fids), "fids": fids}
            return {"error": "删除任务失败: {}".format(task_resp.get("message", ""))}
        return {"error": "删除失败: {}".format(resp.get("message", ""))}

    # ── 下载链接 ──

    def get_download_url(self, fids):
        """获取文件下载链接"""
        if isinstance(fids, str):
            fids = [fids]
        resp, cookie = self._client.download(fids)
        if resp.get("code") != 0:
            return {"error": "获取下载链接失败: {}".format(resp.get("message", ""))}

        items = []
        for item in resp.get("data", []):
            items.append({
                "file_name": item.get("file_name", ""),
                "size": item.get("size", 0),
                "size_fmt": QuarkAPI.format_bytes(item.get("size", 0)),
                "download_url": item.get("download_url", ""),
                "cookie": cookie or "",
            })
        return {"items": items}

    # ── 搜索 ──

    def search(self, keyword, path="/"):
        """在指定目录内搜索文件"""
        pdir_fid = self._resolve_fid(path)
        if pdir_fid is None:
            return {"error": "目录不存在: {}".format(path)}

        resp = self._client.ls_dir(pdir_fid, fetch_full_path=1)
        if resp.get("code") != 0:
            return {"error": "搜索失败: {}".format(resp.get("message", ""))}

        kw_lower = keyword.lower()
        results = []
        for f in resp["data"]["list"]:
            name = f.get("file_name", "")
            if kw_lower in name.lower():
                is_dir = bool(f.get("dir") or f.get("file_type") == 0)
                results.append({
                    "fid": f.get("fid", ""),
                    "file_name": name,
                    "size": f.get("size", 0),
                    "size_fmt": "<DIR>" if is_dir else QuarkAPI.format_bytes(f.get("size", 0)),
                    "is_dir": is_dir,
                    "updated_at": f.get("updated_at", ""),
                })

        return {
            "keyword": keyword,
            "path": path,
            "total": len(results),
            "items": results,
        }

    # ── 空间信息 ──

    def get_space_info(self):
        """获取网盘空间信息"""
        info = self._client.init()
        if not info:
            return {"error": "账号未登录或 Cookie 无效"}
        member = info.get("member", {}) or {}
        return {
            "nickname": info.get("nickname", ""),
            "total_capacity": info.get("total_capacity", 0),
            "use_capacity": info.get("use_capacity", 0),
            "total_fmt": QuarkAPI.format_bytes(info.get("total_capacity", 0)),
            "used_fmt": QuarkAPI.format_bytes(info.get("use_capacity", 0)),
            "is_vip": member.get("is_vip", False),
            "vip_title": member.get("title", ""),
        }

    # ── 内部工具 ──

    def _resolve_fid(self, path):
        """将路径转换为 fid，根目录为 '0'"""
        if not path or path == "/":
            return "0"
        path_normalized = re.sub(r"/{2,}", "/", "/{}".format(path))
        fids = self._client.get_fids([path_normalized])
        if not fids:
            return None
        return fids[0]["fid"]
