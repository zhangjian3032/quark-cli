"""
任务执行历史记录 — SQLite 持久化

记录所有任务/同步/签到的执行结果，供 Dashboard 展示和问题追溯。

表结构:
    history(
        id          INTEGER PRIMARY KEY,
        ts          TEXT    -- ISO8601 时间戳
        type        TEXT    -- task / sync / sign / auto_save
        name        TEXT    -- 任务名称
        status      TEXT    -- success / partial / error
        summary     TEXT    -- 一行摘要 (如 "拷贝 42 文件, 跳过 3")
        detail      TEXT    -- JSON 详情
        duration    REAL    -- 耗时(秒)
    )
"""

import json
import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_DB_FILENAME = "quark_history.db"
_db_lock = threading.Lock()
_db_conn: Optional[sqlite3.Connection] = None


def _get_db_path(config_path: Optional[str] = None) -> str:
    """数据库与 config.json 同目录"""
    if config_path:
        return os.path.join(os.path.dirname(os.path.abspath(config_path)), _DB_FILENAME)
    # 默认 ~/.config/quark-cli/
    default_dir = os.path.join(os.path.expanduser("~"), ".config", "quark-cli")
    os.makedirs(default_dir, exist_ok=True)
    return os.path.join(default_dir, _DB_FILENAME)


def _get_conn(config_path: Optional[str] = None) -> sqlite3.Connection:
    """获取 / 创建 SQLite 连接 (线程安全单例)"""
    global _db_conn
    with _db_lock:
        if _db_conn is None:
            db_path = _get_db_path(config_path)
            _db_conn = sqlite3.connect(db_path, check_same_thread=False)
            _db_conn.row_factory = sqlite3.Row
            _db_conn.execute("PRAGMA journal_mode=WAL")
            _init_schema(_db_conn)
            logger.info("历史记录数据库: %s", db_path)
        return _db_conn


def _init_schema(conn: sqlite3.Connection):
    """初始化表结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS history (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            type     TEXT    NOT NULL DEFAULT 'task',
            name     TEXT    NOT NULL DEFAULT '',
            status   TEXT    NOT NULL DEFAULT 'success',
            summary  TEXT    NOT NULL DEFAULT '',
            detail   TEXT    NOT NULL DEFAULT '{}',
            duration REAL    NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_history_ts   ON history(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_history_type ON history(type);
    """)
    conn.commit()


# ── 写入 ──

def record(
    record_type: str,
    name: str,
    status: str = "success",
    summary: str = "",
    detail: Optional[Dict[str, Any]] = None,
    duration: float = 0,
    config_path: Optional[str] = None,
):
    """
    写入一条执行历史

    Args:
        record_type: task / sync / sign / auto_save
        name: 任务/操作名称
        status: success / partial / error
        summary: 一行摘要
        detail: 详情 dict (JSON 序列化)
        duration: 耗时(秒)
        config_path: 配置文件路径
    """
    try:
        conn = _get_conn(config_path)
        with _db_lock:
            conn.execute(
                "INSERT INTO history (ts, type, name, status, summary, detail, duration) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    record_type,
                    name,
                    status,
                    summary,
                    json.dumps(detail or {}, ensure_ascii=False),
                    round(duration, 2),
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("写入历史记录失败")


# ── 查询 ──

def query(
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    config_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """查询历史记录 (按时间倒序)"""
    conn = _get_conn(config_path)
    sql = "SELECT * FROM history WHERE 1=1"
    params: list = []
    if record_type:
        sql += " AND type = ?"
        params.append(record_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _db_lock:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["detail"] = json.loads(d.get("detail", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["detail"] = {}
        result.append(d)
    return result


def stats(days: int = 7, config_path: Optional[str] = None) -> Dict[str, Any]:
    """统计最近 N 天的执行概况"""
    conn = _get_conn(config_path)
    cutoff = "datetime('now', 'localtime', '-{} days')".format(int(days))

    with _db_lock:
        total = conn.execute(
            "SELECT COUNT(*) FROM history WHERE ts >= {}".format(cutoff)
        ).fetchone()[0]

        by_type = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM history "
            "WHERE ts >= {} GROUP BY type".format(cutoff)
        ).fetchall()

        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM history "
            "WHERE ts >= {} GROUP BY status".format(cutoff)
        ).fetchall()

        recent = conn.execute(
            "SELECT * FROM history WHERE ts >= {} "
            "ORDER BY ts DESC LIMIT 10".format(cutoff)
        ).fetchall()

    recent_list = []
    for row in recent:
        d = dict(row)
        try:
            d["detail"] = json.loads(d.get("detail", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["detail"] = {}
        recent_list.append(d)

    return {
        "days": days,
        "total": total,
        "by_type": {row["type"]: row["cnt"] for row in by_type},
        "by_status": {row["status"]: row["cnt"] for row in by_status},
        "recent": recent_list,
    }


def cleanup(keep_days: int = 90, config_path: Optional[str] = None) -> int:
    """清理超过 N 天的历史记录"""
    conn = _get_conn(config_path)
    cutoff = "datetime('now', 'localtime', '-{} days')".format(int(keep_days))
    with _db_lock:
        cursor = conn.execute("DELETE FROM history WHERE ts < {}".format(cutoff))
        conn.commit()
        return cursor.rowcount
