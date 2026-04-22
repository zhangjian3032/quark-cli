"""Service 层 - 光鸭云盘文件操作 (三端共用)"""

from quark_cli.guangya_api import GuangyaAPI


class GuangyaDriveService:
    """光鸭云盘文件管理 Service — CLI / API / Web 共享"""

    def __init__(self, client):
        # type: (GuangyaAPI) -> None
        self._client = client

    # ── 目录浏览 ──

    def list_dir(self, parent_id=""):
        """列出目录内容"""
        resp = self._client.ls_dir(parent_id=parent_id)
        if resp.get("msg") != "success":
            return {"error": "列目录失败: {}".format(resp.get("msg", ""))}

        items = []
        total_size = 0
        for f in resp["data"]["list"]:
            is_dir = f.get("resType") == 2
            size = f.get("fileSize") or 0
            if not is_dir:
                total_size += size
            items.append({
                "fileId": f.get("fileId", ""),
                "fileName": f.get("fileName", ""),
                "fileSize": size,
                "size_fmt": "<DIR>" if is_dir else GuangyaAPI.format_bytes(size),
                "is_dir": is_dir,
                "ext": f.get("ext", ""),
                "ctime": f.get("ctime", 0),
                "utime": f.get("utime", 0),
            })

        dirs_count = sum(1 for i in items if i["is_dir"])
        files_count = len(items) - dirs_count

        return {
            "parentId": parent_id,
            "items": items,
            "total": len(items),
            "dirs_count": dirs_count,
            "files_count": files_count,
            "total_size": total_size,
            "total_size_fmt": GuangyaAPI.format_bytes(total_size),
        }

    # ── 创建目录 ──

    def mkdir(self, dir_name, parent_id=""):
        result = self._client.mkdir(dir_name, parent_id=parent_id)
        if result:
            return {"fileId": result["fileId"], "fileName": result.get("fileName", dir_name)}
        return {"error": "创建目录失败"}

    # ── 重命名 ──

    def rename(self, file_id, new_name):
        if self._client.rename(file_id, new_name):
            return {"fileId": file_id, "newName": new_name}
        return {"error": "重命名失败"}

    # ── 删除 ──

    def delete(self, file_ids):
        if not file_ids:
            return {"error": "请指定要删除的文件"}
        resp = self._client.delete(file_ids, wait=True)
        if resp.get("msg") == "success" or resp.get("data", {}).get("taskId"):
            return {"deleted": len(file_ids), "fileIds": file_ids}
        return {"error": "删除失败: {}".format(resp.get("msg", ""))}

    # ── 下载链接 ──

    def get_download_url(self, file_id):
        result = self._client.download(file_id)
        if not result:
            return {"error": "获取下载链接失败"}
        return {
            "signedURL": result.get("signedURL", ""),
            "urlDuration": result.get("urlDuration", 0),
        }

    # ── 空间信息 ──

    def get_space_info(self):
        info = self._client.init()
        if not info:
            return {"error": "凭证无效"}
        return {
            "totalSpaceSize": info.get("totalSpaceSize", 0),
            "usedSpaceSize": info.get("usedSpaceSize", 0),
            "total_fmt": GuangyaAPI.format_bytes(info.get("totalSpaceSize", 0)),
            "used_fmt": GuangyaAPI.format_bytes(info.get("usedSpaceSize", 0)),
            "vipStatus": info.get("vipStatus", False),
            "vipExpireTime": info.get("vipExpireTime", 0),
        }


    # ── 下载到服务端本地 ──

    def download_to_local(self, file_id, save_dir, filename=None):
        """下载文件到服务端本地磁盘

        Args:
            file_id: 文件 fileId
            save_dir: 本地保存目录
            filename: 文件名 (默认使用云端文件名)

        Returns:
            {"path": "/saved/path", "size": ..., "fileName": ...} or {"error": ...}
        """
        import os
        import requests as _requests

        # 获取文件详情 (拿文件名)
        if not filename:
            detail = self._client.get_file_detail(file_id)
            if detail:
                filename = detail.get("fileName", file_id)
            else:
                filename = file_id

        # 获取签名下载链接
        dl = self._client.download(file_id)
        if not dl or not dl.get("signedURL"):
            return {"error": "获取下载链接失败"}

        signed_url = dl["signedURL"]

        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        # 流式下载
        try:
            resp = _requests.get(signed_url, stream=True, timeout=600)
            resp.raise_for_status()
            total = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            return {
                "path": save_path,
                "fileName": filename,
                "size": total,
                "size_fmt": GuangyaAPI.format_bytes(total),
            }
        except Exception as e:
            # 清理不完整文件
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            return {"error": "下载失败: {}".format(str(e))}
    # ── 磁力解析 ──

    def resolve_magnet(self, magnet_url):
        result = self._client.resolve_magnet(magnet_url)
        if not result:
            return {"error": "解析磁力链接失败"}
        return result

    # ── 种子解析 ──

    def resolve_torrent(self, torrent_path):
        result = self._client.resolve_torrent(torrent_path)
        if not result:
            return {"error": "解析种子失败"}
        return result

    # ── 创建云添加任务 ──

    def create_cloud_task(self, url, parent_id, file_indexes=None, new_name=None):
        result = self._client.create_cloud_task(
            url=url, parent_id=parent_id,
            file_indexes=file_indexes, new_name=new_name,
        )
        if not result:
            return {"error": "创建云添加任务失败"}
        return result

    # ── 云添加任务列表 ──

    def list_cloud_tasks(self, status=None):
        result = self._client.list_cloud_tasks(status=status)
        if result is None:
            return {"error": "查询云添加任务失败"}
        return result

    # ── 删除云添加任务 ──

    def delete_cloud_tasks(self, task_ids):
        if self._client.delete_cloud_tasks(task_ids):
            return {"deleted": task_ids}
        return {"error": "删除云添加任务失败"}
