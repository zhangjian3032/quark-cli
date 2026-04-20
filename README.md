# Quark CLI

夸克网盘一站式管理工具 — 签到 / 搜索 / 转存 / 文件管理 / 影视中心 / 定时任务 / 订阅追剧 + Web 管理面板。

![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen)

## 功能概览

| 模块 | 说明 |
|------|------|
| 📋 配置管理 | Cookie 设置 / 配置导入导出 |
| 👤 账号管理 | 账号信息 / 每日签到 / Cookie 保活 |
| 🔗 分享链接 | 检查有效性 / 列出文件 / 转存到网盘 |
| 🔍 资源搜索 | 多引擎网盘资源搜索 / 一键转存 |
| 📂 网盘操作 | 列目录 / 创建 / 重命名 / 删除 / 下载 |
| ⏱ 定时任务 | 自动追更转存 / Cron 调度 |
| 🎬 影视中心 | fnOS / Emby / Jellyfin 媒体库管理 |
| 🌟 影视发现 | TMDB + 豆瓣 元数据查询 / 高分推荐 |
| 📡 订阅追剧 | 自动追更 / 剧集追踪 |
| 🔄 文件同步 | WebDAV 挂载 → NAS 本地同步 |
| 🤖 飞书机器人 | 影视自动转存 Bot |
| 📥 Torrent 推送 | RSS → qBittorrent 自动下载 (支持 magnet / .torrent) |
| 🖥 Web 面板 | React + FastAPI 可视化管理 |

## Quick Start

### 1. Docker 部署（推荐）

```bash
# 创建配置目录
mkdir -p data/config

# 启动
docker compose up -d
```

打开浏览器访问 `http://your-ip:9090`，在 Web 面板中设置 Cookie 即可使用。

> 完整的 Docker 配置和 docker-compose.yml 说明参见 [Docker 部署文档](docs/docker.md)。

### 2. pip 安装

```bash
pip install .

# 或安装全部依赖（含 Web 面板 + 飞书 Bot）
pip install ".[all]"
```

### 3. 配置 Cookie

```bash
quark-cli config set-cookie "your_cookie_here"
quark-cli account info
```

> Cookie 获取方式：浏览器登录 [夸克网盘](https://pan.quark.cn) → F12 开发者工具 → Network → 复制任意请求的 Cookie 头。

### 4. 启动 Web 面板

```bash
quark-cli serve
# 访问 http://localhost:9090
```

## 常用命令速查

```bash
# 签到
quark-cli account sign

# 搜索资源
quark-cli search query "流浪地球2"

# 转存分享链接
quark-cli share save "https://pan.quark.cn/s/xxxxx" /电影

# TMDB / 豆瓣影视推荐
quark-cli media discover --list top_rated
quark-cli media discover -s douban --tag "科幻"

# 查询影视元数据
quark-cli media meta "流浪地球2"
quark-cli media meta --douban 35267208

# 一键搜索+转存
quark-cli media auto-save "流浪地球2"

# 文件同步
quark-cli sync run --source /mnt/alist --dest /mnt/nas

# 配置 qBittorrent
quark-cli torrent config --host 192.168.1.100 --port 8080 --username admin --password xxx
quark-cli torrent test

# 手动推送种子
quark-cli torrent add "magnet:?xt=urn:btih:xxxx..."

# 启动飞书机器人
quark-cli bot
```

## 文档

| 文档 | 说明 |
|------|------|
| [安装部署](docs/install.md) | pip / venv / pipx 安装方式 |
| [Docker 部署](docs/docker.md) | Docker Compose 配置与环境变量 |
| [CLI 命令参考](docs/cli-reference.md) | 全部命令与参数详解 |
| [Web API 文档](docs/web-api.md) | RESTful API 端点一览 |
| [配置说明](docs/configuration.md) | config.json 完整字段说明 |
| [架构扩展](docs/architecture.md) | 添加 Provider / 数据源 / 开发调试 |

## 开源协议

[AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html)

## Reference

- [quark-auto-save](https://github.com/Cp0204/quark-auto-save) — 夸克网盘自动追更转存工具，本项目的灵感来源
