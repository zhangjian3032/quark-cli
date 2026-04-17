# Quark CLI - 产品需求文档 (PRD)

## 1. 产品概述

### 1.1 产品名称
**Quark CLI** - 夸克网盘命令行工具

### 1.2 产品定位
基于 [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 项目的 API 封装，提供纯 CLI 交互体验，面向具备技术背景的用户，支持在终端/脚本/CI 环境中管理夸克网盘和影视媒体中心。

### 1.3 目标用户
| 用户画像 | 使用场景 |
|----------|----------|
| 开发者/技术爱好者 | 在服务器上通过命令行管理网盘、定时执行转存 |
| NAS/HTPC 用户 | 自动追更资源、配合 fnOS/Emby/Jellyfin 管理影视库 |
| 脚本自动化用户 | 在 crontab/CI 中批量管理转存任务 |
| 命令行偏好用户 | 不依赖 Docker/WebUI，轻量化使用 |

### 1.4 核心价值
- **零部署成本**：`pip install` 即用，无需 Docker/WebUI
- **脚本友好**：所有操作均为命令行参数，可嵌入 cron/CI
- **功能完整**：覆盖签到、分享检查、转存、文件管理、任务调度、影视媒体管理
- **配置持久化**：`~/.quark-cli/config.json` 统一管理
- **多 Provider 架构**：影视媒体中心支持 fnOS，预留 Emby/Jellyfin 扩展

---

## 2. 功能架构

```
quark-cli
├── config          # 配置管理
│   ├── set-cookie  # 设置 Cookie
│   ├── show        # 查看配置
│   ├── path        # 配置路径
│   ├── reset       # 重置配置
│   └── remove-cookie # 删除 Cookie
├── account         # 账号管理
│   ├── info        # 账号信息
│   ├── sign        # 每日签到
│   ├── verify      # 验证 Cookie
│   └── space       # 空间查询
├── share           # 分享链接
│   ├── check       # 检查有效性
│   ├── list        # 列出文件
│   └── save        # 转存文件
├── search          # 资源搜索
│   ├── query       # 搜索资源
│   ├── sources     # 列出搜索源
│   ├── set-source  # 配置搜索源
│   └── save        # 搜索并转存
├── drive           # 网盘文件
│   ├── ls          # 列目录
│   ├── mkdir       # 创建目录
│   ├── rename      # 重命名
│   ├── download    # 下载链接
│   ├── delete      # 删除
│   └── search      # 搜索
├── task            # 任务管理
│   ├── list        # 查看任务
│   ├── add         # 添加任务
│   ├── remove      # 删除任务
│   ├── run         # 批量执行
│   └── run-one     # 单任务执行
└── media           # 影视媒体中心 (NEW)
    ├── login       # 登录
    ├── status      # 连接状态
    ├── config      # 查看/修改配置
    ├── lib         # 媒体库管理
    │   ├── list    # 列出媒体库
    │   └── show    # 查看媒体库影片
    ├── search      # 搜索影片
    ├── info        # 影片详情
    ├── poster      # 下载海报
    ├── export      # 导出影片列表
    └── playing     # 继续观看列表
```

---

## 3. 功能详细描述

### 3.1 配置管理 (`config`)

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `set-cookie` | 设置夸克 Cookie | `<cookie>` 字符串，`-i` 账号索引 |
| `show` | 查看当前配置（Cookie 脱敏） | - |
| `path` | 显示配置文件路径 | - |
| `reset` | 重置为默认配置 | - |
| `remove-cookie` | 移除指定账号 Cookie | `-i` 账号索引 |

**技术要点**：
- 配置存储于 `~/.quark-cli/config.json`
- 支持 `-c` 全局参数指定自定义配置路径
- Cookie 设置后自动验证有效性

### 3.2 账号管理 (`account`)

| 子命令 | 描述 | 输出 |
|--------|------|------|
| `info` | 查看账号详细信息 | 昵称、会员类型、空间信息 |
| `sign` | 每日签到 | 签到奖励、连签进度 |
| `verify` | 验证 Cookie 有效性 | 有效/无效 |
| `space` | 查看空间信息 | 总空间、签到奖励空间 |

**技术要点**：
- 签到需要 Cookie 中包含移动端参数 (`kps`/`sign`/`vcode`)
- 自动检测已签到状态避免重复签到

### 3.3 分享链接操作 (`share`)

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `check` | 检查分享链接状态 | `<url>` |
| `list` | 列出分享中的文件 | `<url>`，`--tree` 树形 |
| `save` | 转存到指定目录 | `<url> <savepath>`，`--pattern`，`--replace` |

**技术要点**：
- 自动解析分享链接中的 pwd_id、passcode、子目录路径
- 支持需提取码的分享链接
- 转存时自动跳过已存在文件
- 支持正则过滤和重命名
- 仅一个文件夹时自动进入子目录
- 分批转存（每批 100 个）

### 3.4 网盘文件操作 (`drive`)

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `ls` | 列目录 | `[path]` 默认 `/` |
| `mkdir` | 创建目录 | `<path>` |
| `rename` | 重命名 | `<fid> <name>` |
| `download` | 获取下载链接 | `<fid>` 支持逗号分隔多个 |
| `delete` | 删除文件 | `<fid...>` 支持多个，`--permanent` |
| `search` | 搜索文件 | `<keyword>`，`--path` 搜索范围 |

### 3.5 任务管理 (`task`)

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `list` | 查看全部任务 | - |
| `add` | 添加任务 | `--name/--url/--savepath`（必选），`--pattern/--replace/--enddate/--runweek` |
| `remove` | 移除任务 | `<index>` 从 1 开始 |
| `run` | 执行全部任务 | - |
| `run-one` | 执行单个任务 | `<index>` |

### 3.6 影视媒体中心 (`media`) 🆕

#### 3.6.1 架构设计

采用 **Provider 抽象模式**，CLI 命令层仅依赖 `MediaProvider` 基类，不直接依赖任何具体实现：

```
MediaProvider (ABC)              ← CLI 命令层依赖此接口
├── FnosMediaProvider            ← fnOS 飞牛影视实现
├── EmbyMediaProvider (future)   ← Emby 实现 (预留)
└── JellyfinMediaProvider (future) ← Jellyfin 实现 (预留)
```

通过 `media.provider` 配置字段切换当前 Provider，新增 Provider 只需：
1. 实现 `MediaProvider` 接口
2. 在 `registry.py` 注册
3. 添加对应配置段

#### 3.6.2 命令列表

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `login` | 登录影视中心 | `--host`、`--port`、`-u`、`-p` |
| `status` | 检查连接状态 | - |
| `config` | 查看/修改配置 | `--show`、`--provider`、`--host`、`--port`、`--token` |
| `lib list` | 列出所有媒体库 | - |
| `lib show` | 查看媒体库影片 | `<name>` / `<guid>`、`-p` 页码、`-s` 每页 |
| `search` | 搜索影片 | `<keyword>`、`-p` 页码、`-s` 每页 |
| `info` | 查看影片详情 | `<guid>` 或影片名称、`-S` 季列表、`-C` 演职人员 |
| `poster` | 下载海报 | `<guid>`、`-o` 输出目录、`-t` 缩略图 |
| `export` | 导出影片列表 | `-o` 输出文件、`-f json/csv`、`-l` 媒体库 |
| `playing` | 继续观看列表 | - |
| `meta` | 查询 TMDB 影视元数据 | `<query>`、`--tmdb`、`--imdb`、`-t movie/tv`、`-y` |
| `discover` | 高分影视推荐 | `--list popular/top_rated/trending/discover`、`-t`、`-p`、`--min-rating`、`--genre`、`-y`、`--country` |

#### 3.6.3 fnOS Provider 技术要点

| 项目 | 说明 |
|------|------|
| API 地址 | `http://<host>:<port>/v/api/v1/` |
| 认证方式 | authx 签名 + Bearer Token |
| 签名算法 | `md5(SALT + url_path + nonce + timestamp + content_hash + api_key)` |
| 默认 API Key | `16CCEB3D-AB42-077D-36A1-F355324E4237` |
| 搜索方式 | 客户端侧关键字过滤（服务端不支持关键字查询） |
| ENV 覆盖 | `FNOS_HOST` / `FNOS_PORT` / `FNOS_TOKEN` / `FNOS_SSL` |

#### 3.6.4 影视发现 (TMDB Discovery) 🆕

**数据源**: TMDB (The Movie Database) API v3 — 免费用于非商业用途。

| 能力 | 说明 |
|------|------|
| 元数据查询 (`meta`) | 按名称/TMDB ID/IMDb ID 获取完整影视元数据 |
| 搜索关键词建议 | 根据中英文标题+年份自动生成网盘搜索关键词 |
| 保存路径建议 | 遵循 Plex/Emby 命名规范生成分类路径 |
| 高分推荐 (`discover`) | 热门/高分/趋势列表 + 高级筛选（类型/年份/地区/评分） |

**架构设计**:

```
DiscoverySource (ABC)            ← CLI 命令层依赖此接口
└── TmdbSource                   ← TMDB API v3 实现
    ├── search()                 # 搜索
    ├── get_detail()             # 详情 (含 credits)
    ├── find_by_external_id()    # IMDb ID 反查
    ├── get_popular()            # 热门
    ├── get_top_rated()          # 高分
    ├── get_trending()           # 趋势
    ├── discover()               # 高级筛选
    └── get_genres()             # 类型列表

NamingEngine
├── suggest_search_keywords()    # 搜索关键词建议
├── suggest_save_path()          # 保存路径建议 (Plex/Emby 规范)
└── format_meta_summary()        # 结构化元数据摘要
```

**TMDB 技术要点**:

| 项目 | 说明 |
|------|------|
| API Base | `https://api.themoviedb.org/3` |
| 认证方式 | API Key v3 (URL 参数) |
| 语言支持 | `zh-CN` (默认), 可配置 |
| 速率限制 | 40 请求/10 秒 |
| 图片 CDN | `https://image.tmdb.org/t/p/{size}/{path}` |
| 数据源免费 | 非商业用途免费，需注册获取 API Key |

**配置**:

```json
{
  "media": {
    "discovery": {
      "source": "tmdb",
      "tmdb_api_key": "your_key",
      "language": "zh-CN",
      "region": "CN"
    }
  }
}
```

**命名规范** (路径建议引擎):

| 风格 | 路径格式 | 示例 |
|------|----------|------|
| categorized | `/{base}/{电影\|剧集}/{类型}/{标题} ({年份})` | `/媒体/电影/科幻/流浪地球2 (2023)` |
| simple | `/{base}/{电影\|剧集}/{标题} ({年份})` | `/媒体/电影/流浪地球2 (2023)` |
| english | `/{base}/{电影\|剧集}/{英文名} ({年份})` | `/媒体/电影/The Wandering Earth 2 (2023)` |

---

## 4. 技术架构

### 4.1 项目结构

```
quark-cli/
├── pyproject.toml
├── README.md
├── docs/
│   └── PRD.md
├── quark_cli/
│   ├── __init__.py          # 版本信息
│   ├── api.py               # QuarkAPI 客户端
│   ├── cli.py               # CLI 入口 (argparse)
│   ├── config.py            # 配置管理
│   ├── debug.py             # Debug 日志
│   ├── display.py           # 终端输出格式化
│   ├── search.py            # 搜索引擎聚合
│   ├── commands/
│   │   ├── helpers.py       # 共享辅助函数
│   │   ├── config_cmd.py    # config 命令
│   │   ├── account_cmd.py   # account 命令
│   │   ├── share_cmd.py     # share 命令
│   │   ├── search_cmd.py    # search 命令
│   │   ├── drive_cmd.py     # drive 命令
│   │   ├── task_cmd.py      # task 命令
│   │   └── media_cmd.py     # media 命令 (NEW)
│   └── media/               # 影视媒体抽象层 (NEW)
│       ├── __init__.py
│       ├── base.py          # MediaProvider 抽象基类
│       ├── registry.py      # Provider 注册表
│       ├── fnos/            # fnOS Provider
│       │   ├── __init__.py
│       │   ├── auth.py      # authx 签名
│       │   ├── config.py    # fnOS 配置
│       │   ├── client.py    # 同步 HTTP 客户端
│       │   └── provider.py  # MediaProvider 实现
│       └── discovery/       # 影视发现/元数据 (NEW v2.1)
│           ├── __init__.py
│           ├── base.py      # DiscoverySource 抽象基类
│           ├── tmdb.py      # TMDB API v3 实现
│           └── naming.py    # 搜索关键词+保存路径建议引擎
```

### 4.2 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | >=3.8 | 运行时 |
| requests | >=2.28.0 | HTTP 请求（夸克 API + fnOS API） |

> 注：不依赖 httpx / pydantic / typer / rich，保持最小依赖。

### 4.3 配置结构

配置统一存储在 `~/.quark-cli/config.json`，`media` 段管理影视中心：

```json
{
  "cookie": ["..."],
  "search_sources": { "pansou": "..." },
  "tasklist": [],
  "media": {
    "provider": "fnos",
    "fnos": {
      "host": "192.168.1.100",
      "port": 5666,
      "token": "...",
      "ssl": false,
      "api_key": "16CCEB3D-AB42-077D-36A1-F355324E4237",
      "timeout": 30
    }
  }
}
```

---

## 5. 非功能需求

### 5.1 性能
- 单次 API 请求超时 30 秒
- 分页查询自动合并（每页 50 条）
- 转存分批执行（每批 100 个）
- 影视搜索采用客户端侧过滤，按需全量扫描

### 5.2 安全
- Cookie / Token 存储在本地配置文件
- `config show` / `media config --show` 对敏感信息脱敏
- 删除操作需交互确认
- fnOS 通信使用 authx 签名防篡改

### 5.3 兼容性
- Python 3.8+
- macOS / Linux / Windows
- 纯 CLI，无 GUI 依赖
- 仅依赖 requests，无重型依赖

### 5.4 可扩展性
- 命令模块化，新增命令只需添加 `commands/xxx_cmd.py`
- Media Provider 抽象架构，新增 Provider 只需实现接口 + 注册
- Provider 注册表支持运行时注册
- 配置支持 ENV 覆盖

---

## 6. 里程碑

| 阶段 | 功能 | 状态 |
|------|------|------|
| v1.0 | 基础 CLI：config/account/share/drive/task | ✅ 已完成 |
| v1.1 | 搜索引擎聚合、debug 模式 | ✅ 已完成 |
| v2.0 | 影视媒体中心 (`media`) - fnOS Provider | ✅ 已完成 |
| v2.1 | 影视发现 (`media meta/discover`) - TMDB 数据源 | ✅ 已完成 |
| v2.2 | Emby Provider | 🔲 规划中 |
| v2.3 | Jellyfin Provider | 🔲 规划中 |
| v2.4 | 魔法正则/魔法变量完整支持 | 🔲 规划中 |
| v2.5 | 多账号签到支持 | 🔲 规划中 |
| v3.0 | 交互式 TUI 模式 | 🔲 规划中 |
