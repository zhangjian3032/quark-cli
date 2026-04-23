"""
Guangya Pan API Client - 光鸭云盘 API 封装
https://www.guangyapan.com/

认证方式: did (设备 ID) + refresh_token (自动续期 access_token)
"""

import json
import time
import hashlib
import threading
import requests
from typing import Optional, Tuple, List, Dict, Any

from quark_cli import debug as dbg


class GuangyaAPI:
    """光鸭云盘 API 客户端"""

    BASE_URL = "https://api.guangyapan.com"
    TOKEN_URL = "https://account.guangyapan.com/v1/auth/token"
    CLIENT_ID = "aMe-8VSlkrbQXpUR"

    # 服务前缀
    SVC_FILE = "nd.bizuserres.s"     # 文件管理
    SVC_CLOUD = "nd.bizcloudcollection.s"  # 云添加 (磁力/种子)
    SVC_ASSETS = "nd.bizassets.s"    # 存储资产

    # 云添加任务状态
    TASK_PENDING = 0
    TASK_DOWNLOADING = 1
    TASK_COMPLETED = 2
    TASK_FAILED = 3

    # access_token 提前刷新的安全余量 (秒)
    _TOKEN_REFRESH_MARGIN = 300  # 过期前 5 分钟刷新

    def __init__(self, refresh_token: str = "", token: str = ""):
        """初始化

        Args:
            did: 设备 ID (device ID), 32 位 hex 字符串
            refresh_token: OIDC refresh token (以 "gy." 开头, 长期有效, 推荐)
            token: 直接提供 access_token (2h 有效期, 不推荐, 用于临时测试)
        """
        import uuid
        self.did = uuid.uuid4().hex  # 32-char hex 设备标识 (API 不校验)
        self.refresh_token = refresh_token.strip()
        self._access_token = token.strip()
        self._token_expires_at: float = 0  # unix timestamp
        self._token_lock = threading.Lock()

        self.is_active = False
        self.nickname = ""
        self.total_space = 0
        self.used_space = 0

        # 如果提供了直接 token 但没有 refresh_token, 给一个假的过期时间
        if self._access_token and not self._token_expires_at:
            self._token_expires_at = time.time() + 7200

    # ================================================================
    # Token 管理
    # ================================================================

    def _ensure_token(self) -> str:
        """确保 access_token 有效, 必要时用 refresh_token 刷新

        Returns:
            有效的 access_token
        """
        with self._token_lock:
            now = time.time()
            # token 还有效 (带安全余量)
            if self._access_token and now < self._token_expires_at - self._TOKEN_REFRESH_MARGIN:
                return self._access_token

            # 没有 refresh_token, 无法续期
            if not self.refresh_token:
                return self._access_token

            # 刷新
            dbg.log("GuangyaAPI", "access_token 即将过期, 正在刷新...")
            try:
                resp = requests.post(
                    self.TOKEN_URL,
                    json={
                        "grant_type": "refresh_token",
                        "client_id": self.CLIENT_ID,
                        "refresh_token": self.refresh_token,
                    },
                    timeout=10,
                )
                data = resp.json()
                if data.get("access_token"):
                    self._access_token = data["access_token"]
                    expires_in = data.get("expires_in", 7200)
                    self._token_expires_at = now + expires_in
                    # refresh_token 可能更新 (虽然光鸭目前不变)
                    if data.get("refresh_token"):
                        self.refresh_token = data["refresh_token"]
                    dbg.log("GuangyaAPI", f"token 刷新成功, {expires_in}s 后过期")
                else:
                    dbg.log("GuangyaAPI", f"token 刷新失败: {data}")
            except Exception as e:
                dbg.log("GuangyaAPI", f"token 刷新异常: {e}")

            return self._access_token

    # ================================================================
    # 内部请求
    # ================================================================

    def _request(
        self,
        svc: str,
        path: str,
        payload: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """发送 POST JSON 请求

        Args:
            svc: 服务前缀, e.g. "nd.bizuserres.s"
            path: 接口路径, e.g. "/v1/file/get_file_list"
            payload: 请求体 (dict → JSON)
        """
        url = f"{self.BASE_URL}/{svc}{path}"
        access_token = self._ensure_token()

        headers = {
            "content-type": kwargs.pop("content_type", "application/json"),
            "did": self.did,
            "dt": "4",
        }
        if access_token:
            headers["authorization"] = f"Bearer {access_token}"

        dbg.log_request("POST", url, body=payload)

        try:
            t0 = time.time()
            if kwargs.get("files"):
                # multipart form — 不设置 content-type, 让 requests 自动处理
                del headers["content-type"]
                resp = requests.post(
                    url, headers=headers, files=kwargs.pop("files"), timeout=60
                )
            else:
                resp = requests.post(
                    url, headers=headers, json=payload or {}, timeout=30
                )
            elapsed_ms = (time.time() - t0) * 1000

            try:
                body = resp.json()
            except Exception:
                body = resp.text[:500] if resp.text else None
            dbg.log_response(resp.status_code, url, body=body, elapsed_ms=elapsed_ms)

            if isinstance(body, dict):
                # token 过期, 自动重试一次
                if body.get("code") == 117 and self.refresh_token:
                    dbg.log("GuangyaAPI", "收到 117 无效token, 强制刷新重试")
                    self._token_expires_at = 0  # 强制刷新
                    return self._request(svc, path, payload, **kwargs)
                return body
            return {"code": -1, "msg": "invalid response", "raw": body}
        except Exception as e:
            dbg.log("GuangyaAPI", f"请求异常: {e}")
            return {"code": -1, "msg": str(e)}

    def _ok(self, resp: dict) -> bool:
        """判断响应是否成功"""
        return resp.get("msg") == "success" or resp.get("code", -1) == 0

    # ================================================================
    # 账号 / 初始化
    # ================================================================

    def get_assets(self) -> Optional[dict]:
        """获取存储空间信息

        Returns:
            {totalSpaceSize, usedSpaceSize, vipStatus, vipLeftTime, vipExpireTime}
        """
        resp = self._request(self.SVC_ASSETS, "/v1/get_assets")
        if self._ok(resp):
            return resp.get("data")
        return None

    def init(self) -> Optional[dict]:
        """初始化账号, 验证凭证有效性

        Returns:
            assets dict or None
        """
        info = self.get_assets()
        if info:
            self.is_active = True
            self.total_space = info.get("totalSpaceSize", 0)
            self.used_space = info.get("usedSpaceSize", 0)
            return info
        return None

    # ================================================================
    # 文件管理
    # ================================================================

    def ls_dir(
        self,
        parent_id: str = "",
        page_size: int = 50,
        order_by: int = 3,
        sort_type: int = 1,
        file_types: Optional[List[int]] = None,
    ) -> dict:
        """列出目录文件 (cursor 分页, 自动翻页)

        Args:
            parent_id: 父目录 ID, 空字符串 "" 表示根目录
            page_size: 每页数量
            order_by: 排序字段 (3=更新时间)
            sort_type: 排序方向 (1=降序)
            file_types: 文件类型过滤

        Returns:
            {msg, data: {total, list: [{fileId, fileName, fileSize, ...}]}}
        """
        all_items: List[dict] = []
        cursor: str = ""

        while True:
            payload: Dict[str, Any] = {
                "parentId": parent_id,
                "pageSize": page_size,
                "orderBy": order_by,
                "sortType": sort_type,
            }
            if cursor:
                payload["cursor"] = cursor
            if file_types is not None:
                payload["fileTypes"] = file_types

            resp = self._request(self.SVC_FILE, "/v1/file/get_file_list", payload)
            if not self._ok(resp):
                return resp

            data = resp.get("data", {})
            items = data.get("list", [])
            total = data.get("total", 0)
            all_items.extend(items)

            next_cursor = data.get("cursor", "")
            if not items or len(all_items) >= total or not next_cursor:
                break
            cursor = next_cursor

        return {
            "msg": "success",
            "data": {"total": len(all_items), "list": all_items},
        }

    def get_file_detail(self, file_id: str) -> Optional[dict]:
        """获取文件详情

        Returns:
            {fileInfo, location, sizeInfo} or None
        """
        resp = self._request(self.SVC_FILE, "/v1/file/get_file_detail", {"fileId": file_id})
        if self._ok(resp):
            return resp.get("data")
        return None

    def mkdir(self, dir_name: str, parent_id: str = "") -> Optional[dict]:
        """创建目录

        Args:
            dir_name: 目录名
            parent_id: 父目录 ID, "" 表示根目录

        Returns:
            {fileId, fileName, ...} or None
        """
        payload = {
            "parentId": parent_id,
            "dirName": dir_name,
            "failIfNameExist": True,
        }
        resp = self._request(self.SVC_FILE, "/v1/file/create_dir", payload)
        if self._ok(resp):
            return resp.get("data")
        return None

    def rename(self, file_id: str, new_name: str) -> bool:
        """重命名文件/目录

        Returns:
            True if success
        """
        payload = {"fileId": file_id, "newName": new_name}
        resp = self._request(self.SVC_FILE, "/v1/file/rename", payload)
        return self._ok(resp)

    def delete(self, file_ids: List[str], wait: bool = True) -> dict:
        """删除文件/目录

        Args:
            file_ids: 文件 ID 列表
            wait: 是否等待任务完成

        Returns:
            响应 dict
        """
        payload = {"fileIds": file_ids}
        resp = self._request(self.SVC_FILE, "/v1/file/delete_file", payload)
        if self._ok(resp) and wait:
            task_id = resp.get("data", {}).get("taskId")
            if task_id:
                self._wait_task(task_id)
        return resp


    def copy_file(self, file_ids: List[str], dest_parent_id: str = "", wait: bool = True) -> dict:
        """复制文件/目录到目标目录

        Args:
            file_ids: 要复制的文件 ID 列表
            dest_parent_id: 目标父目录 ID ("" = 根目录)
            wait: 是否等待异步任务完成

        Returns:
            响应 dict
        """
        payload = {"fileIds": file_ids, "destParentId": dest_parent_id}
        resp = self._request(self.SVC_FILE, "/v1/file/copy", payload)
        if self._ok(resp) and wait:
            task_id = resp.get("data", {}).get("taskId")
            if task_id:
                self._wait_task(task_id)
        return resp

    def move_file(self, file_ids: List[str], dest_parent_id: str = "", wait: bool = True) -> dict:
        """移动文件/目录到目标目录

        Args:
            file_ids: 要移动的文件 ID 列表
            dest_parent_id: 目标父目录 ID ("" = 根目录)
            wait: 是否等待异步任务完成

        Returns:
            响应 dict
        """
        payload = {"fileIds": file_ids, "destParentId": dest_parent_id}
        resp = self._request(self.SVC_FILE, "/v1/file/move", payload)
        if self._ok(resp) and wait:
            task_id = resp.get("data", {}).get("taskId")
            if task_id:
                self._wait_task(task_id)
        return resp

    def find_dir_by_name(self, name: str, parent_id: str = "") -> Optional[str]:
        """按名称在指定目录下查找子目录, 返回 fileId 或 None"""
        result = self.ls_dir(parent_id=parent_id, page_size=200)
        if not self._ok(result):
            return None
        for item in result.get("data", {}).get("list", []):
            if item.get("fileName") == name and item.get("fileType") == 0:
                return item.get("fileId")
        return None

    def resolve_dir_path(self, path: str) -> Optional[str]:
        """按路径字符串解析目录 ID, 如 "电影/2026"

        从根目录开始逐级查找, 找不到则自动创建.

        Returns:
            目标目录的 fileId, 失败返回 None
        """
        parts = [p.strip() for p in path.replace("\\", "/").split("/") if p.strip()]
        if not parts:
            return ""  # 根目录
        current_id = ""
        for part in parts:
            found = self.find_dir_by_name(part, parent_id=current_id)
            if found:
                current_id = found
            else:
                # 自动创建
                new_dir = self.mkdir(part, parent_id=current_id)
                if not new_dir:
                    return None
                current_id = new_dir.get("fileId", "")
                if not current_id:
                    return None
        return current_id

    def _wait_task(self, task_id: str, timeout: int = 120) -> bool:
        """等待异步任务完成

        Returns:
            True if task completed within timeout
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._request(
                self.SVC_FILE, "/v1/get_task_status", {"taskId": task_id}
            )
            if self._ok(resp):
                status = resp.get("data", {}).get("status")
                if status == 2:  # done
                    return True
            time.sleep(1)
        return False

    # ================================================================
    # 下载
    # ================================================================

    def download(self, file_id: str) -> Optional[dict]:
        """获取下载链接

        Returns:
            {signedURL, urlDuration, ...} or None
        """
        resp = self._request(
            self.SVC_FILE, "/v1/get_res_download_url", {"fileId": file_id}
        )
        if self._ok(resp):
            return resp.get("data")
        return None

    # ================================================================
    # 上传
    # ================================================================

    def upload_file(
        self,
        file_path: str,
        parent_id: str = "",
        file_name: Optional[str] = None,
    ) -> Optional[dict]:
        """上传文件

        流程: get_res_center_token → OSS 上传 → check_can_flash_upload → poll get_info_by_task_id

        Args:
            file_path: 本地文件路径
            parent_id: 目标目录 ID
            file_name: 远程文件名 (默认取本地文件名)

        Returns:
            上传成功后的文件信息 dict, or None
        """
        import os

        if file_name is None:
            file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # 计算 MD5
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        file_md5 = md5.hexdigest()

        # Step 1: 获取上传凭证
        token_payload = {
            "capacity": 2,
            "name": file_name,
            "res": {"fileSize": file_size, "md5": file_md5},
            "parentId": parent_id,
        }
        token_resp = self._request(
            self.SVC_FILE, "/v1/get_res_center_token", token_payload
        )
        if not self._ok(token_resp):
            dbg.log("GuangyaAPI", f"获取上传凭证失败: {token_resp}")
            return None

        data = token_resp["data"]
        gcid = data["gcid"]
        creds = data["creds"]
        endpoint = data["endPoint"]
        bucket = data["bucketName"]
        object_path = data["objectPath"]

        # Step 2: 上传到 OSS (使用 STS 临时凭证)
        try:
            import boto3
            from botocore.config import Config as BotoConfig

            s3 = boto3.client(
                "s3",
                endpoint_url=f"https://{endpoint}",
                aws_access_key_id=creds["accessKeyID"],
                aws_secret_access_key=creds["secretAccessKey"],
                aws_session_token=creds["sessionToken"],
                config=BotoConfig(signature_version="s3v4"),
            )
            s3.upload_file(file_path, bucket, object_path)
        except ImportError:
            # 没有 boto3, 用 requests PUT 简单上传
            put_url = f"https://{bucket}.{endpoint}/{object_path}"
            put_headers = {
                "x-oss-security-token": creds["sessionToken"],
            }
            with open(file_path, "rb") as f:
                put_resp = requests.put(
                    put_url, data=f, headers=put_headers, timeout=300
                )
            if put_resp.status_code not in (200, 201, 204):
                dbg.log("GuangyaAPI", f"OSS 上传失败: {put_resp.status_code}")
                return None

        # Step 3: 确认上传
        flash_resp = self._request(
            self.SVC_FILE,
            "/v1/check_can_flash_upload",
            {"taskId": data.get("taskId", gcid), "gcid": gcid},
        )
        task_id = None
        if self._ok(flash_resp):
            task_id = flash_resp.get("data", {}).get("taskId")

        # Step 4: 轮询获取文件信息
        if task_id:
            for _ in range(30):
                info_resp = self._request(
                    self.SVC_FILE,
                    "/v1/file/get_info_by_task_id",
                    {"taskId": task_id},
                )
                if self._ok(info_resp) and info_resp.get("data", {}).get("fileId"):
                    return info_resp["data"]
                time.sleep(1)

        return None

    # ================================================================
    # 直链
    # ================================================================

    def set_direct_link(self, file_id: str) -> bool:
        """为文件/目录开启直链

        Returns:
            True if success
        """
        resp = self._request(self.SVC_FILE, "/v1/set_direct_link", {"fileId": file_id})
        return self._ok(resp)

    # ================================================================
    # 云添加 — 磁力 / 种子
    # ================================================================

    def resolve_magnet(self, magnet_url: str) -> Optional[dict]:
        """解析磁力链接

        Args:
            magnet_url: 磁力链接 (magnet:?xt=urn:btih:...)

        Returns:
            {resType, btResInfo: {infoHash, fileName, fileSize, subfiles, excludeIndices}, url}
            or None
        """
        payload = {"url": magnet_url}
        resp = self._request(self.SVC_CLOUD, "/v1/resolve_res", payload)
        if self._ok(resp):
            return resp.get("data")
        return None

    def resolve_torrent(self, torrent_path: str) -> Optional[dict]:
        """解析种子文件

        Args:
            torrent_path: 本地 .torrent 文件路径

        Returns:
            {resType, btResInfo: {infoHash, fileName, fileSize, subfiles, excludeIndices}}
            or None
        """
        with open(torrent_path, "rb") as f:
            resp = self._request(
                self.SVC_CLOUD,
                "/v1/resolve_torrent",
                files={"torrent": f},
            )
        if self._ok(resp):
            return resp.get("data")
        return None

    def create_cloud_task(
        self,
        url: str,
        parent_id: str,
        file_indexes: Optional[List[int]] = None,
        new_name: Optional[str] = None,
    ) -> Optional[dict]:
        """创建云添加任务 (磁力 / 种子)

        Args:
            url: 磁力链接 (magnet:?xt=urn:btih:...)
            parent_id: 保存目录 ID
            file_indexes: 选中的子文件索引列表 (全选则传所有索引)
            new_name: 重命名 (可选)

        Returns:
            {taskId, url} or None
        """
        payload: Dict[str, Any] = {
            "url": url,
            "parentId": parent_id,
        }
        if file_indexes is not None:
            payload["fileIndexes"] = file_indexes
        if new_name:
            payload["newName"] = new_name

        resp = self._request(self.SVC_CLOUD, "/v1/create_task", payload)
        if self._ok(resp):
            return resp.get("data")
        return None

    def list_cloud_tasks(
        self,
        page_size: int = 50,
        status: Optional[List[int]] = None,
        task_ids: Optional[List[str]] = None,
    ) -> Optional[dict]:
        """查询云添加任务列表

        Args:
            page_size: 每页数量
            status: 状态过滤 (0=pending, 1=downloading, 2=completed, 3=failed, 5=?)
            task_ids: 按任务 ID 查询

        Returns:
            {statusCounts, list, total, cursor}
        """
        payload: Dict[str, Any] = {"pageSize": page_size}
        if status is not None:
            payload["status"] = status
        if task_ids is not None:
            payload["taskIds"] = task_ids

        resp = self._request(self.SVC_CLOUD, "/v1/list_task", payload)
        if self._ok(resp):
            return resp.get("data")
        return None

    def poll_cloud_task(
        self,
        task_id: str,
        timeout: int = 600,
        interval: float = 3.0,
        callback=None,
    ) -> Optional[dict]:
        """轮询云添加任务直到完成

        Args:
            task_id: 任务 ID
            timeout: 超时秒数
            interval: 轮询间隔
            callback: 进度回调 fn(task_info) → bool, 返回 False 取消

        Returns:
            完成后的 task info dict, or None if timeout/cancelled
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.list_cloud_tasks(task_ids=[task_id])
            if data and data.get("list"):
                task = data["list"][0]
                status = task.get("status", 0)

                if callback and not callback(task):
                    return None  # cancelled by callback

                if status == self.TASK_COMPLETED:
                    return task
                if status == self.TASK_FAILED:
                    dbg.log("GuangyaAPI", f"云添加任务失败: {task}")
                    return task
            time.sleep(interval)
        return None

    def delete_cloud_tasks(self, task_ids: List[str]) -> bool:
        """删除云添加任务

        Returns:
            True if success
        """
        payload = {"taskIds": task_ids}
        resp = self._request(self.SVC_CLOUD, "/v2/delete_task", payload)
        return self._ok(resp) or bool(resp.get("data", {}).get("taskIds"))

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def format_bytes(size_bytes: int) -> str:
        """格式化字节大小"""
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.2f} {units[i]}"
