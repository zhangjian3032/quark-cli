"""
tests/test_sync.py — 同步引擎单元测试
"""

import os
import sys
import time
import tempfile
import shutil
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quark_cli.media.sync import (
    SyncEngine, SyncProgress, SyncManager,
    sync_files, sync_from_config,
    _format_speed, _format_size,
)


# ── 工具函数测试 ──


class TestFormatHelpers(unittest.TestCase):
    def test_format_speed(self):
        self.assertEqual(_format_speed(0), "0 B/s")
        self.assertEqual(_format_speed(512), "512 B/s")
        self.assertEqual(_format_speed(1024), "1.0 KB/s")
        self.assertEqual(_format_speed(1024 * 1024), "1.0 MB/s")
        self.assertEqual(_format_speed(1024 * 1024 * 1024), "1.00 GB/s")
        self.assertIn("MB/s", _format_speed(50 * 1024 * 1024))

    def test_format_size(self):
        self.assertEqual(_format_size(0), "0 B")
        self.assertEqual(_format_size(1023), "1023 B")
        self.assertEqual(_format_size(1024), "1.0 KB")
        self.assertEqual(_format_size(1024 * 1024 * 5), "5.0 MB")
        self.assertIn("GB", _format_size(1024 * 1024 * 1024 * 2))


# ── 同步引擎核心测试 ──


class TestSyncEngine(unittest.TestCase):
    """使用临时目录测试文件同步"""

    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix="sync_src_")
        self.dst_dir = tempfile.mkdtemp(prefix="sync_dst_")

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def _create_file(self, rel_path, size=128):
        full_path = os.path.join(self.src_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"\x00" * size)
        return full_path

    def test_basic_copy(self):
        """基本文件拷贝"""
        self._create_file("movie.mkv", 1024)
        self._create_file("subs.srt", 64)

        result = sync_files(self.src_dir, self.dst_dir, task_name="t")

        self.assertEqual(result.status, "done")
        self.assertEqual(result.copied_files, 2)
        self.assertEqual(result.total_files, 2)
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "movie.mkv")))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "subs.srt")))

    def test_directory_structure(self):
        """保持目录结构"""
        self._create_file("电影/流浪地球2/movie.mkv", 512)
        self._create_file("电影/流浪地球2/subs.srt", 32)
        self._create_file("剧集/三体/S01E01.mkv", 256)

        result = sync_files(self.src_dir, self.dst_dir, task_name="t")

        self.assertEqual(result.status, "done")
        self.assertEqual(result.copied_files, 3)
        self.assertTrue(os.path.exists(
            os.path.join(self.dst_dir, "电影/流浪地球2/movie.mkv")))
        self.assertTrue(os.path.exists(
            os.path.join(self.dst_dir, "剧集/三体/S01E01.mkv")))

    def test_incremental_skip(self):
        """增量同步 — 跳过已存在且大小一致的文件"""
        self._create_file("a.mkv", 1024)
        self._create_file("b.mkv", 512)

        r1 = sync_files(self.src_dir, self.dst_dir, task_name="t")
        self.assertEqual(r1.copied_files, 2)
        self.assertEqual(r1.skipped_files, 0)

        r2 = sync_files(self.src_dir, self.dst_dir, task_name="t")
        self.assertEqual(r2.copied_files, 0)
        self.assertEqual(r2.skipped_files, 2)

    def test_overwrite_different_size(self):
        """大小不一致时覆盖"""
        self._create_file("file.mkv", 1024)
        sync_files(self.src_dir, self.dst_dir, task_name="t")

        self._create_file("file.mkv", 2048)
        r2 = sync_files(self.src_dir, self.dst_dir, task_name="t")
        self.assertEqual(r2.copied_files, 1)
        self.assertEqual(
            os.path.getsize(os.path.join(self.dst_dir, "file.mkv")), 2048)

    def test_delete_after_sync(self):
        """同步后删除源文件"""
        self._create_file("movie.mkv", 256)
        self._create_file("sub.srt", 16)

        result = sync_files(
            self.src_dir, self.dst_dir,
            delete_after_sync=True, task_name="t",
        )

        self.assertEqual(result.status, "done")
        self.assertEqual(result.deleted_files, 2)
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "movie.mkv")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "sub.srt")))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "movie.mkv")))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "sub.srt")))

    def test_delete_preserves_skipped(self):
        """删除模式下，跳过的文件不删除源"""
        self._create_file("a.mkv", 256)
        sync_files(self.src_dir, self.dst_dir, task_name="t")

        r2 = sync_files(
            self.src_dir, self.dst_dir,
            delete_after_sync=True, task_name="t",
        )
        self.assertEqual(r2.skipped_files, 1)
        self.assertEqual(r2.deleted_files, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "a.mkv")))

    def test_exclude_patterns(self):
        """排除文件模式"""
        self._create_file("movie.mkv", 512)
        self._create_file("info.nfo", 32)
        self._create_file("readme.txt", 16)

        result = sync_files(
            self.src_dir, self.dst_dir,
            exclude_patterns=["*.nfo", "*.txt"], task_name="t",
        )

        self.assertEqual(result.copied_files, 1)
        self.assertEqual(result.total_files, 1)
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "movie.mkv")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "info.nfo")))

    def test_skip_hidden_files(self):
        """跳过隐藏文件/目录"""
        self._create_file("movie.mkv", 256)
        self._create_file(".DS_Store", 8)
        self._create_file(".cache/temp.bin", 16)

        result = sync_files(self.src_dir, self.dst_dir, task_name="t")

        self.assertEqual(result.copied_files, 1)
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, ".DS_Store")))

    def test_empty_source(self):
        """空源目录"""
        result = sync_files(self.src_dir, self.dst_dir, task_name="t")
        self.assertEqual(result.status, "done")
        self.assertEqual(result.total_files, 0)

    def test_nonexistent_source(self):
        """源目录不存在"""
        result = sync_files("/tmp/nonexistent_xyz_abc_999", self.dst_dir, task_name="t")
        self.assertEqual(result.status, "error")
        self.assertTrue(len(result.errors) > 0)

    def test_progress_callback(self):
        """进度回调被调用"""
        self._create_file("big.bin", 1024 * 100)

        statuses = []
        def on_progress(progress):
            statuses.append(progress.status)

        sync_files(
            self.src_dir, self.dst_dir,
            progress_callback=on_progress, task_name="t",
        )

        self.assertIn("scanning", statuses)
        self.assertIn("done", statuses)

    def test_cancel(self):
        """取消同步"""
        for i in range(20):
            self._create_file("file_{:03d}.bin".format(i), 1024)

        engine = SyncEngine(
            source_dir=self.src_dir,
            dest_dir=self.dst_dir,
            task_name="test_cancel",
        )

        t = threading.Thread(target=engine.run)
        t.start()
        time.sleep(0.1)
        engine.cancel()
        t.join(timeout=5)

        self.assertIn(engine.progress.status, ("done", "cancelled"))

    def test_to_dict_serialization(self):
        """SyncProgress.to_dict() 序列化"""
        self._create_file("test.mkv", 256)

        result = sync_files(self.src_dir, self.dst_dir, task_name="test_dict")
        d = result.to_dict()

        self.assertEqual(d["task_name"], "test_dict")
        self.assertEqual(d["status"], "done")
        self.assertEqual(d["total_files"], 1)
        self.assertEqual(d["copied_files"], 1)
        self.assertIn("percent", d)
        self.assertIn("speed_human", d)
        self.assertIn("elapsed", d)


# ── SyncManager 测试 ──


class TestSyncManager(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix="mgr_src_")
        self.dst_dir = tempfile.mkdtemp(prefix="mgr_dst_")

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_start_and_progress(self):
        """通过 SyncManager 启动和查询进度"""
        with open(os.path.join(self.src_dir, "test.bin"), "wb") as f:
            f.write(b"\x00" * 1024)

        mgr = SyncManager()
        mgr.start_sync("mgr_test", self.src_dir, self.dst_dir)

        for _ in range(50):
            progress = mgr.get_progress("mgr_test")
            if progress and progress.status == "done":
                break
            time.sleep(0.1)

        self.assertIsNotNone(progress)
        self.assertEqual(progress.status, "done")

    def test_get_all_progress(self):
        """获取所有任务"""
        with open(os.path.join(self.src_dir, "t.bin"), "wb") as f:
            f.write(b"\x00" * 256)

        mgr = SyncManager()
        mgr.start_sync("all_test", self.src_dir, self.dst_dir)
        time.sleep(0.5)

        all_p = mgr.get_all_progress()
        self.assertIn("all_test", all_p)


# ── sync_from_config 测试 ──


class TestSyncFromConfig(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix="cfg_src_")
        self.dst_dir = tempfile.mkdtemp(prefix="cfg_dst_")

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_global_config(self):
        """使用全局 sync 配置"""
        with open(os.path.join(self.src_dir, "a.mkv"), "wb") as f:
            f.write(b"\x00" * 128)

        config = {
            "sync": {
                "webdav_mount": self.src_dir,
                "local_dest": self.dst_dir,
                "delete_after_sync": False,
            }
        }
        result = sync_from_config(config)
        self.assertEqual(result.status, "done")
        self.assertEqual(result.copied_files, 1)

    def test_task_config_override(self):
        """任务级配置覆盖全局"""
        sub_src = os.path.join(self.src_dir, "媒体")
        os.makedirs(sub_src)
        with open(os.path.join(sub_src, "b.mkv"), "wb") as f:
            f.write(b"\x00" * 64)

        config = {
            "sync": {
                "webdav_mount": "/wrong/path",
                "local_dest": "/wrong/dest",
            }
        }
        task_config = {
            "name": "覆盖测试",
            "save_base_path": "",
            "sync": {
                "webdav_mount": sub_src,
                "local_dest": self.dst_dir,
                "delete_after_sync": False,
            }
        }
        result = sync_from_config(config, task_config=task_config)
        self.assertEqual(result.status, "done")
        self.assertEqual(result.copied_files, 1)

    def test_missing_config_raises(self):
        """缺失配置抛出 ValueError"""
        with self.assertRaises(ValueError):
            sync_from_config({})
        with self.assertRaises(ValueError):
            sync_from_config({"sync": {"webdav_mount": "/tmp"}})


if __name__ == "__main__":
    unittest.main()
