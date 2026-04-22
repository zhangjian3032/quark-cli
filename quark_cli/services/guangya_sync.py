"""光鸭云盘 Sync 引擎 — 递归目录下载到本地"""

import os
import time
import uuid
import threading
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("quark_cli.guangya_sync")


class SyncTask:
    """单个 Sync 任务的状态"""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    def __init__(self, task_id: str, file_id: str, save_dir: str, file_name: str = ""):
        self.task_id = task_id
        self.file_id = file_id
        self.save_dir = save_dir
        self.file_name = file_name  # 根目录/文件名

        self.status = self.STATUS_PENDING
        self.error = ""
        self.started_at: float = 0
        self.finished_at: float = 0

        # 进度
        self.total_files = 0       # 需下载的文件总数
        self.total_dirs = 0        # 需创建的目录总数
        self.done_files = 0        # 已完成文件数
        self.done_dirs = 0         # 已创建目录数
        self.failed_files = 0      # 失败文件数
        self.skipped_files = 0     # 跳过 (已存在) 文件数
        self.total_bytes = 0       # 需下载总字节
        self.done_bytes = 0        # 已下载字节
        self.current_file = ""     # 当前正在下载的文件
        self.current_file_bytes = 0  # 当前文件已下载字节
        self.current_file_total = 0  # 当前文件总字节

        self.log: List[str] = []   # 日志 (最近 200 条)

        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self):
        return self._cancelled

    def to_dict(self) -> dict:
        elapsed = 0
        if self.started_at:
            end = self.finished_at or time.time()
            elapsed = round(end - self.started_at, 1)

        speed = 0
        if elapsed > 0 and self.done_bytes > 0:
            speed = self.done_bytes / elapsed

        return {
            "task_id": self.task_id,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "save_dir": self.save_dir,
            "status": self.status,
            "error": self.error,
            "elapsed": elapsed,
            "speed": speed,
            "speed_fmt": _fmt_bytes(int(speed)) + "/s" if speed > 0 else "",
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "done_files": self.done_files,
            "done_dirs": self.done_dirs,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "total_bytes": self.total_bytes,
            "done_bytes": self.done_bytes,
            "total_bytes_fmt": _fmt_bytes(self.total_bytes),
            "done_bytes_fmt": _fmt_bytes(self.done_bytes),
            "current_file": self.current_file,
            "current_file_bytes": self.current_file_bytes,
            "current_file_total": self.current_file_total,
            "progress": round(self.done_bytes / self.total_bytes * 100, 1) if self.total_bytes > 0 else 0,
            "log": self.log[-30:],  # 最近 30 条
        }

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-200:]
        logger.info(msg)


def _fmt_bytes(size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


class SyncManager:
    """管理所有 Sync 任务 (进程级单例)"""

    def __init__(self):
        self._tasks: Dict[str, SyncTask] = {}
        self._lock = threading.Lock()

    def create_task(self, client, file_id: str, save_dir: str, skip_existing: bool = True) -> SyncTask:
        """创建并启动一个 sync 任务"""
        task_id = uuid.uuid4().hex[:12]
        task = SyncTask(task_id=task_id, file_id=file_id, save_dir=save_dir)

        with self._lock:
            self._tasks[task_id] = task

        thread = threading.Thread(
            target=self._run_sync,
            args=(client, task, skip_existing),
            daemon=True,
            name=f"guangya-sync-{task_id}",
        )
        thread.start()
        return task

    def get_task(self, task_id: str) -> Optional[SyncTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[SyncTask]:
        return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == SyncTask.STATUS_RUNNING:
            task.cancel()
            return True
        return False

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status not in (SyncTask.STATUS_RUNNING, SyncTask.STATUS_PENDING):
                del self._tasks[task_id]
                return True
        return False

    # ── 核心 sync 逻辑 ──

    def _run_sync(self, client, task: SyncTask, skip_existing: bool):
        """在后台线程中执行 sync"""
        import requests as _requests

        task.status = SyncTask.STATUS_RUNNING
        task.started_at = time.time()
        task._log("开始同步...")

        try:
            # Phase 1: 扫描远程目录树，收集所有文件和目录
            task._log("扫描远程目录结构...")
            tree = self._scan_tree(client, task.file_id, task)
            if task.is_cancelled:
                task.status = SyncTask.STATUS_CANCELLED
                task._log("任务已取消")
                task.finished_at = time.time()
                return

            if tree is None:
                task.status = SyncTask.STATUS_FAILED
                task.error = "扫描远程目录失败"
                task._log(task.error)
                task.finished_at = time.time()
                return

            root_name = tree["name"]
            task.file_name = root_name

            # 收集扁平化的文件列表 和 目录列表
            all_files = []  # [(remote_file_info, local_rel_path)]
            all_dirs = []   # [local_rel_path]

            if tree["is_dir"]:
                self._flatten_tree(tree, "", all_files, all_dirs)
            else:
                # 单文件下载
                all_files.append((tree, root_name))

            task.total_files = len(all_files)
            task.total_dirs = len(all_dirs)
            task.total_bytes = sum(f[0].get("fileSize", 0) for f in all_files)
            task._log(f"扫描完成: {task.total_dirs} 个目录, {task.total_files} 个文件, 总计 {_fmt_bytes(task.total_bytes)}")

            # Phase 2: 创建目录
            base_dir = task.save_dir
            for rel_dir in all_dirs:
                if task.is_cancelled:
                    break
                local_dir = os.path.join(base_dir, rel_dir)
                os.makedirs(local_dir, exist_ok=True)
                task.done_dirs += 1

            if task.is_cancelled:
                task.status = SyncTask.STATUS_CANCELLED
                task._log("任务已取消")
                task.finished_at = time.time()
                return

            # Phase 3: 逐文件下载
            for file_info, rel_path in all_files:
                if task.is_cancelled:
                    break

                local_path = os.path.join(base_dir, rel_path)
                file_size = file_info.get("fileSize", 0)
                file_id = file_info["fileId"]
                file_name = file_info.get("fileName", "")

                # 跳过已存在且大小一致的文件
                if skip_existing and os.path.exists(local_path):
                    existing_size = os.path.getsize(local_path)
                    if existing_size == file_size:
                        task._log(f"跳过 (已存在): {rel_path}")
                        task.skipped_files += 1
                        task.done_files += 1
                        task.done_bytes += file_size
                        continue

                task.current_file = rel_path
                task.current_file_bytes = 0
                task.current_file_total = file_size
                task._log(f"下载: {rel_path} ({_fmt_bytes(file_size)})")

                # 获取签名 URL
                dl = client.download(file_id)
                if not dl or not dl.get("signedURL"):
                    task._log(f"❌ 获取下载链接失败: {rel_path}")
                    task.failed_files += 1
                    task.done_files += 1
                    continue

                signed_url = dl["signedURL"]

                # 确保父目录存在
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                # 流式下载
                try:
                    resp = _requests.get(signed_url, stream=True, timeout=600)
                    resp.raise_for_status()

                    with open(local_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if task.is_cancelled:
                                break
                            if chunk:
                                f.write(chunk)
                                chunk_len = len(chunk)
                                task.done_bytes += chunk_len
                                task.current_file_bytes += chunk_len

                    if task.is_cancelled:
                        # 清理不完整文件
                        if os.path.exists(local_path):
                            try:
                                os.remove(local_path)
                            except OSError:
                                pass
                        break

                    task.done_files += 1
                    task._log(f"✓ {rel_path}")

                except Exception as e:
                    task._log(f"❌ 下载失败: {rel_path} — {e}")
                    task.failed_files += 1
                    task.done_files += 1
                    if os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except OSError:
                            pass

            # 完成
            if task.is_cancelled:
                task.status = SyncTask.STATUS_CANCELLED
                task._log("任务已取消")
            elif task.failed_files > 0:
                task.status = SyncTask.STATUS_DONE
                task._log(f"同步完成 (有 {task.failed_files} 个文件失败)")
            else:
                task.status = SyncTask.STATUS_DONE
                task._log(f"同步完成: {task.done_files} 文件, {_fmt_bytes(task.done_bytes)}")

            task.current_file = ""
            task.finished_at = time.time()

        except Exception as e:
            task.status = SyncTask.STATUS_FAILED
            task.error = str(e)
            task._log(f"同步异常: {e}")
            task.finished_at = time.time()
            logger.exception("sync task failed")

    def _scan_tree(self, client, file_id: str, task: SyncTask, depth: int = 0) -> Optional[dict]:
        """递归扫描远程目录树

        Returns:
            {fileId, fileName, fileSize, is_dir, children: [...]}
        """
        if task.is_cancelled:
            return None

        # 先获取文件详情判断是文件还是目录
        detail = client.get_file_detail(file_id)
        if not detail:
            return None

        # get_file_detail 返回的结构可能不同，兼容处理
        file_info = detail.get("fileInfo", detail)
        name = file_info.get("fileName", "unknown")
        is_dir = file_info.get("resType") == 2

        node = {
            "fileId": file_id,
            "fileName": name,
            "fileSize": file_info.get("fileSize", 0),
            "is_dir": is_dir,
            "children": [],
        }

        if is_dir:
            task._log(f"{'  ' * depth}📂 {name}")
            # 列出子项
            resp = client.ls_dir(parent_id=file_id)
            if resp.get("msg") != "success":
                task._log(f"列目录失败: {name}")
                return node

            items = resp.get("data", {}).get("list", [])
            for item in items:
                if task.is_cancelled:
                    return None
                child_id = item.get("fileId", "")
                child_is_dir = item.get("resType") == 2
                if child_is_dir:
                    # 递归
                    child_node = self._scan_tree(client, child_id, task, depth + 1)
                    if child_node:
                        node["children"].append(child_node)
                else:
                    node["children"].append({
                        "fileId": child_id,
                        "fileName": item.get("fileName", ""),
                        "fileSize": item.get("fileSize", 0),
                        "is_dir": False,
                        "children": [],
                    })

        return node

    def _flatten_tree(self, node: dict, prefix: str, files: list, dirs: list):
        """将目录树扁平化为文件列表和目录列表"""
        name = node["fileName"]
        if node["is_dir"]:
            rel_dir = os.path.join(prefix, name) if prefix else name
            dirs.append(rel_dir)
            for child in node.get("children", []):
                self._flatten_tree(child, rel_dir, files, dirs)
        else:
            rel_path = os.path.join(prefix, name) if prefix else name
            files.append((node, rel_path))


# 进程级单例
_sync_manager: Optional[SyncManager] = None
_sync_lock = threading.Lock()


def get_sync_manager() -> SyncManager:
    global _sync_manager
    if _sync_manager is None:
        with _sync_lock:
            if _sync_manager is None:
                _sync_manager = SyncManager()
    return _sync_manager
