# Quark CLI Skill Agent

## 概述

Quark CLI Skill Agent 是一个基于 `quark-cli` 工具构建的自动化技能代理，可集成到 AI 助手、Telegram Bot、飞书机器人等平台，提供自然语言到 CLI 命令的映射。

## Skill 定义

### skill: quark-drive

**触发条件**: 用户提及"夸克网盘"、"quark"、"转存"、"签到"、"网盘文件"等关键词

**能力范围**:

| Skill ID | 名称 | 描述 | 触发词示例 |
|----------|------|------|-----------|
| `quark.sign` | 每日签到 | 执行夸克网盘每日签到 | "夸克签到"、"签到领空间" |
| `quark.share.check` | 检查链接 | 检查分享链接是否有效 | "检查这个链接"、"链接还有效吗" |
| `quark.share.list` | 列出分享 | 列出分享链接中的文件 | "看看这个分享里有什么" |
| `quark.share.save` | 转存文件 | 从分享链接转存文件 | "帮我转存"、"保存到网盘" |
| `quark.drive.ls` | 浏览网盘 | 列出网盘目录内容 | "看看网盘里有什么"、"列出文件" |
| `quark.drive.search` | 搜索文件 | 搜索网盘中的文件 | "搜索XXX"、"找一下XXX" |
| `quark.task.run` | 执行任务 | 执行全部自动转存任务 | "执行转存任务"、"开始追更" |
| `quark.account.info` | 账号信息 | 查看夸克账号信息 | "我的账号"、"查看账号" |

### Skill Schema

```yaml
name: quark-drive
version: 1.0.0
description: 夸克网盘 CLI 技能 - 签到/转存/文件管理
author: quark-cli

triggers:
  - pattern: "(夸克|quark).*(签到|sign)"
    action: quark.sign
  - pattern: "(检查|验证|check).*(链接|link|分享|share)"
    action: quark.share.check
  - pattern: "(列出|查看|list).*(分享|share)"
    action: quark.share.list
  - pattern: "(转存|保存|save).*(分享|share|链接)"
    action: quark.share.save
  - pattern: "(列出|查看|浏览|ls).*(网盘|目录|文件夹)"
    action: quark.drive.ls
  - pattern: "(搜索|查找|search).*(网盘|文件)"
    action: quark.drive.search
  - pattern: "(执行|运行|run).*(任务|task|转存)"
    action: quark.task.run
  - pattern: "(账号|account|信息|info)"
    action: quark.account.info

parameters:
  quark.share.check:
    - name: url
      type: string
      required: true
      description: 分享链接 URL
      extract: "https?://pan\\.quark\\.cn/s/\\w+"

  quark.share.list:
    - name: url
      type: string
      required: true
      description: 分享链接 URL

  quark.share.save:
    - name: url
      type: string
      required: true
      description: 分享链接 URL
    - name: savepath
      type: string
      required: true
      description: 保存路径
      default: "/来自分享"
    - name: pattern
      type: string
      required: false
      description: 正则过滤
      default: ".*"

  quark.drive.ls:
    - name: path
      type: string
      required: false
      description: 目录路径
      default: "/"

  quark.drive.search:
    - name: keyword
      type: string
      required: true
      description: 搜索关键词

  quark.task.run: {}
  quark.sign: {}
  quark.account.info: {}
```

## Agent 集成示例

### Python Agent 接口

```python
import subprocess
import json


class QuarkSkillAgent:
    """夸克网盘技能代理"""

    def __init__(self, config_path=None):
        self.base_cmd = ["quark-cli"]
        if config_path:
            self.base_cmd.extend(["-c", config_path])

    def execute(self, skill_id: str, params: dict = None) -> dict:
        """执行技能"""
        cmd = self._build_command(skill_id, params or {})
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
        }

    def _build_command(self, skill_id: str, params: dict) -> list:
        """技能 ID 到 CLI 命令的映射"""
        mapping = {
            "quark.sign": ["account", "sign"],
            "quark.account.info": ["account", "info"],
            "quark.share.check": ["share", "check", params.get("url", "")],
            "quark.share.list": ["share", "list", params.get("url", "")],
            "quark.share.save": [
                "share", "save",
                params.get("url", ""),
                params.get("savepath", "/来自分享"),
                "--pattern", params.get("pattern", ".*"),
            ],
            "quark.drive.ls": ["drive", "ls", params.get("path", "/")],
            "quark.drive.search": ["drive", "search", params.get("keyword", "")],
            "quark.task.run": ["task", "run"],
        }
        sub_cmd = mapping.get(skill_id, [])
        return self.base_cmd + sub_cmd


# 使用示例
agent = QuarkSkillAgent()

# 签到
result = agent.execute("quark.sign")
print(result["output"])

# 检查链接
result = agent.execute("quark.share.check", {"url": "https://pan.quark.cn/s/xxxxx"})
print(result["output"])

# 转存
result = agent.execute("quark.share.save", {
    "url": "https://pan.quark.cn/s/xxxxx",
    "savepath": "/我的资源/电影",
    "pattern": r"\.mp4$"
})
print(result["output"])
```

### Crontab 自动化

```bash
# 每天 8 点签到
0 8 * * * /usr/local/bin/quark-cli account sign >> /var/log/quark-sign.log 2>&1

# 每天 8/18/20 点执行转存任务
0 8,18,20 * * * /usr/local/bin/quark-cli task run >> /var/log/quark-task.log 2>&1

# 每周一检查分享链接
0 9 * * 1 /usr/local/bin/quark-cli share check "https://pan.quark.cn/s/xxx" >> /var/log/quark-check.log 2>&1
```

### Shell 脚本编排

```bash
#!/bin/bash
# quark-auto.sh - 自动签到 + 转存 + 通知

LOG_FILE="/tmp/quark-$(date +%Y%m%d).log"

echo "====== $(date) ======" >> "$LOG_FILE"

# 签到
quark-cli account sign >> "$LOG_FILE" 2>&1

# 执行任务
quark-cli task run >> "$LOG_FILE" 2>&1

# 检查重要链接
quark-cli share check "https://pan.quark.cn/s/important_share" >> "$LOG_FILE" 2>&1

echo "完成" >> "$LOG_FILE"
```

## 安全注意事项

1. Cookie 仅存储在本地 `~/.quark-cli/config.json`
2. 不要将配置文件提交到版本控制
3. 服务器部署时限制配置文件权限: `chmod 600 ~/.quark-cli/config.json`
4. 严禁高频调用 API，遵守夸克官方频率限制
