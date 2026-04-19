# Web API 文档

Base URL: `http://your-host:9090/api`

Swagger 文档: `http://your-host:9090/api/docs`

---

## 账号与配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/account/info` | 账号信息（昵称、会员、容量） |
| GET | `/account/verify` | 验证 Cookie 有效性 |
| POST | `/account/sign` | 每日签到 |
| GET | `/config` | 获取脱敏配置 |
| PUT | `/config/cookie` | 设置 Cookie |
| DELETE | `/config/cookie` | 清除 Cookie |
| PUT | `/config/fnos` | 设置 fnOS 配置 |
| PUT | `/config/tmdb` | 设置 TMDB 配置 |
| GET | `/config/bot` | 获取飞书 Bot 配置 |
| PUT | `/config/bot` | 设置飞书 Bot 配置 |
| GET | `/config/export` | 导出完整配置 |
| POST | `/config/import` | 导入配置 |

## Cookie 保活

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/keepalive/status` | 保活状态 |
| POST | `/keepalive/toggle` | 启用/停用保活 |
| POST | `/keepalive/trigger` | 手动触发一次 |
| GET | `/keepalive/config` | 获取保活配置 |
| PUT | `/keepalive/config` | 更新保活配置 |

## 资源搜索与转存

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/search/query?q=关键词` | 搜索网盘资源 |
| GET | `/search/sources` | 可用搜索源列表 |
| GET | `/share/check?url=...` | 检查分享链接 |
| GET | `/share/list?url=...` | 列出分享文件 |
| GET | `/share/subdir?url=...&fid=...` | 浏览子目录 |
| POST | `/share/save` | 转存到网盘 |
| GET | `/rename/presets` | 正则重命名预设 |
| POST | `/rename/preview` | 预览重命名效果 |

## 网盘文件操作

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/drive/ls?path=/` | 列出目录 |
| POST | `/drive/mkdir` | 创建目录 |
| POST | `/drive/rename` | 重命名 |
| POST | `/drive/delete` | 删除文件/目录 |
| GET | `/drive/download?path=...` | 获取下载链接 |
| GET | `/drive/search?q=...` | 搜索网盘文件 |
| GET | `/drive/space` | 网盘空间信息 |

## 影视发现（TMDB / 豆瓣）

所有端点支持 `source=tmdb|douban` 查询参数。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/discovery/meta?name=...&type=movie` | 按名称查询元数据 |
| GET | `/discovery/meta/{item_id}?source=tmdb` | 按 ID 获取详情 |
| GET | `/discovery/list?list_type=top_rated&type=movie` | 推荐列表 |
| GET | `/discovery/genres?type=movie` | 类型列表 |
| GET | `/discovery/tags?type=movie&source=douban` | 豆瓣标签列表 |
| GET | `/discovery/sources` | 可用数据源列表（含缓存统计） |
| GET | `/discovery/cache/stats` | 缓存统计 |
| POST | `/discovery/cache/clear` | 清除缓存 |

### discovery/list 参数

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `list_type` | 列表类型 | `popular` / `top_rated` / `trending` / `discover` |
| `type` | 媒体类型 | `movie` / `tv` |
| `source` | 数据源 | `tmdb` / `douban` |
| `page` | 页码 | 整数 |
| `tag` | 豆瓣标签 | 字符串（仅 douban） |
| `genre` | TMDB 类型 ID | 字符串 |
| `sort_by` | 排序 | TMDB: `vote_average.desc` / 豆瓣: `recommend` / `time` / `rank` |

## 媒体库管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/media/status` | 媒体中心连接状态 |
| GET | `/media/libraries` | 媒体库列表 |
| GET | `/media/libraries/{lib_id}/items` | 库中影片列表 |
| GET | `/media/search?q=...` | 搜索影片 |
| GET | `/media/items/{guid}` | 影片详情 |
| GET | `/media/items/{guid}/poster` | 海报图片 |
| GET | `/media/img/{path}` | 图片代理 |
| GET | `/media/playing` | 继续观看列表 |

## 定时任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/scheduler/status` | 调度器状态 |
| GET | `/scheduler/tasks` | 任务列表 |
| POST | `/scheduler/tasks` | 添加任务 |
| PUT | `/scheduler/tasks/{index}` | 更新任务 |
| DELETE | `/scheduler/tasks/{index}` | 删除任务 |
| POST | `/scheduler/tasks/{index}/toggle` | 启用/停用任务 |
| POST | `/scheduler/tasks/{index}/trigger` | 手动触发 |
| POST | `/scheduler/start` | 启动调度器 |
| POST | `/scheduler/stop` | 停止调度器 |

## 订阅追剧

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/subscriptions` | 订阅列表 |
| POST | `/subscriptions` | 添加订阅 |
| PUT | `/subscriptions/{name}` | 更新订阅 |
| DELETE | `/subscriptions/{name}` | 删除订阅 |
| POST | `/subscriptions/{name}/check` | 手动检查更新 |
| POST | `/subscriptions/{name}/toggle` | 启用/停用 |
| POST | `/subscriptions/{name}/resume` | 恢复订阅 |
| GET | `/subscriptions/{name}/episodes` | 剧集列表 |
| POST | `/subscriptions/scheduler/start` | 启动订阅调度器 |
| POST | `/subscriptions/scheduler/stop` | 停止订阅调度器 |

## 文件同步

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sync/status` | 所有同步任务状态 |
| GET | `/sync/status/{name}` | 单个任务进度 |
| POST | `/sync/start` | 启动同步 |
| POST | `/sync/cancel/{name}` | 取消同步 |
| GET | `/sync/config` | 获取同步配置 |
| PUT | `/sync/config` | 更新同步配置 |
| GET | `/sync/progress/{name}` | SSE 实时进度流 |
| GET | `/sync/browse?path=/` | 浏览服务器目录 |

## 仪表盘与历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/dashboard` | 仪表盘统计数据 |
| GET | `/history?type=sync&limit=50` | 执行历史记录 |
| GET | `/history/stats?days=7` | 历史统计 |
| DELETE | `/history/cleanup?keep_days=90` | 清理旧记录 |
