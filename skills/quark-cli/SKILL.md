# quark-cli — AI Agent 技能定义

<command-name>quark-cli</command-name>

## Description

quark-cli 是一个夸克云盘 + 影视媒体中心管理工具，提供 CLI 命令行、Web Dashboard、定时调度、文件同步、飞书 Bot 等全链路能力。本 Skill 告诉 Agent 如何理解和使用 quark-cli 的所有功能。

## Trigger

当用户涉及以下场景时触发：
- 夸克网盘操作（签到、转存、搜索、文件管理）
- 影视媒体管理（TMDB/豆瓣查询、媒体库管理）
- 分享链接解析与转存
- 定时任务与自动追剧
- 文件同步（WebDAV → NAS）
- quark-cli 项目开发与维护

## Overview

### 核心能力

| 模块 | 功能 | CLI 命令 | Web API |
|------|------|----------|---------|
| 账号 | 登录/签到/空间查看 | `account info/sign/verify` | `/api/account/*` |
| 分享 | 检查/浏览/转存分享链接 | `share check/list/save` | `/api/share/*` |
| 搜索 | 多源聚合搜索网盘资源 | `search query/save/sources` | `/api/search/*` |
| 网盘 | 文件浏览/创建/删除/重命名 | `drive ls/mkdir/rename/rm` | `/api/drive/*` |
| 媒体 | 影视中心连接/库浏览/搜索 | `media login/lib/search/info` | `/api/media/*` |
| 发现 | TMDB/豆瓣影视推荐与元数据 | `media discover/meta` | `/api/discovery/*` |
| 转存 | 自动搜索+智能重命名+转存 | `media auto-save` | — |
| 同步 | WebDAV 挂载 → NAS 本地同步 | `sync run/status/config` | `/api/sync/*` |
| 调度 | 定时发现+搜索+转存+通知 | `task run` | `/api/scheduler/*` |
| 追剧 | 订阅剧集+集数追踪+自动转存 | — | `/api/subscribe/*` |
| Bot | 飞书机器人影视转存 | `bot` | — |
| Web | 管理面板 (React SPA) | `serve` | 全部 |

### 安装

```bash
# Docker (推荐)
docker run -d --name quark-cli \
  -p 9090:9090 \
  -v ~/.quark-cli:/root/.quark-cli \
  ghcr.io/zhangjian3032/quark-cli:main

# pip
pip install -e .
```

---

## Instructions

### 1. 配置管理

quark-cli 的所有配置存储在 `~/.quark-cli/config.json` 中。

```bash
# 设置夸克 Cookie (必需)
quark-cli config set-cookie "your_cookie"

# 查看当前配置
quark-cli config show

# 设置 TMDB API Key (影视发现需要)
quark-cli media config --tmdb-key "your_tmdb_v3_key"

# 设置 fnOS 媒体中心连接
quark-cli media login --host 192.168.1.100 -u admin
```

配置文件结构:
```json
{
  "cookie": "夸克 Cookie",
  "media": {
    "provider": "fnos",
    "fnos": { "host": "...", "port": 5666, "token": "..." },
    "discovery": {
      "source": "tmdb",
      "tmdb_api_key": "...",
      "cache": { "enabled": true, "list_ttl": 1800 }
    }
  },
  "sync": {
    "tasks": [
      { "name": "电影同步", "source": "/mnt/alist/电影", "dest": "/mnt/nas/电影" }
    ]
  },
  "bot": { "app_id": "...", "app_secret": "..." }
}
```

### 2. CLI 命令速查

#### 账号与签到
```bash
quark-cli account info                    # 账号信息
quark-cli account sign                    # 每日签到
quark-cli account verify                  # 验证 Cookie
```

#### 分享链接转存
```bash
quark-cli share check <url>               # 检查链接有效性
quark-cli share list <url>                # 列出文件
quark-cli share save <url> /保存路径      # 转存
quark-cli share save <url> /路径 -p "\.mkv$"           # 正则过滤
quark-cli share save <url> /路径 -p "^广告(.*)" -r "\1" # 正则重命名
```

#### 网盘资源搜索
```bash
quark-cli search query "流浪地球"         # 搜索
quark-cli search save "流浪地球" /媒体/电影  # 搜索 + 转存
quark-cli search sources                  # 查看搜索源
```

#### 网盘文件操作
```bash
quark-cli drive ls /                      # 根目录
quark-cli drive ls /媒体/电影 --size      # 带文件大小
quark-cli drive mkdir /媒体/电影/新目录   # 创建目录
quark-cli drive rename /路径 新名称       # 重命名
quark-cli drive rm /路径                  # 删除
quark-cli drive search "关键词"           # 搜索
```

#### 影视发现 (TMDB/豆瓣)
```bash
# 元数据查询
quark-cli media meta "流浪地球2"                    # 自动搜索
quark-cli media meta --tmdb 906126                   # TMDB ID
quark-cli media meta --douban 35267208               # 豆瓣 ID
quark-cli media meta -s douban "霸王别姬"           # 指定豆瓣源

# 影视推荐
quark-cli media discover --list top_rated            # 高分电影
quark-cli media discover --list popular -t tv        # 热门剧集
quark-cli media discover --list trending             # 趋势
quark-cli media discover -s douban --tag "科幻"     # 豆瓣标签
quark-cli media discover --list discover --genre "动作" --min-rating 7.5
```

`--source` / `-s` 参数: `auto` (默认，TMDB 优先) | `tmdb` | `douban`

#### 自动搜索转存
```bash
quark-cli media auto-save "流浪地球2"
quark-cli media auto-save "权力的游戏" -t tv --save-path "/媒体/剧集/权力的游戏"
quark-cli media auto-save "三体" --dry-run  # 仅搜索，不转存
```

#### 文件同步
```bash
quark-cli sync run                         # 按配置同步
quark-cli sync run --source /mnt/alist --dest /mnt/nas  # 手动路径
quark-cli sync status                      # 同步状态
quark-cli sync config --show               # 查看配置
```

#### 定时任务
```bash
quark-cli task list                        # 查看任务
quark-cli task add                         # 添加任务
quark-cli task run                         # 执行全部
quark-cli task run --index 0               # 执行指定
```

#### 飞书 Bot
```bash
quark-cli bot                              # 启动 (从配置读凭证)
quark-cli bot --app-id <id> --app-secret <secret>
```

#### Web 面板
```bash
quark-cli serve                            # 默认 0.0.0.0:9090
quark-cli serve --port 8080 --host 127.0.0.1
```

### 3. Web API 端点

Base URL: `http://<host>:9090/api`

| 分类 | 端点 | 说明 |
|------|------|------|
| 账号 | `GET /account/info` | 账号信息 |
| 账号 | `POST /account/sign` | 签到 |
| 配置 | `GET /config` | 获取配置 |
| 配置 | `PUT /config/cookie` | 设置 Cookie |
| 配置 | `GET /config/export` | 导出配置 |
| 配置 | `POST /config/import` | 导入配置 |
| 保活 | `GET /keepalive/status` | 保活状态 |
| 保活 | `POST /keepalive/toggle` | 启停保活 |
| 搜索 | `GET /search/query?q=...` | 搜索资源 |
| 分享 | `GET /share/list?url=...` | 列出文件 |
| 分享 | `POST /share/save` | 转存 |
| 网盘 | `GET /drive/ls?path=/` | 列目录 |
| 网盘 | `POST /drive/mkdir` | 创建目录 |
| 网盘 | `POST /drive/delete` | 删除 |
| 发现 | `GET /discovery/meta?name=...` | 元数据查询 |
| 发现 | `GET /discovery/list?list_type=top_rated` | 推荐列表 |
| 发现 | `GET /discovery/tags?source=douban` | 豆瓣标签 |
| 媒体 | `GET /media/libraries` | 媒体库列表 |
| 媒体 | `GET /media/search?q=...` | 搜索影片 |
| 同步 | `POST /sync/run` | 触发同步 |
| 同步 | `GET /sync/status` | 同步状态 |
| 调度 | `GET /scheduler/status` | 调度器状态 |
| 调度 | `POST /scheduler/start` | 启动调度器 |
| 追剧 | `GET /subscribe/list` | 订阅列表 |
| 追剧 | `POST /subscribe/add` | 添加订阅 |
| 历史 | `GET /dashboard/stats` | Dashboard 统计 |
| 历史 | `GET /dashboard/history` | 执行历史 |

### 4. Docker 部署

```yaml
# docker-compose.yml
services:
  quark-cli:
    image: ghcr.io/zhangjian3032/quark-cli:main
    container_name: quark-cli
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./config:/root/.quark-cli
      # WebDAV 挂载（同步用）
      # - /mnt/alist:/mnt/alist:ro
      # NAS 目标目录
      # - /mnt/nas/media:/mnt/nas/media
    environment:
      - TZ=Asia/Shanghai
```

### 5. 常见工作流

#### 工作流 A: 搜索并转存一部电影
```bash
# 1. 查询元数据获取标准名
quark-cli media meta "流浪地球2"
# 2. 搜索网盘资源
quark-cli search query "流浪地球2 2160p"
# 3. 转存到网盘
quark-cli share save <url> "/媒体/电影/流浪地球2 (2023)"
# 或一键完成:
quark-cli media auto-save "流浪地球2"
```

#### 工作流 B: 设置自动追剧
```bash
# 1. 启动 Web 面板
quark-cli serve
# 2. 浏览器打开 http://localhost:9090
# 3. 在"订阅追剧"页面添加剧集
# 4. 调度器会自动检查新集并转存
```

#### 工作流 C: 全自动化流水线
```bash
# Docker 部署后，Web 面板自动启动
# 1. 配置 Cookie + TMDB Key
# 2. 配置同步任务 (WebDAV → NAS)
# 3. 配置飞书 Bot (转存通知)
# 4. 启动调度器 → 自动发现 + 搜索 + 转存 + 同步 + 通知
```

---

## Project Structure

```
quark-cli/
├── quark_cli/
│   ├── cli.py              # CLI 入口 (argparse)
│   ├── config.py            # 配置管理
│   ├── api.py               # 夸克网盘 API Client
│   ├── search.py            # 多源搜索引擎
│   ├── rename.py            # 正则重命名
│   ├── scheduler.py         # 定时调度 + 飞书通知
│   ├── subscribe.py         # 订阅追剧
│   ├── history.py           # SQLite 执行历史
│   ├── keepalive.py         # Cookie 保活 + 自动签到
│   ├── commands/            # CLI 子命令实现
│   ├── media/
│   │   ├── discovery/       # TMDB + 豆瓣数据源
│   │   ├── fnos/            # fnOS Provider
│   │   ├── sync.py          # 文件同步引擎
│   │   └── autosave.py      # 自动搜索转存
│   ├── services/            # Web Service 层
│   └── web/
│       ├── app.py           # FastAPI 应用
│       └── routes/          # API 路由
├── web/                     # React 前端 (Vite + Tailwind)
├── docs/                    # 文档
├── skills/                  # Agent Skills
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### 开发规范

- **Commit 格式**: `<type>(<scope>): <描述>` — type: feat/fix/chore/docs/build
- **多数据源**: `--source auto|tmdb|douban`，auto 优先 TMDB 失败回落豆瓣
- **懒导入**: 大型依赖在函数内 `from xxx import yyy`
- **交付**: `git format-patch` 打包为 tar.gz

## Notes

- GitHub: https://github.com/zhangjian3032/quark-cli
- Docker 镜像: `ghcr.io/zhangjian3032/quark-cli:main`
- 默认端口: 9090
- 配置路径: `~/.quark-cli/config.json`
