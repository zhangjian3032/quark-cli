# Quark CLI - 产品需求文档 (PRD)

## 1. 产品概述

### 1.1 产品名称
**Quark CLI** - 夸克网盘命令行工具

### 1.2 产品定位
基于 [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 项目的 API 封装，提供纯 CLI 交互体验，面向具备技术背景的用户，支持在终端/脚本/CI 环境中管理夸克网盘。

### 1.3 目标用户
| 用户画像 | 使用场景 |
|----------|----------|
| 开发者/技术爱好者 | 在服务器上通过命令行管理网盘、定时执行转存 |
| NAS/HTPC 用户 | 自动追更资源、配合 Emby/Jellyfin 使用 |
| 脚本自动化用户 | 在 crontab/CI 中批量管理转存任务 |
| 命令行偏好用户 | 不依赖 Docker/WebUI，轻量化使用 |

### 1.4 核心价值
- **零部署成本**：`pip install` 即用，无需 Docker/WebUI
- **脚本友好**：所有操作均为命令行参数，可嵌入 cron/CI
- **功能完整**：覆盖签到、分享检查、转存、文件管理、任务调度
- **配置持久化**：`~/.quark-cli/config.json` 统一管理

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
├── drive           # 网盘文件
│   ├── ls          # 列目录
│   ├── mkdir       # 创建目录
│   ├── rename      # 重命名
│   ├── download    # 下载链接
│   ├── delete      # 删除
│   └── search      # 搜索
└── task            # 任务管理
    ├── list        # 查看任务
    ├── add         # 添加任务
    ├── remove      # 删除任务
    ├── run         # 批量执行
    └── run-one     # 单任务执行
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

**技术要点**：
- `ls` 输出表格含图标、文件名、大小、FID、修改时间
- `delete` 需确认，`--permanent` 清空回收站
- `download` 返回带时效的下载链接和需携带的 Cookie

### 3.5 任务管理 (`task`)

| 子命令 | 描述 | 参数 |
|--------|------|------|
| `list` | 查看全部任务 | - |
| `add` | 添加任务 | `--name/--url/--savepath`（必选），`--pattern/--replace/--enddate/--runweek` |
| `remove` | 移除任务 | `<index>` 从 1 开始 |
| `run` | 执行全部任务 | - |
| `run-one` | 执行单个任务 | `<index>` |

**技术要点**：
- 任务支持结束日期和运行星期
- 执行时自动检查任务周期
- 记录失效分享避免重复请求
- 支持正则过滤和重命名
- 执行结果汇总统计

---

## 4. 技术架构

### 4.1 项目结构

```
quark-cli/
├── pyproject.toml           # 包配置
├── requirements.txt
├── README.md
├── quark_cli/
│   ├── __init__.py          # 版本信息
│   ├── api.py               # QuarkAPI 客户端
│   ├── cli.py               # CLI 入口 (argparse)
│   ├── config.py            # 配置管理
│   ├── display.py           # 终端输出格式化
│   └── commands/
│       ├── __init__.py
│       ├── helpers.py       # 共享辅助函数
│       ├── config_cmd.py    # config 命令
│       ├── account_cmd.py   # account 命令
│       ├── share_cmd.py     # share 命令
│       ├── drive_cmd.py     # drive 命令
│       └── task_cmd.py      # task 命令
```

### 4.2 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | >=3.8 | 运行时 |
| requests | >=2.28.0 | HTTP 请求 |

### 4.3 API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `pan.quark.cn/account/info` | GET | 账号信息 |
| `drive-m.quark.cn/.../growth/info` | GET | 签到信息 |
| `drive-m.quark.cn/.../growth/sign` | POST | 执行签到 |
| `drive-pc.quark.cn/.../share/sharepage/token` | POST | 获取 stoken |
| `drive-pc.quark.cn/.../share/sharepage/detail` | GET | 分享详情 |
| `drive-pc.quark.cn/.../share/sharepage/save` | POST | 转存 |
| `drive-pc.quark.cn/.../file/sort` | GET | 列目录 |
| `drive-pc.quark.cn/.../file` | POST | 创建目录 |
| `drive-pc.quark.cn/.../file/rename` | POST | 重命名 |
| `drive-pc.quark.cn/.../file/delete` | POST | 删除 |
| `drive-pc.quark.cn/.../file/download` | POST | 下载链接 |
| `drive-pc.quark.cn/.../file/info/path_list` | POST | 路径→FID |
| `drive-pc.quark.cn/.../task` | GET | 查询任务状态 |

---

## 5. 非功能需求

### 5.1 性能
- 单次 API 请求超时 30 秒
- 分页查询自动合并（每页 50 条）
- 转存分批执行（每批 100 个）

### 5.2 安全
- Cookie 存储在本地配置文件
- `config show` 对 Cookie 脱敏显示
- 删除操作需交互确认

### 5.3 兼容性
- Python 3.8+
- macOS / Linux / Windows
- 纯 CLI，无 GUI 依赖

### 5.4 可扩展性
- 命令模块化，新增命令只需添加 `commands/xxx_cmd.py`
- 配置支持 magic_regex 扩展正则
- API 客户端独立封装，可被其他项目引用

---

## 6. 里程碑

| 阶段 | 功能 | 状态 |
|------|------|------|
| v1.0 | 基础 CLI：config/account/share/drive/task | ✅ 已完成 |
| v1.1 | 魔法正则/魔法变量完整支持 | 🔲 规划中 |
| v1.2 | 多账号签到支持 | 🔲 规划中 |
| v1.3 | 通知推送集成 | 🔲 规划中 |
| v1.4 | 插件系统 (emby/aria2 等) | 🔲 规划中 |
| v2.0 | 交互式 TUI 模式 | 🔲 规划中 |
