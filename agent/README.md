# Quark Drive Agent

可直接部署的 AI Agent 技能包，兼容主流 Agent 框架。

## 架构

```
agent/
├── agent.json      # Agent manifest（工具定义、触发规则、配置声明）
├── main.py         # Agent 入口（工具实现、Schema 导出、独立运行）
└── README.md       # 本文件
```

## 兼容性

| 框架 | 集成方式 |
|------|----------|
| **OpenAI Codex / Assistants** | `agent.get_openai_tools()` 导出 function calling schema |
| **Anthropic Claude Tool Use** | `agent.get_anthropic_tools()` 导出 tool_use schema |
| **LangChain / LangGraph** | `agent.call(name, params)` 作为 `StructuredTool` |
| **AutoGPT / MetaGPT** | 读取 `agent.json` manifest |
| **Dify / Coze** | 通过 `agent.json` 的 tools 定义导入 |
| **自定义 Agent** | 直接实例化 `QuarkDriveAgent` 调用 |

## 快速集成

### 1. OpenAI Function Calling

```python
import openai
from agent.main import QuarkDriveAgent

agent = QuarkDriveAgent()
tools = agent.get_openai_tools()

response = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "帮我签到夸克网盘"}],
    tools=tools,
)

# 处理 tool_calls
for call in response.choices[0].message.tool_calls:
    result = agent.call(call.function.name, json.loads(call.function.arguments))
    print(result)
```

### 2. Anthropic Claude Tool Use

```python
import anthropic
from agent.main import QuarkDriveAgent

agent = QuarkDriveAgent()
tools = agent.get_anthropic_tools()

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "检查这个链接 https://pan.quark.cn/s/xxx"}],
)

for block in response.content:
    if block.type == "tool_use":
        result = agent.call(block.name, block.input)
        print(result)
```

### 3. LangChain StructuredTool

```python
from langchain.tools import StructuredTool
from agent.main import QuarkDriveAgent

agent = QuarkDriveAgent()

tools = [
    StructuredTool.from_function(
        func=lambda **kw: agent.call("quark_sign", kw),
        name="quark_sign",
        description="夸克网盘每日签到",
    ),
    StructuredTool.from_function(
        func=lambda url, **kw: agent.call("quark_share_check", {"url": url}),
        name="quark_share_check",
        description="检查夸克分享链接是否有效",
    ),
    # ... 更多工具
]
```

### 4. 独立运行

```bash
# 列出所有工具
python agent/main.py --list-tools

# 导出 OpenAI schema
python agent/main.py --openai-schema > openai_tools.json

# 导出 Anthropic schema
python agent/main.py --anthropic-schema > anthropic_tools.json

# 直接调用工具
python agent/main.py quark_sign
python agent/main.py quark_share_check --params '{"url": "https://pan.quark.cn/s/xxx"}'
python agent/main.py quark_resource_search --params '{"keyword": "流浪地球"}'
```

### 5. Crontab 自动化

```bash
# 每天 8 点签到
0 8 * * * python /path/to/agent/main.py quark_sign >> /var/log/quark.log 2>&1

# 每天 8/18/20 点执行转存
0 8,18,20 * * * python /path/to/agent/main.py quark_task_run >> /var/log/quark.log 2>&1
```

## 配置

通过环境变量配置（推荐用于容器/CI 部署）：

```bash
export QUARK_COOKIE="your_cookie_here"
export PANSOU_BASE_URL="https://www.pansou.com"
```

或通过 CLI 配置：

```bash
quark-cli config set-cookie "your_cookie_here"
```

## 工具清单

| Tool | 描述 | 必填参数 |
|------|------|----------|
| `quark_sign` | 每日签到 | - |
| `quark_account_info` | 账号信息 | - |
| `quark_share_check` | 检查分享链接 | `url` |
| `quark_share_list` | 列出分享文件 | `url` |
| `quark_share_save` | 转存分享文件 | `url`, `savepath` |
| `quark_drive_ls` | 列出网盘目录 | - |
| `quark_drive_search` | 搜索网盘文件 | `keyword` |
| `quark_resource_search` | 搜索网盘资源 | `keyword` |
| `quark_task_list` | 查看任务列表 | - |
| `quark_task_run` | 执行全部任务 | - |
