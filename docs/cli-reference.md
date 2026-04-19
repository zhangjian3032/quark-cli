# CLI 命令参考

## 全局选项

```
quark-cli [-c CONFIG] [--debug] [--json] <command>
```

| 选项 | 说明 |
|------|------|
| `-c, --config` | 指定配置文件路径（默认 `~/.quark-cli/config.json`） |
| `--debug` | 启用 debug 模式，打印所有 API 请求/响应 |
| `--json` | 所有命令以 JSON 格式输出 |
| `-v, --version` | 显示版本号 |

---

## config — 配置管理

```bash
quark-cli config set-cookie "cookie_value"   # 设置 Cookie
quark-cli config show                        # 查看当前配置
quark-cli config reset                       # 重置配置
```

---

## account — 账号管理

```bash
quark-cli account info       # 查看账号信息（昵称、会员、容量）
quark-cli account verify     # 验证 Cookie 有效性
quark-cli account sign       # 每日签到
```

---

## share — 分享链接

```bash
quark-cli share check <url>                     # 检查链接有效性
quark-cli share list <url>                       # 列出分享中的文件
quark-cli share save <url> /保存路径             # 转存到网盘
quark-cli share save <url> /路径 -p "\.mp4$"     # 正则过滤文件
quark-cli share save <url> /路径 -p "^广告(.*)" -r "\1"  # 正则重命名
```

| 选项 | 说明 |
|------|------|
| `-p, --pattern` | 文件名正则过滤（匹配的才转存） |
| `-r, --replace` | 正则替换表达式（重命名） |

---

## search — 资源搜索

```bash
quark-cli search query "关键词"              # 搜索网盘资源
quark-cli search query "关键词" -s funletu   # 指定搜索源
quark-cli search save "关键词" /保存路径     # 搜索并直接转存
quark-cli search sources                     # 列出可用搜索源
```

| 选项 | 说明 |
|------|------|
| `-s, --source` | 搜索源名称 |
| `-p, --page` | 页码 |

---

## drive — 网盘文件操作

```bash
quark-cli drive ls /路径                # 列出目录
quark-cli drive ls /路径 --size         # 显示文件大小
quark-cli drive mkdir /新目录           # 创建目录
quark-cli drive rename /路径 新名称     # 重命名
quark-cli drive rm /路径                # 删除文件/目录
quark-cli drive search "关键词"         # 搜索网盘文件
quark-cli drive download /路径          # 获取下载链接
```

---

## task — 定时任务管理

```bash
quark-cli task list                    # 查看所有任务
quark-cli task add                     # 交互式添加任务
quark-cli task remove <index>          # 删除任务
quark-cli task run                     # 立即执行所有任务
quark-cli task run --index 0           # 执行指定任务
```

---

## media — 影视中心

### 媒体库管理

```bash
quark-cli media login --host <ip> -u <user>    # 登录 (fnOS/Emby/Jellyfin)
quark-cli media status                          # 检查连接
quark-cli media config --show                   # 查看配置
quark-cli media config --tmdb-key <key>         # 设置 TMDB API Key
quark-cli media lib list                        # 媒体库列表
quark-cli media lib show <库名>                 # 库中影片列表
quark-cli media search "关键词"                 # 搜索影片
quark-cli media info <GUID>                     # 影片详情
quark-cli media poster <GUID> -o ./             # 下载海报
quark-cli media export -f json -o export.json   # 导出影片列表
quark-cli media playing                         # 继续观看列表
```

### 影视发现（TMDB / 豆瓣）

```bash
# TMDB 推荐
quark-cli media discover --list top_rated           # 高分电影
quark-cli media discover --list popular -t tv       # 热门剧集
quark-cli media discover --list trending            # 本周趋势
quark-cli media discover --list discover --genre "动作,科幻" --min-rating 7.5

# 豆瓣推荐
quark-cli media discover -s douban --list top_rated
quark-cli media discover -s douban --list discover --tag "科幻"
quark-cli media discover -s douban --list discover --tag "热门" --sort-by rank
```

| 选项 | 说明 |
|------|------|
| `-s, --source` | 数据源：`auto` / `tmdb` / `douban`（默认 auto） |
| `--list` | 列表类型：`popular` / `top_rated` / `trending` / `discover` |
| `-t, --type` | 类型：`movie` / `tv` |
| `-p, --page` | 页码 |
| `--genre` | 类型过滤（逗号分隔，如 `动作,科幻`） |
| `--tag` | 豆瓣标签（如 `热门`、`科幻`、`美剧`，仅豆瓣） |
| `--min-rating` | 最低评分 |
| `-y, --year` | 年份 |
| `--country` | 国家/地区代码（仅 TMDB） |
| `--sort-by` | 排序（TMDB: `vote_average.desc` / 豆瓣: `recommend` / `time` / `rank`） |
| `--window` | 趋势时间窗口：`day` / `week` |

### 元数据查询

```bash
quark-cli media meta "流浪地球2"                    # 自动搜索
quark-cli media meta --tmdb 906126                   # TMDB ID
quark-cli media meta --imdb tt21692408               # IMDb ID
quark-cli media meta --douban 35267208               # 豆瓣 ID
quark-cli media meta -s douban "霸王别姬"           # 指定豆瓣源搜索
```

| 选项 | 说明 |
|------|------|
| `-s, --source` | 数据源：`auto` / `tmdb` / `douban` |
| `--tmdb` | 直接指定 TMDB ID |
| `--imdb` | 直接指定 IMDb ID |
| `--douban` | 直接指定豆瓣 ID |
| `-t, --type` | 类型：`movie` / `tv` |
| `-y, --year` | 年份过滤 |
| `--base-path` | 保存路径基准目录（默认 `/媒体`） |

### 自动搜索转存

```bash
quark-cli media auto-save "流浪地球2"
quark-cli media auto-save "权力的游戏" -t tv --save-path "/媒体/剧集/权力的游戏"
quark-cli media auto-save "三体" --dry-run    # 仅搜索排序，不转存
```

---

## sync — 文件同步

```bash
quark-cli sync run                                          # 按配置执行同步
quark-cli sync run --source /mnt/alist --dest /mnt/nas      # 手动指定路径
quark-cli sync config --show                                # 查看同步配置
quark-cli sync status                                       # 同步状态
```

---

## bot — 飞书机器人

```bash
quark-cli bot                                              # 启动（从配置读取凭证）
quark-cli bot --app-id <id> --app-secret <secret>          # 指定凭证
quark-cli bot --base-path /媒体                            # 指定转存基准路径
```

---

## serve — Web 面板

```bash
quark-cli serve                       # 启动 (默认 0.0.0.0:9090)
quark-cli serve --port 8080           # 自定义端口
quark-cli serve --host 127.0.0.1      # 仅本地访问
quark-cli serve --reload              # 开发模式 (热重载)
quark-cli serve --no-open             # 不自动打开浏览器
```

---

## 正则处理示例

| pattern | replace | 效果 |
|---------|---------|------|
| `.*` | | 转存所有文件 |
| `\.mp4$` | | 只转存 .mp4 文件 |
| `^【XX】(.*)\.mp4` | `\1.mp4` | 去掉前缀广告 |
| `^(\d+)\.mp4` | `S02E\1.mp4` | 01.mp4 → S02E01.mp4 |
