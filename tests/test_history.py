"""history 模块单元测试"""

import os
import tempfile
import unittest
import json

# 让 history 使用临时目录
import quark_cli.history as history


class TestHistory(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, "config.json")
        with open(self.cfg_path, "w") as f:
            f.write("{}")
        # 重置全局连接
        history._db_conn = None

    def tearDown(self):
        if history._db_conn:
            history._db_conn.close()
            history._db_conn = None
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_and_query(self):
        """写入记录后能查询到"""
        history.record(
            record_type="task", name="测试任务",
            status="success", summary="转存 3 / 失败 0",
            detail={"saved": [1, 2, 3]}, duration=12.5,
            config_path=self.cfg_path,
        )
        results = history.query(config_path=self.cfg_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "测试任务")
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["detail"]["saved"], [1, 2, 3])
        self.assertAlmostEqual(results[0]["duration"], 12.5, places=1)

    def test_filter_by_type(self):
        """按类型筛选"""
        history.record(record_type="task", name="T1", config_path=self.cfg_path)
        history.record(record_type="sync", name="S1", config_path=self.cfg_path)
        history.record(record_type="task", name="T2", config_path=self.cfg_path)

        tasks = history.query(record_type="task", config_path=self.cfg_path)
        self.assertEqual(len(tasks), 2)

        syncs = history.query(record_type="sync", config_path=self.cfg_path)
        self.assertEqual(len(syncs), 1)

    def test_filter_by_status(self):
        """按状态筛选"""
        history.record(record_type="task", name="OK", status="success", config_path=self.cfg_path)
        history.record(record_type="task", name="BAD", status="error", config_path=self.cfg_path)

        ok = history.query(status="success", config_path=self.cfg_path)
        self.assertEqual(len(ok), 1)
        self.assertEqual(ok[0]["name"], "OK")

    def test_stats(self):
        """统计功能"""
        history.record(record_type="task", name="T1", status="success", config_path=self.cfg_path)
        history.record(record_type="sync", name="S1", status="error", config_path=self.cfg_path)
        history.record(record_type="task", name="T2", status="success", config_path=self.cfg_path)

        s = history.stats(days=7, config_path=self.cfg_path)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_type"]["task"], 2)
        self.assertEqual(s["by_type"]["sync"], 1)
        self.assertEqual(s["by_status"]["success"], 2)
        self.assertEqual(s["by_status"]["error"], 1)
        self.assertEqual(len(s["recent"]), 3)

    def test_limit_offset(self):
        """分页"""
        for i in range(10):
            history.record(record_type="task", name="T{}".format(i), config_path=self.cfg_path)

        page1 = history.query(limit=3, offset=0, config_path=self.cfg_path)
        self.assertEqual(len(page1), 3)

        page2 = history.query(limit=3, offset=3, config_path=self.cfg_path)
        self.assertEqual(len(page2), 3)

        # 不重叠
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        self.assertEqual(len(ids1 & ids2), 0)

    def test_cleanup(self):
        """清理旧记录"""
        history.record(record_type="task", name="Old", config_path=self.cfg_path)

        # 手动把 ts 改成 200 天前
        conn = history._get_conn(self.cfg_path)
        conn.execute("UPDATE history SET ts = datetime('now', '-200 days')")
        conn.commit()

        deleted = history.cleanup(keep_days=90, config_path=self.cfg_path)
        self.assertEqual(deleted, 1)

        remaining = history.query(config_path=self.cfg_path)
        self.assertEqual(len(remaining), 0)

    def test_order_desc(self):
        """返回按 id 倒序 (即插入倒序)"""
        history.record(record_type="task", name="First", config_path=self.cfg_path)
        history.record(record_type="task", name="Second", config_path=self.cfg_path)

        results = history.query(config_path=self.cfg_path)
        # id 自增, 后插入的 id 更大 → ORDER BY ts DESC, id DESC
        self.assertEqual(results[0]["name"], "Second")
        self.assertEqual(results[1]["name"], "First")


if __name__ == "__main__":
    unittest.main()
