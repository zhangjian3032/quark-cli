"""文件名正则替换 & 魔法重命名

正则重命名引擎 (MagicRename)，支持:
- 魔法正则预设 ($TV / $BLACK_WORD / 自定义)
- 魔法变量 ({TASKNAME} / {E} / {S} / {YEAR} / {DATE} / {I} 等)
- 转存后批量 rename
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class MagicRename:
    """文件名正则替换引擎"""

    # ── 内置魔法正则预设 ──
    BUILTIN_REGEX = {
        "$TV": {
            "pattern": r".*?([Ss]\d{1,2})?(?:[第EePpXx\.\-\_\( ]{1,2}|^)(\d{1,3})(?!\d).*?\.(mp4|mkv)",
            "replace": r"\1E\2.\3",
            "description": "剧集标准化: 提取 SxxExx + 扩展名",
        },
        "$BLACK_WORD": {
            "pattern": r"^(?!.*纯享)(?!.*加更)(?!.*超前企划)(?!.*训练室)(?!.*蒸蒸日上).*",
            "replace": "",
            "description": "黑名单过滤: 排除纯享/加更/超前企划等",
        },
    }

    # ── 内置魔法变量 ──
    BUILTIN_VARIABLES = {
        "{TASKNAME}": "",
        "{I}": 1,
        "{EXT}": [r"(?<=\.)\w+$"],
        "{CHINESE}": [r"[\u4e00-\u9fa5]{2,}"],
        "{DATE}": [
            r"(18|19|20)?\d{2}[\.\-/年]\d{1,2}[\.\-/月]\d{1,2}",
            r"(?<!\d)[12]\d{3}[01]?\d[0123]?\d",
            r"(?<!\d)[01]?\d[\.\-/月][0123]?\d",
        ],
        "{YEAR}": [r"(?<!\d)(18|19|20)\d{2}(?!\d)"],
        "{S}": [r"(?<=[Ss])\d{1,2}(?=[EeXx])", r"(?<=[Ss])\d{1,2}"],
        "{SXX}": [r"[Ss]\d{1,2}(?=[EeXx])", r"[Ss]\d{1,2}"],
        "{E}": [
            r"(?<=[Ss]\d\d[Ee])\d{1,3}",
            r"(?<=[Ee])\d{1,3}",
            r"(?<=[Ee][Pp])\d{1,3}",
            r"(?<=第)\d{1,3}(?=[集期话部篇])",
            r"(?<!\d)\d{1,3}(?=[集期话部篇])",
            r"(?!.*19)(?!.*20)(?<=[\._])\d{1,3}(?=[\._])",
            r"^\d{1,3}(?=\.\w+)",
            r"(?<!\d)\d{1,3}(?!\d)(?!$)",
        ],
        "{PART}": [
            r"(?<=[集期话部篇第])[上中下一二三四五六七八九十]",
            r"[上中下一二三四五六七八九十]",
        ],
        "{VER}": [r"[\u4e00-\u9fa5]+版"],
    }

    def __init__(self, custom_regex: Optional[Dict] = None, taskname: str = ""):
        self.magic_regex = dict(self.BUILTIN_REGEX)
        if custom_regex:
            self.magic_regex.update(custom_regex)

        self.magic_variable = {}
        for k, v in self.BUILTIN_VARIABLES.items():
            if isinstance(v, list):
                self.magic_variable[k] = list(v)
            else:
                self.magic_variable[k] = v

        if taskname:
            self.magic_variable["{TASKNAME}"] = taskname

    # ── 公开 API ──

    def resolve_pattern(self, pattern: str, replace: str = "") -> Tuple[str, str]:
        """解析魔法正则预设: $TV → 实际的 pattern + replace"""
        if pattern in self.magic_regex:
            preset = self.magic_regex[pattern]
            real_pattern = preset["pattern"]
            if not replace:
                replace = preset.get("replace", "")
            return real_pattern, replace
        return pattern, replace

    def rename(self, pattern: str, replace: str, file_name: str) -> str:
        """对单个文件名应用正则替换 (含魔法变量展开)

        Args:
            pattern: 正则模式 (可以是 $TV 等预设名)
            replace: 替换模板 (可包含魔法变量)
            file_name: 原文件名

        Returns:
            替换后的文件名，若 replace 为空则返回原名
        """
        # 解析预设 (需在检查 replace 之前，因为预设可能填充 replace)
        real_pattern, real_replace = self.resolve_pattern(pattern, replace)

        if not real_replace:
            return file_name

        # 展开魔法变量
        expanded_replace = self._expand_variables(real_replace, file_name)

        # 执行替换
        if real_pattern and expanded_replace:
            return re.sub(real_pattern, expanded_replace, file_name)
        elif expanded_replace:
            return expanded_replace
        return file_name

    def match(self, pattern: str, file_name: str) -> bool:
        """检查文件名是否匹配 pattern (用于过滤)"""
        if not pattern:
            return True
        real_pattern, _ = self.resolve_pattern(pattern)
        try:
            return bool(re.search(real_pattern, file_name))
        except re.error:
            return False

    def preview_batch(
        self, pattern: str, replace: str, file_names: List[str]
    ) -> List[dict]:
        """批量预览重命名结果

        Returns:
            [{"original": "xxx", "renamed": "yyy", "changed": True/False, "filtered": True/False}]
        """
        results = []
        for name in file_names:
            matched = self.match(pattern, name)
            if matched:
                new_name = self.rename(pattern, replace, name)
                # $BLACK_WORD 的 replace="" 表示过滤掉
                if not replace or new_name:
                    results.append({
                        "original": name,
                        "renamed": new_name,
                        "changed": new_name != name,
                        "filtered": False,
                    })
                else:
                    results.append({
                        "original": name,
                        "renamed": "",
                        "changed": False,
                        "filtered": True,
                    })
            else:
                results.append({
                    "original": name,
                    "renamed": name,
                    "changed": False,
                    "filtered": True,
                })
        return results

    def list_presets(self) -> List[dict]:
        """列出所有可用的魔法正则预设"""
        presets = []
        for key, val in self.magic_regex.items():
            presets.append({
                "name": key,
                "pattern": val["pattern"],
                "replace": val.get("replace", ""),
                "description": val.get("description", ""),
            })
        return presets

    def list_variables(self) -> List[dict]:
        """列出所有可用的魔法变量"""
        variables = []
        descriptions = {
            "{TASKNAME}": "任务名称",
            "{I}": "自增序号 (可用 {II} {III} 补零)",
            "{EXT}": "文件扩展名",
            "{CHINESE}": "中文字符 (≥2字)",
            "{DATE}": "日期 (多种格式)",
            "{YEAR}": "年份 (4位)",
            "{S}": "季号数字 (如 01)",
            "{SXX}": "季号含前缀 (如 S01)",
            "{E}": "集号数字 (多种匹配规则)",
            "{PART}": "分集标记 (上/中/下/一/二...)",
            "{VER}": "版本 (如 国语版、粤语版)",
        }
        for key in self.magic_variable:
            variables.append({
                "name": key,
                "description": descriptions.get(key, ""),
            })
        return variables

    # ── 内部方法 ──

    def _expand_variables(self, replace: str, file_name: str) -> str:
        """展开替换模板中的魔法变量"""
        result = replace

        for key, p_list in self.magic_variable.items():
            if key not in result:
                continue

            # 正则类变量：从文件名中提取
            if isinstance(p_list, list) and p_list:
                matched = False
                for p in p_list:
                    m = re.search(p, file_name)
                    if m:
                        value = m.group()
                        # 日期格式特殊处理
                        if key == "{DATE}":
                            value = "".join(c for c in value if c.isdigit())
                            value = str(datetime.now().year)[:(8 - len(value))] + value
                        result = result.replace(key, value)
                        matched = True
                        break
                if not matched:
                    # 未匹配到的变量清理
                    if key == "{SXX}":
                        result = result.replace(key, "S01")
                    else:
                        result = result.replace(key, "")

            # 字符串类变量：直接替换
            elif isinstance(p_list, str):
                result = result.replace(key, p_list)

            # {I} 跳过 (需要 sort_file_list 处理)

        return result
