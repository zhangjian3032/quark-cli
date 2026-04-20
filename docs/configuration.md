# 配置说明

配置文件默认路径：`~/.quark-cli/config.json`（Docker 中为 `/root/.quark-cli/config.json`）。

可通过 `-c` 参数或 `QUARK_CONFIG` 环境变量指定自定义路径。

## 完整配置示例

```json
{
  "cookie": "your_quark_cookie_here",

  "push_config": {},

  "magic_regex": {
    "$TV": { "pattern": "...", "replace": "..." }
  },

  "tasklist": [
    {
      "taskname": "流浪地球",
      "shareurl": "https://pan.quark.cn/s/xxxxx",
      "savepath": "/媒体/电影/流浪地球2 (2023)",
      "pattern": ".*\\.mp4$",
      "replace": "",
      "enabled": true,
      "source": "tmdb"
    }
  ],

  "media": {
    "provider": "fnos",
    "fnos": {
      "host": "192.168.1.100",
      "port": 5666,
      "token": "xxx",
      "ssl": false,
      "api_key": "16CCEB3D-AB42-077D-36A1-F355324E4237",
      "timeout": 30
    },
    "discovery": {
      "source": "tmdb",
      "tmdb_api_key": "your_tmdb_v3_api_key",
      "language": "zh-CN",
      "region": "CN",
      "cache": {
        "enabled": true,
        "list_ttl": 1800,
        "detail_ttl": 7200,
        "search_ttl": 900,
        "static_ttl": 86400,
        "max_entries": 500
      }
    }
  },

  "sync": {
    "schedule_enabled": false,
    "schedule_interval_minutes": 60,
    "bot_notify": false,
    "exclude_patterns": ["*.nfo", "*.txt", "Thumbs.db"],
    "tasks": [
      {
        "name": "电影同步",
        "source": "/mnt/alist/夸克/媒体/电影",
        "dest": "/mnt/nas/media/电影",
        "delete_after_sync": false,
        "enabled": true
      },
      {
        "name": "剧集同步",
        "source": "/mnt/alist/夸克/媒体/剧集",
        "dest": "/mnt/nas/media/剧集",
        "delete_after_sync": true,
        "enabled": true
      }
    ]
  },

  "bot": {
    "feishu": {
      "app_id": "cli_xxx",
      "app_secret": "xxx",
      "notify_open_id": "ou_xxx",
      "api_base": "https://open.feishu.cn"
    }
  },

  "keepalive": {
    "enabled": true,
    "interval_minutes": 60,
    "auto_sign": true
  },

  "torrent_clients": {
    "default": "qb1",
    "qbittorrent": [
      {
        "id": "qb1",
        "name": "NAS qBittorrent",
        "host": "192.168.1.100",
        "port": 8080,
        "username": "admin",
        "password": "your_password",
        "use_https": false,
        "default_save_path": "/downloads/rss",
        "default_category": "RSS",
        "default_tags": ["quark-cli", "rss"]
      }
    ],
    "_reserved": {
      "transmission": "Transmission RPC — 如有需求请反馈开发",
      "aria2": "aria2 JSON-RPC — 如有需求请反馈开发"
    }
  }
}
```

## 字段说明

### 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `cookie` | string | 夸克网盘 Cookie |
| `push_config` | object | 推送配置（预留） |
| `magic_regex` | object | 预定义正则变量 |
| `tasklist` | array | 自动转存任务列表 |

### media — 影视中心

| 字段 | 说明 |
|------|------|
| `provider` | 媒体中心类型：`fnos` / `emby` / `jellyfin` |
| `fnos` | fnOS 连接配置 |
| `discovery.source` | 默认数据源：`tmdb` / `douban` |
| `discovery.tmdb_api_key` | TMDB API v3 Key |
| `discovery.language` | TMDB 语言（默认 `zh-CN`） |
| `discovery.region` | TMDB 地区（默认 `CN`） |
| `discovery.cache` | 发现缓存配置 |

### discovery.cache — 缓存配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `true` | 是否启用缓存 |
| `list_ttl` | int | `1800` | 列表缓存 TTL（秒） |
| `detail_ttl` | int | `7200` | 详情缓存 TTL（秒） |
| `search_ttl` | int | `900` | 搜索缓存 TTL（秒） |
| `static_ttl` | int | `86400` | 静态数据缓存 TTL（秒） |
| `max_entries` | int | `500` | 最大缓存条目数 |

### sync — 文件同步

| 字段 | 说明 |
|------|------|
| `schedule_enabled` | 是否启用定时同步 |
| `schedule_interval_minutes` | 同步间隔（分钟，最小 5） |
| `bot_notify` | 同步完成后飞书通知 |
| `exclude_patterns` | 排除文件模式列表 |
| `tasks[]` | 同步任务列表 |
| `tasks[].name` | 任务名称 |
| `tasks[].source` | 源目录（WebDAV 挂载路径） |
| `tasks[].dest` | 目标目录（NAS 本地路径） |
| `tasks[].delete_after_sync` | 同步后删除源文件 |
| `tasks[].enabled` | 是否启用 |

### bot.feishu — 飞书机器人

| 字段 | 说明 |
|------|------|
| `app_id` | 飞书 App ID |
| `app_secret` | 飞书 App Secret |
| `notify_open_id` | 通知目标用户 open_id |
| `api_base` | API 地址（默认 `https://open.feishu.cn`） |

### keepalive — Cookie 保活

| 字段 | 说明 |
|------|------|
| `enabled` | 是否启用 |
| `interval_minutes` | 检查间隔（分钟） |
| `auto_sign` | 自动签到 |

### torrent_clients — Torrent 下载客户端

| 字段 | 说明 |
|------|------|
| `default` | 默认客户端 ID |
| `qbittorrent[]` | qBittorrent 实例列表 |
| `_reserved` | 预留客户端（Transmission / aria2，尚未实现） |

#### qbittorrent[] — qBittorrent 实例

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 客户端唯一 ID |
| `name` | string | 显示名称 |
| `host` | string | Web UI 地址 |
| `port` | int | 端口（默认 8080） |
| `username` | string | 用户名（默认 admin） |
| `password` | string | 密码 |
| `use_https` | bool | 是否使用 HTTPS |
| `default_save_path` | string | 默认下载路径 |
| `default_category` | string | 默认分类 |
| `default_tags` | array | 默认标签列表 |

> **预留客户端**：`_reserved` 字段中列出了计划支持但尚未实现的客户端。如有需求可在 Issue 中反馈，实现后只需在 `torrent_client.py` 中新增 Client 类即可。

## 环境变量覆盖

以下环境变量优先于配置文件：

| 变量 | 覆盖字段 |
|------|----------|
| `QUARK_COOKIE` | `cookie` |
| `QUARK_CONFIG` | 配置文件路径 |
| `FNOS_HOST` | `media.fnos.host` |
| `FNOS_PORT` | `media.fnos.port` |
| `FNOS_TOKEN` | `media.fnos.token` |
| `FNOS_SSL` | `media.fnos.ssl` |
| `FEISHU_APP_ID` | `bot.feishu.app_id` |
| `FEISHU_APP_SECRET` | `bot.feishu.app_secret` |
| `FEISHU_NOTIFY_OPEN_ID` | `bot.feishu.notify_open_id` |
