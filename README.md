# Quark CLI - 夸克网盘命令行工具

基于 [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 项目 API 封装的完整 CLI 工具。

## 功能特性

| 模块 | 功能 | 命令 |
|------|------|------|
| **配置管理** | Cookie 设置/查看/重置 | `quark-cli config` |
| **账号管理** | 账号信息/签到/空间查询 | `quark-cli account` |
| **分享链接** | 检查有效性/列出文件/转存 | `quark-cli share` |
| **网盘操作** | 列目录/创建目录/重命名/删除/搜索/下载 | `quark-cli drive` |
| **资源搜索** | 通过网盘搜索引擎搜索资源 | `quark-cli search` |
| **任务管理** | 自动转存任务的增删改查/批量执行 | `quark-cli task` |
| **影视中心** | fnOS/Emby/Jellyfin 媒体库管理 | `quark-cli media` |
| **影视发现** | TMDB 元数据查询/高分推荐/路径建议 | `quark-cli media meta/discover` |

## 安装

### 方式一：pip 直接安装

```bash
pip install .
```

### 方式二：venv 虚拟环境（推荐开发调试）

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
# macOS / Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# 可编辑模式安装（代码修改即时生效）
pip install -e ".[dev]"

# 验证安装
quark-cli --version

# 退出虚拟环境
deactivate
```

### 开发调试

```bash
# 激活 venv 后，直接运行入口模块（等价于 quark-cli 命令）
python -m quark_cli.cli --help

# 启用 DEBUG 模式（显示完整请求日志）
quark-cli --debug account info

# 使用自定义配置文件调试（不影响主配置）
quark-cli -c /tmp/test_config.json config show

# 使用 pdb 断点调试
python -m pdb -m quark_cli.cli share check "https://pan.quark.cn/s/xxxxx"
```

### 方式三：pipx 全局安装（隔离环境）

```bash
pipx install .
```

## 快速开始

### 1. 配置 Cookie

从浏览器获取夸克网盘的 Cookie，然后设置：

```bash
quark-cli config set-cookie "your_cookie_here"
```

### 2. 验证账号

```bash
quark-cli account verify
quark-cli account info
```

### 3. 每日签到

```bash
quark-cli account sign
```

### 4. 检查分享链接

```bash
quark-cli share check "https://pan.quark.cn/s/xxxxx"
```

### 5. 列出分享文件

```bash
quark-cli share list "https://pan.quark.cn/s/xxxxx"
quark-cli share list "https://pan.quark.cn/s/xxxxx" --tree
```

### 6. 转存文件

```bash
quark-cli share save "https://pan.quark.cn/s/xxxxx" /我的资源/电影
quark-cli share save "https://pan.quark.cn/s/xxxxx" /追更/剧集 --pattern "\.mp4$"
quark-cli share save "https://pan.quark.cn/s/xxxxx" /追更/剧集 --pattern "^(\d+)\.mp4" --replace "S02E\1.mp4"
```

### 7. 搜索网盘资源

```bash
# 通过 pansou 等搜索引擎搜索资源
quark-cli search query "流浪地球"
quark-cli search query "庆余年" --source pansou

# 先配置搜索源（可选，有默认值）
quark-cli config set-search-source mypansou "http://your-pansou-host:3032"
```

### 8. 网盘文件管理

```bash
quark-cli drive ls /                    # 列出根目录
quark-cli drive ls /我的资源             # 列出子目录
quark-cli drive mkdir /新文件夹          # 创建目录
quark-cli drive search "关键词"          # 搜索网盘内文件
quark-cli drive rename <fid> "新名字"   # 重命名
quark-cli drive download <fid>          # 获取下载链接
quark-cli drive delete <fid>            # 删除文件
```

### 9. 自动转存任务管理

```bash
# 查看任务
quark-cli task list

# 添加任务
quark-cli task add \
  --name "追更-某剧" \
  --url "https://pan.quark.cn/s/xxxxx" \
  --savepath "/追更/某剧" \
  --pattern '.*\.(mp4|mkv)$' \
  --enddate "2026-12-31" \
  --runweek "1,3,5"

# 执行全部任务
quark-cli task run

# 执行单个任务
quark-cli task run-one 1

# 移除任务
quark-cli task remove 1
```

### 10. 影视媒体中心

`media` 子命令集成了影视媒体中心管理功能，当前支持 **fnOS 飞牛影视**，架构预留 Emby / Jellyfin 扩展。

#### 10.1 登录 fnOS

```bash
quark-cli media login --host 192.168.1.100 --port 5666 -u admin -p your_password

# 支持 URL 格式的 host
quark-cli media login --host http://mynas.local:5666 -u admin
```

#### 10.2 检查连接状态

```bash
quark-cli media status
```

#### 10.3 媒体库管理

```bash
# 列出所有媒体库
quark-cli media lib list

# 查看某个媒体库的影片
quark-cli media lib show "电影"
quark-cli media lib show "电影" --page 2 --size 50
```

#### 10.4 搜索影片

```bash
quark-cli media search "流浪地球"
quark-cli media search "甄嬛" --page 1 --size 10
```

#### 10.5 影片详情

```bash
# 通过 GUID 查看
quark-cli media info 04d6155c8eb64df0bdd39623d006fb57

# 通过名称查看（自动搜索匹配）
quark-cli media info "流浪地球"

# 显示季列表和演职人员
quark-cli media info "甄嬛传" --seasons --cast
```

#### 10.6 下载海报

```bash
quark-cli media poster "流浪地球" -o ./posters
```

#### 10.7 导出影片列表

```bash
# 导出全部影片为 JSON
quark-cli media export -o my_library.json

# 导出指定媒体库为 CSV
quark-cli media export -o movies.csv -f csv -l "电影"
```

#### 10.8 继续观看

```bash
quark-cli media playing
```

#### 10.9 媒体配置管理

```bash
# 查看当前配置（token 脱敏）
quark-cli media config --show

# 切换 Provider（未来支持 emby / jellyfin）
quark-cli media config --provider fnos

# 修改服务器配置
quark-cli media config --host 192.168.1.200 --port 5666
```

#### 10.10 环境变量覆盖

| 变量 | 说明 | 示例 |
|------|------|------|
| `FNOS_HOST` | fnOS 服务器地址 | `192.168.1.100` |
| `FNOS_PORT` | fnOS 端口 | `5666` |
| `FNOS_TOKEN` | fnOS 认证 Token | `eyJ...` |
| `FNOS_SSL` | 启用 HTTPS | `true` |

### 11. 影视发现 (TMDB)

`media meta` 和 `media discover` 基于 TMDB (The Movie Database) API，提供影视元数据查询和高分推荐功能。

#### 11.1 配置 TMDB API Key

使用前需先配置 TMDB API Key（免费申请：https://www.themoviedb.org/settings/api）：

```bash
quark-cli media config --tmdb-key "your_tmdb_api_key_v3"

# 可选: 修改语言（默认 zh-CN）
quark-cli media config --tmdb-lang en-US
```

#### 11.2 查询影视元数据 (meta)

通过关键词搜索、TMDB ID 或 IMDb ID 获取完整元数据，同时生成搜索关键词建议和保存路径建议：

```bash
# 按名称搜索
quark-cli media meta "流浪地球2"
quark-cli media meta "Breaking Bad" -t tv

# 按 TMDB ID 直接获取
quark-cli media meta --tmdb 634649

# 按 IMDb ID 查找
quark-cli media meta --imdb tt12093860

# 指定年份过滤
quark-cli media meta "蜘蛛侠" -y 2021

# 自定义保存路径基准
quark-cli media meta "流浪地球2" --base-path /我的NAS/媒体

# JSON 输出
quark-cli --json media meta "流浪地球2"
```

输出内容包括：
- 基本信息：标题、年份、评分、类型、片长、状态
- 主创信息：导演、主演
- 剧情简介
- **搜索关键词建议**：中文名、英文名及其年份组合
- **保存路径建议**：按类型分类、简洁、英文命名三种风格
- 海报和背景图 URL

#### 11.3 高分影视推荐 (discover)

```bash
# 高分电影 (默认)
quark-cli media discover

# 热门电影
quark-cli media discover --list popular

# 本周趋势
quark-cli media discover --list trending --window week

# 高分剧集
quark-cli media discover -t tv --list top_rated

# 高级筛选: 8分以上的科幻动作片
quark-cli media discover --list discover --min-rating 8.0 --genre "科幻,动作"

# 筛选指定年份和地区
quark-cli media discover --list discover -y 2025 --country CN

# 翻页
quark-cli media discover --list top_rated -p 2

# JSON 输出
quark-cli --json media discover --list popular -t movie
```

支持的列表类型：

| 类型 | 说明 | 参数 |
|------|------|------|
| `top_rated` | 高分排行（默认） | `-p` 页码 |
| `popular` | 热门排行 | `-p` 页码 |
| `trending` | 趋势 | `--window day/week` |
| `discover` | 高级筛选 | `--min-rating` `--genre` `-y` `--country` `--sort-by` |

支持的筛选参数（仅 `discover` 模式）：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--min-rating` | 最低评分 | `8.0` |
| `--genre` | 类型（中文或 ID） | `动作,科幻` 或 `28,878` |
| `-y/--year` | 年份 | `2025` |
| `--country` | 国家/地区代码 | `CN`, `US`, `JP` |
| `--sort-by` | 排序方式 | `vote_average.desc`, `popularity.desc` |
| `--min-votes` | 最低票数（默认 50） | `100` |

#### 11.4 典型工作流

```bash
# 1. 发现高分电影
quark-cli media discover --list top_rated

# 2. 查看某部电影的详细元数据和搜索关键词
quark-cli media meta --tmdb 278

# 3. 用建议的关键词搜索网盘资源
quark-cli search query "肖申克的救赎"

# 4. 转存到建议的路径
quark-cli share save "https://pan.quark.cn/s/xxxxx" "/媒体/电影/剧情/肖申克的救赎 (1994)"
```

## 配置文件

默认位置：`~/.quark-cli/config.json`

可通过 `-c` 参数指定：

```bash
quark-cli -c /path/to/config.json account info
```

### 配置结构

```json
{
  "cookie": ["your_cookie_here"],
  "search_sources": {
    "pansou": "https://www.pansou.com"
  },
  "push_config": {},
  "magic_regex": {
    "$TV": { "pattern": "...", "replace": "..." }
  },
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
    },
    "discovery": {
      "source": "tmdb",
      "tmdb_api_key": "your_tmdb_v3_api_key",
      "language": "zh-CN",
      "region": "CN"
    }
  }
}
```

## Debug 模式

全局 `--debug` 开关会打印所有 API 请求/响应详情到 stderr，同时适用于夸克 API 和影视中心 API：

```bash
quark-cli --debug media status
quark-cli --debug share check "https://pan.quark.cn/s/xxxxx"
```

## JSON 输出模式

全局 `--json` 开关让所有命令以 JSON 格式输出，便于脚本集成：

```bash
quark-cli --json media meta "流浪地球2"
quark-cli --json media discover --list popular
quark-cli --json account info
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QUARK_DEBUG` | 启用调试日志 | 未设置 |
| `QUARK_CONFIG` | 配置文件路径 | `~/.quark-cli/config.json` |
| `QUARK_COOKIE` | Cookie（优先于配置文件） | 未设置 |
| `FNOS_HOST` | fnOS 服务器地址 | 未设置 |
| `FNOS_PORT` | fnOS 端口 | `5666` |
| `FNOS_TOKEN` | fnOS Token | 未设置 |
| `FNOS_SSL` | fnOS HTTPS | `false` |

## Cookie 获取方法

1. 打开浏览器，登录 [夸克网盘](https://pan.quark.cn)
2. 按 F12 打开开发者工具
3. 切到 Network (网络) 标签
4. 刷新页面，点击任一请求
5. 在 Request Headers 中复制 `Cookie` 的值

> **完整签到功能**需要从夸克 APP 抓取包含 `kps`/`sign`/`vcode` 参数的 Cookie

## 正则处理示例

| pattern | replace | 效果 |
|---------|---------|------|
| `.*` | | 转存所有文件 |
| `\.mp4$` | | 只转存 .mp4 文件 |
| `^【XX】(.*)\.mp4` | `\1.mp4` | 去掉前缀广告 |
| `^(\d+)\.mp4` | `S02E\1.mp4` | 01.mp4 → S02E01.mp4 |

## 架构扩展指南

### 添加新的 Media Provider

1. 创建 `quark_cli/media/<provider_name>/` 目录
2. 实现 `MediaProvider` 抽象接口（见 `quark_cli/media/base.py`）
3. 在 `quark_cli/media/registry.py` 注册 Provider
4. 在配置 `media` 段添加对应配置字段

### 添加新的 Discovery 数据源

1. 创建 `quark_cli/media/discovery/<source_name>.py`
2. 实现 `DiscoverySource` 抽象接口（见 `quark_cli/media/discovery/base.py`）
3. 在 `media_cmd.py` 中添加对应数据源创建逻辑

## 开源协议

基于 [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) 协议开源。

参考项目：[quark-auto-save](https://github.com/Cp0204/quark-auto-save)
