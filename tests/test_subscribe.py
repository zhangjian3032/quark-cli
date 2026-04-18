"""订阅追剧引擎单元测试"""

import json
import os
import tempfile
import pytest

from quark_cli.subscribe import (
    extract_episode,
    build_search_queries,
    filter_candidates,
    _merge_sub_defaults,
    update_subscription_state,
    format_subscribe_notify,
)


# ═══════════════════════════════════════════════
#  集数提取器
# ═══════════════════════════════════════════════

class TestExtractEpisode:
    def test_sxxexx(self):
        assert extract_episode("三体.2024.S01E05.4K.WEB-DL.mkv") == (1, 5)

    def test_sxxexx_lowercase(self):
        assert extract_episode("The.Three-Body.s02e12.1080p.mp4") == (2, 12)

    def test_season_episode_full(self):
        assert extract_episode("Season 1 Episode 8") == (1, 8)

    def test_chinese_format(self):
        assert extract_episode("庆余年 第2季第15集 4K") == (2, 15)

    def test_chinese_hua(self):
        assert extract_episode("鬼灭之刃 第3季第7话") == (3, 7)

    def test_ep_only(self):
        s, e = extract_episode("三体 EP06 1080p")
        assert e == 6

    def test_e_only(self):
        s, e = extract_episode("三体 E08.mkv")
        assert e == 8

    def test_bracket_number(self):
        s, e = extract_episode("[Lilith-Raws] 三体 - [05].mp4")
        assert e == 5

    def test_dot_number(self):
        s, e = extract_episode("SanTi.2024.03.1080p.mkv")
        assert e == 3

    def test_chinese_ji(self):
        s, e = extract_episode("庆余年 第12集")
        assert e == 12

    def test_no_match(self):
        assert extract_episode("三体.2024.4K.COMPLETE.PACK.mkv") == (None, None)

    def test_default_season(self):
        s, e = extract_episode("E05.mkv", default_season=2)
        assert s == 2
        assert e == 5


# ═══════════════════════════════════════════════
#  搜索关键词构造
# ═══════════════════════════════════════════════

class TestBuildSearchQueries:
    def test_basic(self):
        q = build_search_queries("三体 2024", 1, 5)
        assert q[0] == "三体 2024 S01E05"
        assert q[1] == "三体 2024 第5集"
        assert q[2] == "三体 2024 E05"
        assert q[3] == "三体 2024"
        assert len(q) == 4

    def test_double_digit(self):
        q = build_search_queries("庆余年", 2, 15)
        assert "S02E15" in q[0]


# ═══════════════════════════════════════════════
#  候选筛选
# ═══════════════════════════════════════════════

class TestFilterCandidates:
    def setup_method(self):
        self.results = [
            {"title": "三体.S01E04.1080p.mkv", "url": "https://a", "score": 50},
            {"title": "三体.S01E05.4K.WEB-DL.mkv", "url": "https://b", "score": 80},
            {"title": "三体.S01E05.720p.HDTV.mkv", "url": "https://c", "score": 40},
            {"title": "三体.S01E06.1080p.mkv", "url": "https://d", "score": 60},
        ]

    def test_match_episode(self):
        c = filter_candidates(self.results, season=1, episode=5)
        assert c is not None
        assert "S01E05" in c["title"]
        # 应该选 score 最高的
        assert c["url"] == "https://b"

    def test_no_match(self):
        c = filter_candidates(self.results, season=1, episode=10)
        assert c is None

    def test_quality_preference(self):
        # 指定 720p 优先
        c = filter_candidates(self.results, season=1, episode=5, quality_re="720p")
        assert c["url"] == "https://c"

    def test_quality_fallback(self):
        # 指定不存在的画质, 应 fallback 到 score 最高
        c = filter_candidates(self.results, season=1, episode=5, quality_re="REMUX")
        assert c["url"] == "https://b"


# ═══════════════════════════════════════════════
#  默认值合并
# ═══════════════════════════════════════════════

class TestMergeDefaults:
    def test_fill_defaults(self):
        sub = _merge_sub_defaults({"name": "三体"})
        assert sub["name"] == "三体"
        assert sub["season"] == 1
        assert sub["next_episode"] == 1
        assert sub["enabled"] is True
        assert sub["finished"] is False

    def test_override(self):
        sub = _merge_sub_defaults({"name": "test", "season": 3, "quality": "4K"})
        assert sub["season"] == 3
        assert sub["quality"] == "4K"


# ═══════════════════════════════════════════════
#  状态回写
# ═══════════════════════════════════════════════

class TestUpdateState:
    def test_update_after_success(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "subscriptions": [
                {
                    "name": "三体",
                    "season": 1,
                    "next_episode": 5,
                    "last_episode": 4,
                    "miss_count": 0,
                    "episodes_found": [1, 2, 3, 4],
                    "finished": False,
                }
            ]
        }))

        check_result = {
            "name": "三体",
            "new_episodes": [
                {"season": 1, "episode": 5},
                {"season": 1, "episode": 6},
            ],
            "finished": False,
        }

        update_subscription_state(str(config_file), "三体", check_result)

        with open(config_file) as f:
            data = json.load(f)

        sub = data["subscriptions"][0]
        assert sub["next_episode"] == 7
        assert sub["last_episode"] == 6
        assert sub["miss_count"] == 0
        assert 5 in sub["episodes_found"]
        assert 6 in sub["episodes_found"]
        assert sub["last_check"] is not None

    def test_update_miss(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "subscriptions": [
                {
                    "name": "庆余年",
                    "miss_count": 2,
                    "next_episode": 10,
                    "finished": False,
                }
            ]
        }))

        check_result = {
            "name": "庆余年",
            "new_episodes": [],
            "finished": False,
        }

        update_subscription_state(str(config_file), "庆余年", check_result)

        with open(config_file) as f:
            data = json.load(f)

        assert data["subscriptions"][0]["miss_count"] == 3

    def test_mark_finished(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "subscriptions": [{"name": "完结剧", "finished": False}]
        }))

        check_result = {
            "name": "完结剧",
            "new_episodes": [],
            "finished": True,
        }

        update_subscription_state(str(config_file), "完结剧", check_result)

        with open(config_file) as f:
            data = json.load(f)

        assert data["subscriptions"][0]["finished"] is True


# ═══════════════════════════════════════════════
#  飞书通知格式化
# ═══════════════════════════════════════════════

class TestNotifyFormat:
    def test_new_episodes(self):
        result = {
            "name": "三体",
            "new_episodes": [
                {"season": 1, "episode": 5, "save_path": "/追剧/三体"},
                {"season": 1, "episode": 6, "save_path": "/追剧/三体"},
            ],
        }
        content = format_subscribe_notify({"name": "三体"}, result)
        assert "zh_cn" in content
        assert "三体" in content["zh_cn"]["title"]
        # 检查内容包含集数
        texts = [line[0]["text"] for line in content["zh_cn"]["content"]]
        found_eps = any("E05" in t and "E06" in t for t in texts)
        assert found_eps

    def test_finished(self):
        result = {"name": "三体", "new_episodes": [], "finished": True}
        content = format_subscribe_notify({"name": "三体"}, result)
        assert "完结" in str(content)

    def test_no_content_when_empty(self):
        result = {"name": "三体", "new_episodes": []}
        content = format_subscribe_notify({"name": "三体"}, result)
        assert content == {}
