"""
WebDAV 挂载目录 → 本地 NAS 同步引擎

设计思路:
  用户已通过 Alist 将夸克网盘挂载为本地目录 (WebDAV mount)，
  本模块负责将挂载目录中的文件 **复制** 到 NAS 物理磁盘缓存目录，
  复制完成后可选 **删除源文件** 以释放网盘空间。

  本质: 本地目录 → 本地目录的文件拷贝，附带:
    - 实时进度回调 (字节级)
    - 断点续传 (比较文件大小)
    - 增量同步 (跳过已存在且大小一致的文件)
    - 每任务可配置是否删除源文件
    - 临时文件拷贝 (.quark_tmp 后缀, 完成后 rename)
    - 每任务独立调度间隔

配置 (config.json → sync 或 scheduler.tasks[].sync):
  {
    "webdav_mount": "/mnt/alist/夸克",       # WebDAV 挂载根目录
    "local_dest":   "/mnt/nas/media",         # NAS 物理缓存目录
    "delete_after_sync": false,               # 同步后是否删除源
    "buffer_size": 8388608,                   # 拷贝缓冲区 8MB
    "exclude_patterns": ["*.nfo", "*.txt"],   # 排除文件模式
  }
"""

import logging
import os
import shutil
import fnmatch
import time
import re as _re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("quark_cli.sync")

# 默认 8MB 缓冲区 — WebDAV 挂载通常 FUSE 有延迟，大缓冲区更高效
DEFAULT_BUFFER_SIZE = 8 * 1024 * 1024

# 临时文件后缀 — 拷贝过程中使用，完成后 rename 去掉
TEMP_SUFFIX = ".quark_tmp"

# ── 进度数据结构 ──


@dataclass
class FileProgress:
    """单个文件的同步进度"""
    src: str
    dst: str
    filename: str
    size: int = 0
    copied: int = 0
    speed: float = 0.0  # bytes/sec
    status: str = "pending"  # pending / copying / done / skipped / error
    error: str = ""

    @property
    def percent(self) -> float:
        if self.size <= 0:
            return 0.0
        return min(100.0, self.copied / self.size * 100)

    @property
    def eta(self) -> float:
        """预计剩余时间 (秒)"""
        if self.speed <= 0 or self.copied >= self.size:
            return 0.0
        return (self.size - self.copied) / self.speed


@dataclass
class SyncProgress:
    """整体同步进度"""
    task_name: str = ""
    source_dir: str = ""
    dest_dir: str = ""
    total_files: int = 0
    total_bytes: int = 0
    copied_files: int = 0
    copied_bytes: int = 0
    skipped_files: int = 0
    deleted_files: int = 0
    error_files: int = 0
    status: str = "idle"  # idle / scanning / syncing / deleting / done / error
    current_file: Optional[FileProgress] = None
    files: List[FileProgress] = field(default_factory=list)
    start_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, self.copied_bytes / self.total_bytes * 100)

    @property
    def elapsed(self) -> float:
        if self.start_time <= 0:
            return 0.0
        return time.time() - self.start_time

    @property
    def speed(self) -> float:
        """Overall bytes/sec"""
        e = self.elapsed
        if e <= 0:
            return 0.0
        return self.copied_bytes / e

    @property
    def eta(self) -> float:
        """预计剩余时间 (秒)"""
        s = self.speed
        if s <= 0 or self.copied_bytes >= self.total_bytes:
            return 0.0
        return (self.total_bytes - self.copied_bytes) / s

    def to_dict(self) -> dict:
        """序列化为可 JSON 输出的 dict"""
        d = {
            "task_name": self.task_name,
            "source_dir": self.source_dir,
            "dest_dir": self.dest_dir,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "copied_files": self.copied_files,
            "copied_bytes": self.copied_bytes,
            "skipped_files": self.skipped_files,
            "deleted_files": self.deleted_files,
            "error_files": self.error_files,
            "status": self.status,
            "percent": round(self.percent, 1),
            "elapsed": round(self.elapsed, 1),
            "speed": round(self.speed),
            "speed_human": _format_speed(self.speed),
            "eta": round(self.eta),
            "eta_human": _format_duration(self.eta),
            "errors": self.errors[-10:],  # 最后 10 条错误
        }
        # 已拷贝的文件列表 (含文件名和大小)
        copied_list = []
        for fp in self.files:
            if fp.status == "done":
                copied_list.append({
                    "filename": fp.filename,
                    "size": fp.size,
                    "size_human": _format_size(fp.size),
                })
        if copied_list:
            d["copied_file_list"] = copied_list

        if self.current_file:
            d["current_file"] = {
                "filename": self.current_file.filename,
                "size": self.current_file.size,
                "copied": self.current_file.copied,
                "percent": round(self.current_file.percent, 1),
                "speed": round(self.current_file.speed),
                "speed_human": _format_speed(self.current_file.speed),
                "eta": round(self.current_file.eta),
                "eta_human": _format_duration(self.current_file.eta),
                "status": self.current_file.status,
            }
        return d


def _format_speed(bps: float) -> str:
    """格式化速度为人类可读"""
    if bps <= 0:
        return "0 B/s"
    if bps < 1024:
        return "{:.0f} B/s".format(bps)
    if bps < 1024 * 1024:
        return "{:.1f} KB/s".format(bps / 1024)
    if bps < 1024 * 1024 * 1024:
        return "{:.1f} MB/s".format(bps / 1024 / 1024)
    return "{:.2f} GB/s".format(bps / 1024 / 1024 / 1024)


def _format_duration(seconds: float) -> str:
    """格式化剩余时间"""
    if seconds <= 0:
        return ""
    s = int(seconds)
    if s < 60:
        return "{}s".format(s)
    if s < 3600:
        return "{}m {:02d}s".format(s // 60, s % 60)
    h = s // 3600
    m = (s % 3600) // 60
    return "{}h {:02d}m".format(h, m)


def _format_size(n: int) -> str:
    """格式化文件大小"""
    if n < 1024:
        return "{} B".format(n)
    if n < 1024 * 1024:
        return "{:.1f} KB".format(n / 1024)
    if n < 1024 * 1024 * 1024:
        return "{:.1f} MB".format(n / 1024 / 1024)
    return "{:.2f} GB".format(n / 1024 / 1024 / 1024)


# ── 核心同步引擎 ──


class SyncEngine:
    """
    文件同步引擎

    将 source_dir 下的所有文件/目录结构复制到 dest_dir，
    支持实时进度回调、增量同步、可选源删除。
    """

    def __init__(
        self,
        source_dir: str,
        dest_dir: str,
        delete_after_sync: bool = False,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        exclude_patterns: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[SyncProgress], None]] = None,
        task_name: str = "",
    ):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.delete_after_sync = delete_after_sync
        self.buffer_size = buffer_size
        self.exclude_patterns = exclude_patterns or []
        self.progress_callback = progress_callback
        self.task_name = task_name

        self._progress = SyncProgress(
            task_name=task_name,
            source_dir=str(self.source_dir),
            dest_dir=str(self.dest_dir),
        )
        self._cancelled = False
        self._active_rsync_proc = None
        self._lock = threading.Lock()

    @property
    def progress(self) -> SyncProgress:
        return self._progress

    def cancel(self):
        """取消同步 — 终止正在运行的 rsync 进程"""
        self._cancelled = True
        # 终止 rsync 子进程
        proc = getattr(self, "_active_rsync_proc", None)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _notify(self):
        """通知进度回调"""
        if self.progress_callback:
            try:
                self.progress_callback(self._progress)
            except Exception:
                pass

    def _is_excluded(self, filename: str) -> bool:
        """检查文件是否匹配排除模式"""
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def _scan_files(self) -> List[tuple]:
        """
        扫描源目录，返回 [(src_path, dest_path, size), ...]
        保持目录结构。
        """
        self._progress.status = "scanning"
        self._notify()

        file_list = []

        if not self.source_dir.exists():
            raise FileNotFoundError("源目录不存在: {}".format(self.source_dir))

        if not self.source_dir.is_dir():
            raise NotADirectoryError("源路径不是目录: {}".format(self.source_dir))

        for root, dirs, files in os.walk(str(self.source_dir)):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            rel_root = os.path.relpath(root, str(self.source_dir))

            for fname in files:
                if self._cancelled:
                    return file_list

                # 跳过隐藏文件
                if fname.startswith("."):
                    continue

                # 跳过临时文件 (上次未完成的拷贝残留)
                if fname.endswith(TEMP_SUFFIX):
                    continue

                # 排除模式
                if self._is_excluded(fname):
                    continue

                src_path = os.path.join(root, fname)
                if rel_root == ".":
                    dst_path = os.path.join(str(self.dest_dir), fname)
                else:
                    dst_path = os.path.join(str(self.dest_dir), rel_root, fname)

                try:
                    size = os.path.getsize(src_path)
                except OSError:
                    size = 0

                file_list.append((src_path, dst_path, size))

        return file_list

    def _need_copy(self, src_path: str, dst_path: str, src_size: int) -> bool:
        """
        判断是否需要拷贝:
          - 目标不存在 → 需要
          - 目标存在但大小不一致 → 需要 (覆盖)
          - 目标存在且大小一致 → 跳过
        """
        if not os.path.exists(dst_path):
            # 清理可能残留的 .quark_tmp 临时文件
            tmp_path = dst_path + TEMP_SUFFIX
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    logger.debug("清理残留临时文件: %s", tmp_path)
                except OSError:
                    pass
            return True
        try:
            dst_size = os.path.getsize(dst_path)
            return dst_size != src_size
        except OSError:
            return True

    def _safe_rename(self, tmp_path: str, dst_path: str, max_retries: int = 3):
        """
        稳健的 rename 操作 — 处理 NAS/FUSE/NFS 文件系统的边界情况。

        某些网络文件系统 (NFS/CIFS/FUSE) 在写入完成后，目录项可能存在短暂的
        不一致窗口，导致 os.rename() 抛出 ENOENT。本方法通过以下策略解决:
          1. 确保目标目录存在 (处理并发删除或缓存失效)
          2. 最多重试 max_retries 次，每次间隔递增
          3. 若 os.rename() 始终失败，回退到 shutil.move()
        """
        last_err = None
        for attempt in range(max_retries):
            try:
                # 每次重试前确保目标目录存在
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                os.rename(tmp_path, dst_path)
                return
            except OSError as e:
                last_err = e
                if attempt < max_retries - 1:
                    delay = 0.5 * (attempt + 1)
                    logger.warning(
                        "rename 失败 (尝试 %d/%d): %s -> %s — %s, %.1f秒后重试",
                        attempt + 1, max_retries, tmp_path, dst_path, e, delay
                    )
                    time.sleep(delay)

        # os.rename 多次失败 — 回退到 shutil.move (支持跨设备)
        logger.warning(
            "rename 重试耗尽，回退到 shutil.move: %s -> %s (最后错误: %s)",
            tmp_path, dst_path, last_err
        )
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.move(tmp_path, dst_path)
        except Exception as e:
            raise OSError(
                f"无法移动临时文件到目标路径: {tmp_path} -> {dst_path}: {e}"
            ) from e

    def _copy_file(self, src_path: str, dst_path: str, size: int) -> FileProgress:
        """
        基于 rsync 的高性能文件拷贝

        调用系统 rsync 获得 zero-copy / sendfile 级别的拷贝性能。
        先写入 dst_path + ".quark_tmp" 临时文件，完成后 rename 为正式文件。
        通过 --info=progress2 解析实时进度。

        使用独立线程读取 rsync stdout，避免 pipe buffer 满导致 rsync 进程阻塞。
        """
        fp = FileProgress(
            src=src_path,
            dst=dst_path,
            filename=os.path.basename(src_path),
            size=size,
            status="copying",
        )

        with self._lock:
            self._progress.current_file = fp

        # 确保目标目录存在
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        # 临时文件路径
        tmp_path = dst_path + TEMP_SUFFIX

        copy_start = time.time()
        proc = None

        # 解析 rsync --info=progress2 的输出
        # 格式:  1,234,567  25%   12.34MB/s   0:00:05 (xfr#1, to-chk=0/1)
        progress_re = _re.compile(
            r"[\s]*([\d,]+)\s+(\d+)%\s+([\d.]+\S+/s)"
        )

        # 用独立线程读 stdout，防止 pipe buffer 满阻塞 rsync
        latest_copied = [0]  # 从 reader 线程更新

        def _stdout_reader(stream):
            """持续读取并丢弃 rsync stdout，仅提取最新已拷贝字节数"""
            buf = b""
            try:
                while True:
                    data = stream.read(4096)
                    if not data:
                        break
                    buf += data
                    # 按 \r 或 \n 切分
                    while b"\r" in buf or b"\n" in buf:
                        ri = buf.find(b"\r")
                        ni = buf.find(b"\n")
                        if ri < 0:
                            ri = len(buf)
                        if ni < 0:
                            ni = len(buf)
                        idx = min(ri, ni)
                        line = buf[:idx].decode("utf-8", errors="replace").strip()
                        buf = buf[idx + 1:]
                        if not line:
                            continue
                        m = progress_re.search(line)
                        if m:
                            latest_copied[0] = int(m.group(1).replace(",", ""))
            except (OSError, ValueError):
                pass  # 进程被 kill 时 stream 会关闭

        try:
            cmd = [
                "rsync", "-a", "--no-compress",
                "--info=progress2", "--no-inc-recursive",
                src_path, tmp_path,
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self._active_rsync_proc = proc

            # 启动 stdout reader 线程 — 持续排空 pipe，rsync 永远不会被阻塞
            reader_t = threading.Thread(
                target=_stdout_reader, args=(proc.stdout,),
                daemon=True,
                name="rsync-reader",
            )
            reader_t.start()

            # 主线程: 定期轮询 latest_copied 更新进度，等待 rsync 结束
            last_report = copy_start
            while proc.poll() is None:
                if self._cancelled:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    fp.status = "error"
                    fp.error = "cancelled"
                    break

                copied = latest_copied[0]
                if copied > fp.copied:
                    fp.copied = copied
                    now = time.time()
                    elapsed = now - copy_start
                    if elapsed > 0:
                        fp.speed = copied / elapsed

                    if now - last_report >= 0.5:
                        with self._lock:
                            prev = sum(
                                f.size for f in self._progress.files
                                if f.status in ("done", "skipped")
                            )
                            self._progress.copied_bytes = prev + fp.copied
                        self._notify()
                        last_report = now

                time.sleep(0.2)

            reader_t.join(timeout=5)
            self._active_rsync_proc = None

            if fp.status == "error" and fp.error == "cancelled":
                raise Exception("cancelled")

            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
                raise OSError("rsync failed (code {}): {}".format(proc.returncode, stderr[:500]))

            # rsync 写到了 tmp_path — rename 为正式文件 (原子操作)
            self._safe_rename(tmp_path, dst_path)

            fp.status = "done"
            fp.copied = size  # 确保 100%
            logger.info("已同步: %s (%s)", fp.filename, _format_size(size))

        except Exception as e:
            self._active_rsync_proc = None
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except OSError:
                    pass
            if fp.status != "error":
                fp.status = "error"
                fp.error = str(e) if str(e) != "cancelled" else "cancelled"
                if str(e) != "cancelled":
                    logger.error("同步失败: %s — %s", fp.filename, e)
            # 删除不完整的临时文件
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

        return fp

    def run(self) -> SyncProgress:
        """
        执行完整同步流程

        Returns:
            SyncProgress: 最终同步结果
        """
        self._progress.start_time = time.time()
        self._cancelled = False

        logger.info("开始同步: %s → %s", self.source_dir, self.dest_dir)

        # ── Step 1: 扫描 ──
        try:
            file_list = self._scan_files()
        except (FileNotFoundError, NotADirectoryError) as e:
            self._progress.status = "error"
            self._progress.errors.append(str(e))
            logger.error("扫描失败: %s", e)
            self._notify()
            return self._progress

        if not file_list:
            self._progress.status = "done"
            logger.info("源目录为空，无需同步")
            self._notify()
            return self._progress

        self._progress.total_files = len(file_list)
        self._progress.total_bytes = sum(s for _, _, s in file_list)

        logger.info("扫描完成: %d 个文件, 共 %s",
                     len(file_list), _format_size(self._progress.total_bytes))

        # ── Step 2: 逐文件同步 ──
        self._progress.status = "syncing"
        self._notify()

        # 确保目标根目录存在
        os.makedirs(str(self.dest_dir), exist_ok=True)

        for src_path, dst_path, size in file_list:
            if self._cancelled:
                break

            # 检查是否需要拷贝
            if not self._need_copy(src_path, dst_path, size):
                fp = FileProgress(
                    src=src_path, dst=dst_path,
                    filename=os.path.basename(src_path),
                    size=size, copied=size, status="skipped",
                )
                self._progress.skipped_files += 1
                self._progress.copied_bytes += size  # 计入总进度
                self._progress.files.append(fp)
                logger.debug("跳过已存在: %s", fp.filename)

                # 跳过的文件 = 目标端已有完整副本, 源文件可安全删除
                if self.delete_after_sync:
                    try:
                        os.remove(fp.src)
                        self._progress.deleted_files += 1
                        logger.info("已删除源(已同步): %s", fp.filename)
                        self._try_remove_empty_parents(fp.src)
                    except OSError as e:
                        logger.warning("删除源失败: %s — %s", fp.filename, e)
                        self._progress.errors.append(
                            "删除失败 {}: {}".format(fp.filename, e)
                        )

                self._notify()
                continue

            # 执行拷贝
            fp = self._copy_file(src_path, dst_path, size)
            self._progress.files.append(fp)

            if fp.status == "done":
                self._progress.copied_files += 1
                with self._lock:
                    self._progress.copied_bytes = (
                        sum(f.size for f in self._progress.files
                            if f.status in ("done", "skipped"))
                    )

                # 即时删除: 每个文件拷贝成功后立即删除源文件
                # 影视文件通常很大, 等全部拷完再删会长时间占用双倍空间
                if self.delete_after_sync:
                    try:
                        os.remove(fp.src)
                        self._progress.deleted_files += 1
                        logger.info("已删除源: %s", fp.filename)
                        # 向上逐级清理空目录 (不删源根目录)
                        self._try_remove_empty_parents(fp.src)
                    except OSError as e:
                        logger.warning("删除源失败: %s — %s", fp.filename, e)
                        self._progress.errors.append(
                            "删除失败 {}: {}".format(fp.filename, e)
                        )

            elif fp.status == "error":
                self._progress.error_files += 1
                self._progress.errors.append(
                    "{}: {}".format(fp.filename, fp.error)
                )

            self._progress.current_file = None
            self._notify()

        # ── Step 3: 清理空目录 ──
        if self.delete_after_sync and not self._cancelled:
            self._progress.status = "deleting"
            self._notify()

            # 源文件已在 Step 2 中逐个删除, 这里只清理残留空目录
            self._cleanup_empty_dirs()

        # ── 完成 ──
        self._progress.status = "done" if not self._cancelled else "cancelled"
        self._progress.current_file = None
        self._notify()

        logger.info(
            "同步完成: 拷贝 %d / 跳过 %d / 失败 %d / 删除 %d — 耗时 %.1fs, 平均 %s",
            self._progress.copied_files,
            self._progress.skipped_files,
            self._progress.error_files,
            self._progress.deleted_files,
            self._progress.elapsed,
            _format_speed(self._progress.speed),
        )

        return self._progress

    def _try_remove_empty_parents(self, filepath: str):
        """删除源文件后，向上逐级清理空父目录，直到源根目录为止。"""
        src_root = str(self.source_dir)
        parent = os.path.dirname(filepath)
        while parent and parent != src_root and parent.startswith(src_root):
            try:
                if not os.listdir(parent):
                    os.rmdir(parent)
                    logger.debug("删除空目录: %s", parent)
                    parent = os.path.dirname(parent)
                else:
                    break  # 目录非空，停止
            except OSError:
                break  # 权限或其他错误，停止

    def _cleanup_empty_dirs(self):
        """删除源目录中的空子目录 (不删根)"""
        try:
            for root, dirs, files in os.walk(str(self.source_dir), topdown=False):
                if root == str(self.source_dir):
                    continue
                if not os.listdir(root):
                    try:
                        os.rmdir(root)
                        logger.debug("删除空目录: %s", root)
                    except OSError:
                        pass
        except OSError:
            pass


# ── 全局同步状态管理 ──


class SyncManager:
    """
    管理多个同步任务的全局状态。

    Web API / CLI 通过此单例获取进度、触发同步。
    """

    def __init__(self):
        self._tasks: Dict[str, SyncEngine] = {}  # task_name → engine
        self._lock = threading.Lock()
        self._listeners: Dict[str, List[Callable]] = {}  # task_name → [callbacks]

    def start_sync(
        self,
        task_name: str,
        source_dir: str,
        dest_dir: str,
        delete_after_sync: bool = False,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        exclude_patterns: Optional[List[str]] = None,
    ) -> SyncProgress:
        """
        在后台线程启动同步任务

        Returns:
            SyncProgress: 初始进度对象 (后续通过 get_progress 查询)
        """
        with self._lock:
            if task_name in self._tasks and self._tasks[task_name].progress.status in ("scanning", "syncing", "deleting"):
                raise RuntimeError("任务 {} 正在执行中".format(task_name))

        def _on_progress(progress: SyncProgress):
            """分发进度到监听器"""
            with self._lock:
                listeners = list(self._listeners.get(task_name, []))
            for cb in listeners:
                try:
                    cb(progress)
                except Exception:
                    pass

        engine = SyncEngine(
            source_dir=source_dir,
            dest_dir=dest_dir,
            delete_after_sync=delete_after_sync,
            buffer_size=buffer_size,
            exclude_patterns=exclude_patterns,
            progress_callback=_on_progress,
            task_name=task_name,
        )

        with self._lock:
            self._tasks[task_name] = engine

        def _run():
            try:
                engine.run()
            except Exception as e:
                logger.exception("同步任务异常: %s", task_name)
                engine.progress.status = "error"
                engine.progress.errors.append(str(e))

        t = threading.Thread(target=_run, daemon=True, name="sync-{}".format(task_name))
        t.start()

        return engine.progress

    def cancel_sync(self, task_name: str) -> bool:
        """取消同步任务"""
        with self._lock:
            engine = self._tasks.get(task_name)
        if engine:
            engine.cancel()
            return True
        return False

    def get_progress(self, task_name: str) -> Optional[SyncProgress]:
        """获取任务进度"""
        with self._lock:
            engine = self._tasks.get(task_name)
        if engine:
            return engine.progress
        return None

    def get_all_progress(self) -> Dict[str, dict]:
        """获取所有任务进度"""
        with self._lock:
            tasks = dict(self._tasks)
        return {name: engine.progress.to_dict() for name, engine in tasks.items()}

    def add_listener(self, task_name: str, callback: Callable):
        """添加进度监听器 (用于 SSE)"""
        with self._lock:
            if task_name not in self._listeners:
                self._listeners[task_name] = []
            self._listeners[task_name].append(callback)

    def remove_listener(self, task_name: str, callback: Callable):
        """移除进度监听器"""
        with self._lock:
            listeners = self._listeners.get(task_name, [])
            if callback in listeners:
                listeners.remove(callback)


# ── 全局单例 ──

_sync_manager: Optional[SyncManager] = None


def get_sync_manager() -> SyncManager:
    """获取全局 SyncManager 单例"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager


# ── 便捷函数 ──


def sync_files(
    source_dir: str,
    dest_dir: str,
    delete_after_sync: bool = False,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
    exclude_patterns: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[SyncProgress], None]] = None,
    task_name: str = "default",
) -> SyncProgress:
    """
    同步文件 (阻塞执行)

    Args:
        source_dir: 源目录 (WebDAV 挂载路径)
        dest_dir: 目标目录 (NAS 物理路径)
        delete_after_sync: 同步后删除源文件
        buffer_size: 拷贝缓冲区大小
        exclude_patterns: 排除的文件模式列表
        progress_callback: 进度回调函数
        task_name: 任务名称

    Returns:
        SyncProgress: 同步结果
    """
    engine = SyncEngine(
        source_dir=source_dir,
        dest_dir=dest_dir,
        delete_after_sync=delete_after_sync,
        buffer_size=buffer_size,
        exclude_patterns=exclude_patterns,
        progress_callback=progress_callback,
        task_name=task_name,
    )
    return engine.run()


def sync_from_config(config_data: dict, task_config: Optional[dict] = None,
                     progress_callback: Optional[Callable] = None) -> SyncProgress:
    """
    从配置自动读取参数执行同步

    优先使用 task_config 中的 sync 配置，fallback 到全局 sync 配置。

    Args:
        config_data: 完整配置 dict
        task_config: 单个任务配置 (scheduler.tasks[] 中的一项)
        progress_callback: 进度回调

    Returns:
        SyncProgress
    """
    # 全局 sync 配置
    global_sync = config_data.get("sync", {})

    # 任务级 sync 配置 (覆盖全局)
    task_sync = {}
    if task_config:
        task_sync = task_config.get("sync", {})

    # 合并: 任务级 > 全局
    webdav_mount = task_sync.get("webdav_mount") or global_sync.get("webdav_mount", "")
    local_dest = task_sync.get("local_dest") or global_sync.get("local_dest", "")
    delete_after = task_sync.get("delete_after_sync", global_sync.get("delete_after_sync", False))
    buffer_size = task_sync.get("buffer_size", global_sync.get("buffer_size", DEFAULT_BUFFER_SIZE))
    exclude = task_sync.get("exclude_patterns", global_sync.get("exclude_patterns", []))

    if not webdav_mount:
        raise ValueError("未配置 sync.webdav_mount (WebDAV 挂载路径)")
    if not local_dest:
        raise ValueError("未配置 sync.local_dest (本地目标路径)")

    # 如果任务有 save_base_path, 拼接子目录
    task_name = "sync"
    if task_config:
        task_name = task_config.get("name", "sync")
        # source: webdav_mount + save_base_path 中的相对部分
        save_base = task_config.get("save_base_path", "")
        if save_base:
            # save_base_path 如 "/媒体/电影" → 取相对路径拼到 webdav_mount
            rel = save_base.lstrip("/")
            source = os.path.join(webdav_mount, rel)
            dest = os.path.join(local_dest, rel)
        else:
            source = webdav_mount
            dest = local_dest
    else:
        source = webdav_mount
        dest = local_dest

    return sync_files(
        source_dir=source,
        dest_dir=dest,
        delete_after_sync=delete_after,
        buffer_size=buffer_size,
        exclude_patterns=exclude,
        progress_callback=progress_callback,
        task_name=task_name,
    )


# ── 同步定时调度器 ──


class SyncScheduler:
    """
    独立的同步定时调度器 — 支持每任务独立调度间隔

    配置 (config.json → sync):
      {
        "schedule_enabled": true,
        "schedule_interval_minutes": 60,     // 全局默认间隔 (向后兼容)
        "bot_notify": true,
        "tasks": [
          {
            "name": "media",
            "source": "/mnt/alist/media",
            "dest": "/mnt/nas/media",
            "enabled": true,
            "interval_minutes": 30,          // 任务级独立间隔 (可选)
            ...
          }
        ]
      }
    """

    def __init__(self, config_path=None):
        self.config_path = config_path
        self._running = False
        self._thread = None
        self._interval = 3600  # 全局默认间隔 (秒)
        self._enabled = False
        self._bot_notify = False
        self._last_run = None
        # 每任务独立的上次执行时间
        self._task_last_run: Dict[str, float] = {}  # task_name → timestamp

    def reload(self, sync_config: dict):
        """重新加载配置"""
        self._enabled = sync_config.get("schedule_enabled", False)
        minutes = sync_config.get("schedule_interval_minutes", 60)
        self._interval = max(int(minutes) * 60, 300)  # 最小 5 分钟
        self._bot_notify = sync_config.get("bot_notify", False)
        logger.info("同步调度器配置更新: enabled=%s, interval=%dm, notify=%s",
                     self._enabled, self._interval // 60, self._bot_notify)

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="sync-scheduler")
        self._thread.start()
        logger.info("同步定时调度器已启动")

    def stop(self):
        self._running = False

    def _load_config(self):
        """从配置文件读取"""
        try:
            from quark_cli.config import ConfigManager
            cfg = ConfigManager(self.config_path)
            cfg.load()
            sync_cfg = cfg.data.get("sync", {})
            self.reload(sync_cfg)
            return cfg
        except Exception:
            return None

    def _get_task_interval(self, task_def: dict) -> int:
        """获取任务的调度间隔 (秒), 优先使用任务级配置, 否则用全局默认"""
        task_minutes = task_def.get("interval_minutes", 0)
        if task_minutes and int(task_minutes) > 0:
            return max(int(task_minutes) * 60, 300)  # 最小 5 分钟
        return self._interval

    def _loop(self):
        """调度主循环 — 每任务独立间隔"""
        import time as _time

        _time.sleep(60)  # 启动后等 60 秒

        while self._running:
            try:
                cfg = self._load_config()

                if self._enabled and cfg:
                    now = _time.time()
                    sync_cfg = cfg.data.get("sync", {})
                    tasks_list = sync_cfg.get("tasks", [])

                    # 兼容旧配置: 无 tasks 时走旧的单任务逻辑
                    if not tasks_list:
                        webdav = sync_cfg.get("webdav_mount", "")
                        local = sync_cfg.get("local_dest", "")
                        if webdav and local:
                            tasks_list = [{
                                "name": "default",
                                "source": webdav,
                                "dest": local,
                                "delete_after_sync": sync_cfg.get("delete_after_sync", False),
                                "enabled": True,
                            }]

                    # 逐个任务检查是否到时间
                    due_tasks = []
                    for task_def in tasks_list:
                        if not task_def.get("enabled", True):
                            continue
                        src = task_def.get("source", "")
                        dst = task_def.get("dest", "")
                        if not src or not dst:
                            continue

                        tname = task_def.get("name", "sync")
                        interval = self._get_task_interval(task_def)
                        last = self._task_last_run.get(tname, 0)

                        if now - last >= interval:
                            due_tasks.append(task_def)

                    if due_tasks:
                        self._execute_sync_tasks(cfg, due_tasks)

            except Exception:
                logger.exception("同步调度循环异常")

            _time.sleep(60)

    def _execute_sync_tasks(self, cfg, tasks_to_run):
        """执行到期的同步任务"""
        import time as _time
        sync_cfg = cfg.data.get("sync", {})

        logger.info("定时同步: 启动 %d 个任务", len(tasks_to_run))

        results = []
        threads = []

        def _run_one(task_def):
            name = task_def.get("name", "sync")
            src = task_def.get("source", "")
            dst = task_def.get("dest", "")
            if not src or not dst:
                return
            try:
                # 记录本次执行时间
                self._task_last_run[name] = _time.time()

                result = sync_files(
                    source_dir=src,
                    dest_dir=dst,
                    delete_after_sync=task_def.get("delete_after_sync", False),
                    exclude_patterns=task_def.get("exclude_patterns",
                                                  sync_cfg.get("exclude_patterns", [])),
                    task_name=name,
                )
                results.append((name, result))
                logger.info("定时同步 [%s] 完成: 拷贝 %d / 跳过 %d / 失败 %d",
                             name, result.copied_files, result.skipped_files,
                             result.error_files)
                # 写入历史
                try:
                    from quark_cli.history import record as history_record
                    h_status = "success" if result.error_files == 0 else "partial"
                    copied_names = [fp.filename for fp in result.files if fp.status == "done"]
                    file_hint = ""
                    if copied_names:
                        shown = copied_names[:5]
                        file_hint = " | " + ", ".join(shown)
                        if len(copied_names) > 5:
                            file_hint += " 等{}个".format(len(copied_names))
                    history_record(
                        record_type="sync",
                        name=name,
                        status=h_status,
                        summary="拷贝 {} / 跳过 {} / 失败 {} ({}){}".format(
                            result.copied_files, result.skipped_files,
                            result.error_files, _format_speed(result.speed),
                            file_hint),
                        detail=result.to_dict(),
                        duration=result.elapsed,
                        config_path=self.config_path,
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.exception("定时同步 [%s] 失败: %s", name, e)
                try:
                    from quark_cli.history import record as history_record
                    history_record(
                        record_type="sync", name=name, status="error",
                        summary="异常: {}".format(str(e)[:200]),
                        config_path=self.config_path,
                    )
                except Exception:
                    pass

        for task_def in tasks_to_run:
            t = threading.Thread(target=_run_one, args=(task_def,),
                                 daemon=True,
                                 name="sched-sync-{}".format(task_def.get("name", "")))
            threads.append(t)
            t.start()

        # 等待所有完成
        for t in threads:
            t.join(timeout=86400)

        # Bot 通知汇总
        if self._bot_notify and results:
            self._send_notify_multi(cfg, results)

    def _execute_sync(self, cfg):
        """执行一次同步 — 所有 enabled 任务 (兼容旧调用)"""
        sync_cfg = cfg.data.get("sync", {})
        tasks_list = sync_cfg.get("tasks", [])

        # 兼容旧配置
        if not tasks_list:
            webdav = sync_cfg.get("webdav_mount", "")
            local = sync_cfg.get("local_dest", "")
            if webdav and local:
                tasks_list = [{
                    "name": "default",
                    "source": webdav,
                    "dest": local,
                    "delete_after_sync": sync_cfg.get("delete_after_sync", False),
                    "enabled": True,
                }]

        enabled_tasks = [t for t in tasks_list if t.get("enabled", True)]
        if not enabled_tasks:
            logger.info("定时同步: 无可用任务")
            return

        self._execute_sync_tasks(cfg, enabled_tasks)

    def _send_notify(self, cfg, progress):
        """发送飞书 Bot 通知"""
        try:
            from quark_cli.scheduler import send_bot_notify

            result = {
                "task_name": "定时文件同步",
                "saved": [],
                "failed": [],
            }

            if progress.status == "done" and progress.copied_files > 0:
                filenames = [fp.filename for fp in progress.files if fp.status == "done"]
                result["saved"] = [{
                    "title": "文件同步",
                    "year": "",
                    "save_path": str(progress.dest_dir),
                    "saved_count": progress.copied_files,
                    "filenames": filenames,
                }]
            elif progress.error_files > 0 or progress.status == "error":
                result["failed"] = [{"title": "文件同步", "year": "",
                                     "error": "; ".join(progress.errors[:3]) if progress.errors else "未知错误"}]
            else:
                return

            config_path = str(cfg.config_path) if hasattr(cfg, 'config_path') else self.config_path
            send_bot_notify(config_path, result)

        except Exception:
            logger.exception("同步通知发送失败")

    def _send_notify_multi(self, cfg, results):
        """多任务汇总通知"""
        try:
            from quark_cli.scheduler import send_bot_notify

            saved_items = []
            failed_items = []
            for name, progress in results:
                if progress.status == "done" and progress.copied_files > 0:
                    filenames = [fp.filename for fp in progress.files if fp.status == "done"]
                    saved_items.append({
                        "title": name,
                        "year": "",
                        "save_path": str(progress.dest_dir),
                        "saved_count": progress.copied_files,
                        "filenames": filenames,
                    })
                elif progress.error_files > 0 or progress.status == "error":
                    failed_items.append({
                        "title": name,
                        "year": "",
                        "error": "; ".join(progress.errors[:3]) if progress.errors else "未知错误",
                    })

            if not saved_items and not failed_items:
                return

            result = {
                "task_name": "定时文件同步 ({} 任务)".format(len(results)),
                "saved": saved_items,
                "failed": failed_items,
            }

            config_path = str(cfg.config_path) if hasattr(cfg, 'config_path') else self.config_path
            send_bot_notify(config_path, result)

        except Exception:
            logger.exception("同步汇总通知发送失败")

    def get_status(self):
        return {
            "running": self._running,
            "enabled": self._enabled,
            "interval_minutes": self._interval // 60,
            "bot_notify": self._bot_notify,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "task_last_run": {
                name: time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))
                for name, ts in self._task_last_run.items()
            },
        }


# ── 同步调度器单例 ──

_sync_scheduler: Optional[SyncScheduler] = None


def get_sync_scheduler(config_path=None) -> SyncScheduler:
    """获取同步调度器单例"""
    global _sync_scheduler
    if _sync_scheduler is None:
        _sync_scheduler = SyncScheduler(config_path)
    return _sync_scheduler


def try_start_sync_scheduler(config_path=None):
    """尝试启动同步定时调度器"""
    from quark_cli.config import ConfigManager
    cfg = ConfigManager(config_path)
    cfg.load()
    sync_cfg = cfg.data.get("sync", {})

    if not sync_cfg.get("schedule_enabled", False):
        logger.info("同步定时任务: 未启用，跳过")
        return None

    # 检查是否有可用任务 (新格式 tasks[] 或旧格式 webdav_mount)
    tasks_list = sync_cfg.get("tasks", [])
    has_tasks = any(t.get("source") and t.get("dest") for t in tasks_list)
    has_legacy = sync_cfg.get("webdav_mount") and sync_cfg.get("local_dest")

    if not has_tasks and not has_legacy:
        logger.info("同步定时任务: 未配置路径，跳过")
        return None

    sched = get_sync_scheduler(config_path)
    sched.reload(sync_cfg)
    sched.start()
    return sched
