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
export QUARK_DEBUG=1
quark-cli account info

# 使用自定义配置文件调试（不影响主配置）
quark-cli -c /tmp/test_config.json config show

# 使用 pytest 运行测试（如有）
pytest tests/ -v

# 使用 pdb 断点调试
python -m pdb -m quark_cli.cli share check "https://pan.quark.cn/s/xxxxx"

# 查看调用栈追踪
python -c "
from quark_cli.api import QuarkAPI
client = QuarkAPI('test_cookie')
print(client.get_account_info())
"
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
quark-cli search "流浪地球"
quark-cli search "庆余年" --source pansou
quark-cli search "庆余年" --source funletu

# 先配置搜索源（可选，有默认值）
quark-cli config set-search-source "https://www.pansou.com"
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
    "pansou": "https://www.pansou.com",
    "funletu": "https://pan.funletu.com"
  },
  "push_config": {},
  "magic_regex": {
    "$TV": {
      "pattern": "...",
      "replace": "..."
    }
  },
  "tasklist": [
    {
      "taskname": "任务名",
      "shareurl": "https://pan.quark.cn/s/xxxxx",
      "savepath": "/保存路径",
      "pattern": ".*",
      "replace": "",
      "enddate": "2026-12-31",
      "runweek": [1, 3, 5]
    }
  ]
}
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QUARK_DEBUG` | 启用调试日志 | 未设置 |
| `QUARK_CONFIG` | 配置文件路径 | `~/.quark-cli/config.json` |
| `QUARK_COOKIE` | Cookie（优先于配置文件） | 未设置 |

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

## 开源协议

基于 [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) 协议开源。

参考项目：[quark-auto-save](https://github.com/Cp0204/quark-auto-save)
