# 架构扩展指南

## 项目结构

```
quark-cli/
├── quark_cli/
│   ├── cli.py                      # CLI 入口与参数定义
│   ├── config.py                   # 配置管理
│   ├── client.py                   # 夸克网盘 API Client
│   ├── search.py                   # 网盘资源搜索引擎
│   ├── scheduler.py                # 定时任务调度器 + 飞书通知
│   ├── subscribe.py                # 订阅追剧
│   ├── history.py                  # 任务历史 (SQLite)
│   ├── keepalive.py                # Cookie 保活
│   ├── commands/                   # CLI 子命令处理模块
│   │   ├── media_cmd.py            # media 子命令
│   │   ├── sync_cmd.py             # sync 子命令
│   │   └── ...
│   ├── media/
│   │   ├── base.py                 # MediaProvider 抽象接口
│   │   ├── registry.py             # Provider 注册中心
│   │   ├── fnos/                   # fnOS Provider 实现
│   │   ├── discovery/
│   │   │   ├── base.py             # DiscoverySource 抽象接口
│   │   │   ├── tmdb.py             # TMDB 数据源
│   │   │   ├── douban.py           # 豆瓣数据源
│   │   │   ├── cache.py            # 缓存层 (TTLCache)
│   │   │   └── naming.py           # 命名建议 (搜索关键词/路径)
│   │   ├── sync.py                 # 文件同步引擎
│   │   └── autosave.py             # 自动搜索转存
│   └── web/
│       ├── app.py                  # FastAPI 应用工厂
│       ├── deps.py                 # 依赖注入 (配置/数据源/缓存)
│       └── routes/                 # API 路由模块
│           ├── account.py
│           ├── discovery.py
│           ├── media.py
│           ├── scheduler.py
│           ├── sync.py
│           └── ...
├── web/                            # React 前端 (Vite + Tailwind)
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   └── vite.config.js
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 添加新的 Media Provider

Media Provider 是影视媒体中心的抽象层，目前支持 fnOS，可扩展 Emby / Jellyfin 等。

### 1. 实现接口

创建 `quark_cli/media/<provider_name>/` 目录，实现 `MediaProvider`：

```python
# quark_cli/media/my_provider/provider.py
from quark_cli.media.base import MediaProvider, MediaItem, MediaLibrary, PagedResult

class MyProvider(MediaProvider):
    provider_name = "my_provider"

    def __init__(self, config):
        self.config = config

    def get_libraries(self) -> list[MediaLibrary]:
        ...

    def get_items(self, library_guid, page=1, page_size=20) -> PagedResult:
        ...

    def search_items(self, keyword, page=1, page_size=20) -> PagedResult:
        ...

    def get_item_detail(self, guid) -> MediaItem:
        ...

    # 更多方法见 base.py
```

### 2. 注册 Provider

```python
# quark_cli/media/registry.py
from quark_cli.media.my_provider.provider import MyProvider

PROVIDERS = {
    "fnos": ...,
    "my_provider": MyProvider,
}
```

### 3. 添加配置字段

在 `config.json` 的 `media` 段中添加对应配置。

## 添加新的 Discovery 数据源

Discovery 数据源提供影视元数据查询和推荐功能。

### 1. 实现接口

```python
# quark_cli/media/discovery/my_source.py
from quark_cli.media.discovery.base import DiscoverySource, DiscoveryItem, DiscoveryResult

class MySource(DiscoverySource):

    def search(self, query, media_type="movie", page=1, year=None) -> DiscoveryResult:
        ...

    def get_detail(self, source_id, media_type="movie") -> DiscoveryItem:
        ...

    def get_popular(self, media_type="movie", page=1) -> DiscoveryResult:
        ...

    def get_top_rated(self, media_type="movie", page=1) -> DiscoveryResult:
        ...

    def get_trending(self, media_type="movie", time_window="week") -> DiscoveryResult:
        ...

    def discover(self, media_type="movie", page=1, **filters) -> DiscoveryResult:
        ...

    def get_genres(self, media_type="movie") -> dict:
        ...

    def get_poster_url(self, path, size="w500") -> str:
        ...
```

### 2. 注册数据源

在 `quark_cli/web/deps.py` 中添加创建函数，在 `quark_cli/commands/media_cmd.py` 中注册 CLI 支持。

## 开发调试

```bash
# 激活 venv
source .venv/bin/activate

# debug 模式
quark-cli --debug media status

# 自定义配置（不影响主配置）
quark-cli -c /tmp/test.json config show

# pdb 断点调试
python -m pdb -m quark_cli.cli share check "https://pan.quark.cn/s/xxx"

# Web 面板热重载 (后端)
quark-cli serve --reload

# 前端开发服务器
cd web && npm run dev
```
