# 安装部署

## 系统要求

- Python 3.9+
- Node.js 16+（仅从源码构建 Web 前端时需要）

## 方式一：pip 安装

```bash
# 基础安装 (CLI 功能)
pip install .

# 安装 Web 面板依赖
pip install ".[web]"

# 安装全部依赖 (Web + 飞书 Bot + 开发工具)
pip install ".[all]"
```

## 方式二：venv 虚拟环境（推荐）

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

pip install -e ".[all]"
quark-cli --version
```

## 方式三：pipx 全局安装

```bash
pipx install .
```

## 方式四：Docker

参见 [Docker 部署文档](docker.md)。

## 验证安装

```bash
quark-cli --version
quark-cli --help
```

## 构建 Web 前端（开发模式）

如果需要修改前端代码：

```bash
cd web
npm install
npm run dev      # 开发服务器 (Vite HMR)
npm run build    # 生产构建 → quark_cli/web/static/
```
