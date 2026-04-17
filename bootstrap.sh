#!/usr/bin/env bash
#
# bootstrap.sh — Quark CLI 一键安装部署脚本
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/zhangjian3032/quark-cli/main/bootstrap.sh | bash
#   # 或:
#   bash bootstrap.sh [选项]
#
# 选项:
#   --port PORT       Web 面板端口 (默认 9090)
#   --no-web          不安装 Web 面板依赖
#   --no-bot          不安装飞书 Bot 依赖
#   --dev             安装开发依赖 + 前端构建
#   --systemd         安装为 systemd 服务
#   --docker          生成 Docker 部署文件
#   --cn              使用国内镜像源
#   --config PATH     指定配置文件路径
#   --cookie COOKIE   初始化 Cookie
#   --help            显示帮助
#
set -euo pipefail

GITHUB_REPO="https://github.com/zhangjian3032/quark-cli.git"
GITHUB_RAW="https://raw.githubusercontent.com/zhangjian3032/quark-cli/main"

# ════════════════════════════════════════════════════════════════
# 颜色 & 输出
# ════════════════════════════════════════════════════════════════
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${CYAN}${BOLD}▸ $*${NC}"; }

banner() {
    echo -e "${CYAN}"
    cat << 'BANNER'
   ____                   _       ____ _     ___
  / __ \ _   _  __ _ _ __| | __  / ___| |   |_ _|
 | |  | | | | |/ _` | '__| |/ / | |   | |    | |
 | |__| | |_| | (_| | |  |   <  | |___| |___ | |
  \___\_\\__,_|\__,_|_|  |_|\_\  \____|_____|___|

  夸克网盘 CLI · 一键部署
BANNER
    echo -e "${NC}"
}

# ════════════════════════════════════════════════════════════════
# 默认参数
# ════════════════════════════════════════════════════════════════
PORT=9090
INSTALL_WEB=true
INSTALL_BOT=true
DEV_MODE=false
INSTALL_SYSTEMD=false
GENERATE_DOCKER=false
USE_CN_MIRROR=false
CONFIG_PATH=""
INITIAL_COOKIE=""
INSTALL_DIR=""

# ════════════════════════════════════════════════════════════════
# 参数解析
# ════════════════════════════════════════════════════════════════
show_help() {
    cat << 'EOF'
用法: bash bootstrap.sh [选项]

选项:
  --port PORT       Web 面板端口 (默认 9090)
  --no-web          不安装 Web 面板依赖
  --no-bot          不安装飞书 Bot 依赖
  --dev             安装开发依赖 + 前端构建环境
  --systemd         安装为 systemd 服务
  --docker          生成 Docker Compose 部署文件
  --cn              使用国内镜像源 (pip + npm)
  --config PATH     指定配置文件路径
  --cookie COOKIE   初始化 Cookie (quark_sess=xxx)
  --install-dir DIR 安装目录 (默认 ~/quark-cli)
  --help            显示此帮助

示例:
  # 最简一行安装
  curl -fsSL https://raw.githubusercontent.com/zhangjian3032/quark-cli/main/bootstrap.sh | bash

  # 完整安装 + systemd 服务
  bash bootstrap.sh --systemd --cookie "your_cookie_here"

  # 国内镜像 + 自定义端口
  bash bootstrap.sh --cn --port 8080

  # 生成 Docker 部署文件
  bash bootstrap.sh --docker
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)       PORT="$2"; shift 2 ;;
        --no-web)     INSTALL_WEB=false; shift ;;
        --no-bot)     INSTALL_BOT=false; shift ;;
        --dev)        DEV_MODE=true; shift ;;
        --systemd)    INSTALL_SYSTEMD=true; shift ;;
        --docker)     GENERATE_DOCKER=true; shift ;;
        --cn)         USE_CN_MIRROR=true; shift ;;
        --config)     CONFIG_PATH="$2"; shift 2 ;;
        --cookie)     INITIAL_COOKIE="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --help|-h)    show_help; exit 0 ;;
        *)            error "未知选项: $1"; show_help; exit 1 ;;
    esac
done

# ════════════════════════════════════════════════════════════════
# 环境检测
# ════════════════════════════════════════════════════════════════
banner

step "检测系统环境"

OS="$(uname -s)"
ARCH="$(uname -m)"
info "系统: $OS $ARCH"

# Python 检测
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        if [[ -n "$PY_VER" ]]; then
            MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 8 ]]; then
                PYTHON="$cmd"
                break
            fi
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    error "需要 Python >= 3.8，未检测到合适版本"
    info "安装方法:"
    case "$OS" in
        Linux)
            if command -v apt-get &>/dev/null; then
                info "  sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv"
            elif command -v dnf &>/dev/null; then
                info "  sudo dnf install -y python3 python3-pip"
            elif command -v yum &>/dev/null; then
                info "  sudo yum install -y python3 python3-pip"
            elif command -v apk &>/dev/null; then
                info "  apk add python3 py3-pip"
            fi
            ;;
        Darwin)
            info "  brew install python@3.11"
            ;;
    esac
    exit 1
fi

PY_VERSION=$("$PYTHON" --version 2>&1)
success "Python: $PY_VERSION ($PYTHON)"

# pip 检测
if ! "$PYTHON" -m pip --version &>/dev/null; then
    warn "pip 未找到，尝试安装..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-pip
    else
        curl -fsSL https://bootstrap.pypa.io/get-pip.py | "$PYTHON"
    fi
fi
success "pip: $("$PYTHON" -m pip --version 2>&1 | head -1)"

# Node.js 检测 (仅 dev 模式或需要构建前端)
HAS_NODE=false
if command -v node &>/dev/null && command -v npm &>/dev/null; then
    NODE_VER="$(node --version)"
    success "Node.js: $NODE_VER"
    HAS_NODE=true
else
    if $DEV_MODE; then
        warn "Node.js 未检测到 (开发模式需要)"
        info "安装: https://nodejs.org 或 nvm install --lts"
    fi
fi

# Git 检测
HAS_GIT=false
if command -v git &>/dev/null; then
    success "Git: $(git --version)"
    HAS_GIT=true
else
    warn "Git 未找到，将尝试其他安装方式"
fi

# ════════════════════════════════════════════════════════════════
# 国内镜像设置
# ════════════════════════════════════════════════════════════════
PIP_EXTRA_ARGS=""
if $USE_CN_MIRROR; then
    step "配置国内镜像源"
    PIP_EXTRA_ARGS="-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn"
    success "pip 镜像: 清华 TUNA"

    # 国内 GitHub 加速
    GITHUB_REPO="https://ghproxy.com/https://github.com/zhangjian3032/quark-cli.git"
    info "GitHub 加速: ghproxy"

    if $HAS_NODE; then
        npm config set registry https://registry.npmmirror.com
        success "npm 镜像: npmmirror"
    fi
fi

# ════════════════════════════════════════════════════════════════
# 获取源码
# ════════════════════════════════════════════════════════════════
step "获取源码"

# 优先检测: 脚本所在目录或当前目录是否就是项目源码
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
LOCAL_PROJECT=""
if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    LOCAL_PROJECT="$SCRIPT_DIR"
elif [[ -f "./pyproject.toml" ]]; then
    LOCAL_PROJECT="$(pwd)"
fi

if [[ -n "$LOCAL_PROJECT" ]]; then
    # ── 本地项目目录，直接使用 ──
    if [[ -z "$INSTALL_DIR" ]]; then
        INSTALL_DIR="$LOCAL_PROJECT"
    fi
    cd "$INSTALL_DIR"
    success "使用本地源码: $INSTALL_DIR"
else
    # ── 需要从远程获取 ──
    if [[ -z "$INSTALL_DIR" ]]; then
        INSTALL_DIR="$HOME/quark-cli"
    fi

    if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
        # 已有安装目录
        info "检测到已有安装: $INSTALL_DIR"
        cd "$INSTALL_DIR"
        if [[ -d ".git" ]] && $HAS_GIT; then
            info "执行 git pull 更新..."
            git pull --rebase 2>/dev/null || warn "git pull 失败，继续使用当前版本"
            success "源码已更新"
        else
            info "使用现有源码"
        fi
    elif $HAS_GIT; then
        # Git clone
        info "从 GitHub 克隆源码..."
        if [[ -d "$INSTALL_DIR" ]]; then
            # 目录存在但不是项目，备份后 clone
            warn "目标目录已存在: $INSTALL_DIR"
            if [[ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
                # 空目录，直接 clone 进去
                rmdir "$INSTALL_DIR"
            else
                BACKUP="${INSTALL_DIR}.bak.$(date +%s)"
                warn "备份到: $BACKUP"
                mv "$INSTALL_DIR" "$BACKUP"
            fi
        fi
        git clone --depth 1 "$GITHUB_REPO" "$INSTALL_DIR" 2>&1
        cd "$INSTALL_DIR"
        success "源码已克隆: $INSTALL_DIR"
    else
        # 无 Git，下载 tarball
        info "Git 不可用，下载源码压缩包..."
        TARBALL_URL="https://github.com/zhangjian3032/quark-cli/archive/refs/heads/main.tar.gz"
        if $USE_CN_MIRROR; then
            TARBALL_URL="https://ghproxy.com/$TARBALL_URL"
        fi
        mkdir -p "$INSTALL_DIR"
        curl -fsSL "$TARBALL_URL" | tar xz --strip-components=1 -C "$INSTALL_DIR" || {
            error "源码下载失败，请检查网络连接"
            info "手动下载: https://github.com/zhangjian3032/quark-cli"
            exit 1
        }
        cd "$INSTALL_DIR"
        success "源码已下载: $INSTALL_DIR"
    fi
fi

# 验证源码
if [[ ! -f "pyproject.toml" ]]; then
    error "安装目录中未找到 pyproject.toml，源码不完整"
    exit 1
fi

success "安装目录: $INSTALL_DIR"

# ════════════════════════════════════════════════════════════════
# 创建虚拟环境
# ════════════════════════════════════════════════════════════════
step "创建 Python 虚拟环境"

VENV_DIR="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON" -m venv "$VENV_DIR"
    success "虚拟环境已创建: $VENV_DIR"
else
    info "虚拟环境已存在，跳过创建"
fi

# 激活虚拟环境
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
success "已激活虚拟环境 ($(python --version))"

# 升级 pip
python -m pip install --upgrade pip $PIP_EXTRA_ARGS --quiet

# ════════════════════════════════════════════════════════════════
# 安装 quark-cli
# ════════════════════════════════════════════════════════════════
step "安装 quark-cli"

# 确定安装 extras
EXTRAS=""
if $INSTALL_WEB && $INSTALL_BOT; then
    EXTRAS="all"
elif $INSTALL_WEB; then
    EXTRAS="web"
elif $INSTALL_BOT; then
    EXTRAS="bot"
fi

if $DEV_MODE; then
    if [[ -n "$EXTRAS" ]]; then
        EXTRAS="$EXTRAS,dev"
    else
        EXTRAS="dev"
    fi
fi

# 从源码 editable 安装
if [[ -n "$EXTRAS" ]]; then
    pip install -e ".[$EXTRAS]" $PIP_EXTRA_ARGS --quiet
else
    pip install -e . $PIP_EXTRA_ARGS --quiet
fi
success "安装完成 (editable mode)"

# 验证安装
if command -v quark-cli &>/dev/null; then
    success "quark-cli 已可用: $(which quark-cli)"
else
    QUARK_BIN="$VENV_DIR/bin/quark-cli"
    if [[ -f "$QUARK_BIN" ]]; then
        success "quark-cli 已安装: $QUARK_BIN"
    else
        warn "quark-cli 命令未找到，可能需要刷新 PATH"
    fi
fi

# ════════════════════════════════════════════════════════════════
# 构建前端 (如果有源码且需要)
# ════════════════════════════════════════════════════════════════
STATIC_DIR="$INSTALL_DIR/quark_cli/web/static"
WEB_SRC="$INSTALL_DIR/web"

if $INSTALL_WEB && [[ -d "$WEB_SRC" ]]; then
    if [[ ! -d "$STATIC_DIR/assets" ]] || $DEV_MODE; then
        step "构建前端资源"
        if $HAS_NODE; then
            cd "$WEB_SRC"
            npm install --quiet 2>/dev/null
            npm run build
            cd "$INSTALL_DIR"
            success "前端构建完成"
        else
            warn "Node.js 未安装，无法构建前端"
            warn "请手动执行: cd $WEB_SRC && npm install && npm run build"
        fi
    else
        info "前端资源已存在，跳过构建 (--dev 强制重新构建)"
    fi
fi

# ════════════════════════════════════════════════════════════════
# 初始化配置
# ════════════════════════════════════════════════════════════════
step "初始化配置"

CONFIG_DIR="$HOME/.quark-cli"
if [[ -n "$CONFIG_PATH" ]]; then
    CONFIG_FILE="$CONFIG_PATH"
    CONFIG_DIR="$(dirname "$CONFIG_FILE")"
else
    CONFIG_FILE="$CONFIG_DIR/config.json"
fi

mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
    cat > "$CONFIG_FILE" << 'DEFAULTCONFIG'
{
  "cookie": [],
  "push_config": {},
  "search_sources": {
    "pansou": "https://www.pansou.com"
  },
  "media": {
    "provider": "fnos",
    "fnos": {
      "host": "",
      "port": 9096,
      "username": "",
      "password": ""
    },
    "discovery": {
      "tmdb_api_key": "",
      "language": "zh-CN",
      "region": "CN"
    }
  },
  "bot": {
    "feishu": {
      "app_id": "",
      "app_secret": "",
      "notify_open_id": "",
      "api_base": ""
    }
  },
  "scheduler": {
    "tasks": []
  }
}
DEFAULTCONFIG
    success "配置文件已创建: $CONFIG_FILE"
else
    info "配置文件已存在: $CONFIG_FILE"
fi

# 初始化 Cookie
if [[ -n "$INITIAL_COOKIE" ]]; then
    python -c "
import json, sys
cfg_path = '$CONFIG_FILE'
with open(cfg_path, 'r') as f:
    cfg = json.load(f)
cookie = '$INITIAL_COOKIE'
if cookie not in cfg.get('cookie', []):
    cfg.setdefault('cookie', []).append(cookie)
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print('Cookie 已写入配置')
else:
    print('Cookie 已存在，跳过')
"
fi

# ════════════════════════════════════════════════════════════════
# 生成启动脚本
# ════════════════════════════════════════════════════════════════
step "生成启动脚本"

LAUNCHER="$INSTALL_DIR/start.sh"
cat > "$LAUNCHER" << STARTSCRIPT
#!/usr/bin/env bash
# Quark CLI 启动脚本
set -euo pipefail

SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
VENV_DIR="\$SCRIPT_DIR/.venv"
PORT=\${1:-$PORT}

# 激活虚拟环境
source "\$VENV_DIR/bin/activate"

echo "════════════════════════════════════════"
echo " Quark CLI Web Panel"
echo " http://127.0.0.1:\$PORT"
echo "════════════════════════════════════════"

exec quark-cli serve --port "\$PORT" --host 0.0.0.0
STARTSCRIPT
chmod +x "$LAUNCHER"
success "启动脚本: $LAUNCHER"

# 停止脚本
STOPPER="$INSTALL_DIR/stop.sh"
cat > "$STOPPER" << 'STOPSCRIPT'
#!/usr/bin/env bash
# 停止 Quark CLI 服务
PID=$(pgrep -f "quark-cli serve" || true)
if [[ -n "$PID" ]]; then
    kill "$PID"
    echo "Quark CLI 已停止 (PID: $PID)"
else
    echo "Quark CLI 未运行"
fi
STOPSCRIPT
chmod +x "$STOPPER"
success "停止脚本: $STOPPER"

# ════════════════════════════════════════════════════════════════
# systemd 服务 (可选)
# ════════════════════════════════════════════════════════════════
if $INSTALL_SYSTEMD; then
    step "安装 systemd 服务"

    SERVICE_FILE="/etc/systemd/system/quark-cli.service"
    CURRENT_USER="$(whoami)"

    if [[ "$CURRENT_USER" == "root" ]] || command -v sudo &>/dev/null; then
        SERVICE_CONTENT="[Unit]
Description=Quark CLI Web Panel
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/quark-cli serve --port $PORT --host 0.0.0.0 --no-open
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target"

        if [[ "$CURRENT_USER" == "root" ]]; then
            echo "$SERVICE_CONTENT" > "$SERVICE_FILE"
        else
            echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null
        fi

        if [[ "$CURRENT_USER" == "root" ]]; then
            systemctl daemon-reload
            systemctl enable quark-cli
        else
            sudo systemctl daemon-reload
            sudo systemctl enable quark-cli
        fi

        success "systemd 服务已安装"
        info "管理命令:"
        info "  sudo systemctl start quark-cli    # 启动"
        info "  sudo systemctl stop quark-cli     # 停止"
        info "  sudo systemctl restart quark-cli  # 重启"
        info "  sudo systemctl status quark-cli   # 状态"
        info "  journalctl -u quark-cli -f        # 日志"
    else
        warn "需要 root 权限安装 systemd 服务"
        info "手动安装: sudo cp quark-cli.service /etc/systemd/system/"
    fi
fi

# ════════════════════════════════════════════════════════════════
# Docker Compose (可选)
# ════════════════════════════════════════════════════════════════
if $GENERATE_DOCKER; then
    step "生成 Docker 部署文件"

    # Dockerfile
    cat > "$INSTALL_DIR/Dockerfile" << 'DOCKERFILE'
FROM python:3.11-slim AS base

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git && \
    rm -rf /var/lib/apt/lists/*

# 前端构建 (可选, 如果有 Node.js)
FROM node:20-slim AS frontend
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --quiet
COPY web/ .
RUN npm run build

# 最终镜像
FROM base
COPY pyproject.toml .
COPY quark_cli/ quark_cli/
RUN pip install --no-cache-dir ".[all]"

# 复制前端构建产物
COPY --from=frontend /app/web/../quark_cli/web/static/ quark_cli/web/static/

# 配置目录
RUN mkdir -p /root/.quark-cli
VOLUME /root/.quark-cli

EXPOSE 9090

ENV PYTHONUNBUFFERED=1

CMD ["quark-cli", "serve", "--port", "9090", "--host", "0.0.0.0", "--no-open"]
DOCKERFILE
    success "Dockerfile 已生成"

    # docker-compose.yml
    cat > "$INSTALL_DIR/docker-compose.yml" << COMPOSE
version: "3.8"

services:
  quark-cli:
    build: .
    container_name: quark-cli
    restart: unless-stopped
    ports:
      - "${PORT}:9090"
    volumes:
      - quark-config:/root/.quark-cli
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/api/account/info"]
      interval: 60s
      timeout: 10s
      retries: 3

volumes:
  quark-config:
COMPOSE
    success "docker-compose.yml 已生成"

    info "Docker 部署:"
    info "  cd $INSTALL_DIR"
    info "  docker compose up -d       # 启动"
    info "  docker compose logs -f     # 日志"
    info "  docker compose down        # 停止"
fi

# ════════════════════════════════════════════════════════════════
# 添加 PATH
# ════════════════════════════════════════════════════════════════
step "配置环境变量"

SHELL_RC=""
case "${SHELL:-/bin/bash}" in
    */zsh)  SHELL_RC="$HOME/.zshrc" ;;
    */bash) SHELL_RC="$HOME/.bashrc" ;;
    */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
esac

PATH_LINE="export PATH=\"$VENV_DIR/bin:\$PATH\""

if [[ -n "$SHELL_RC" && -f "$SHELL_RC" ]]; then
    if ! grep -q "quark-cli" "$SHELL_RC" 2>/dev/null; then
        {
            echo ""
            echo "# Quark CLI"
            echo "$PATH_LINE"
        } >> "$SHELL_RC"
        success "PATH 已添加到 $SHELL_RC"
        info "执行 source $SHELL_RC 或重新打开终端生效"
    else
        info "PATH 配置已存在"
    fi
else
    warn "无法自动配置 PATH，请手动添加:"
    info "  $PATH_LINE"
fi

# ════════════════════════════════════════════════════════════════
# 完成
# ════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓ Quark CLI 安装完成!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}安装目录${NC}   $INSTALL_DIR"
echo -e "  ${BOLD}配置文件${NC}   $CONFIG_FILE"
echo -e "  ${BOLD}虚拟环境${NC}   $VENV_DIR"
echo ""
echo -e "  ${BOLD}快速开始:${NC}"
echo ""

if [[ -z "$INITIAL_COOKIE" ]]; then
    echo -e "  ${YELLOW}1. 设置 Cookie (必须):${NC}"
    echo -e "     quark-cli config set-cookie \"your_quark_sess_cookie\""
    echo ""
    echo -e "  ${YELLOW}2. 启动 Web 面板:${NC}"
else
    echo -e "  ${YELLOW}1. 启动 Web 面板:${NC}"
fi

echo -e "     $LAUNCHER"
echo -e "     # 或: quark-cli serve --port $PORT"
echo ""

if $INSTALL_WEB; then
    echo -e "  ${YELLOW}Web 面板:${NC}  http://127.0.0.1:$PORT"
    echo -e "  ${YELLOW}API 文档:${NC}  http://127.0.0.1:$PORT/api/docs"
    echo ""
fi

echo -e "  ${BOLD}常用命令:${NC}"
echo -e "     quark-cli checkin                # 每日签到"
echo -e "     quark-cli drive ls /             # 文件列表"
echo -e "     quark-cli search <关键词>         # 搜索资源"
echo -e "     quark-cli serve                  # 启动面板"
echo ""

if $INSTALL_SYSTEMD; then
    echo -e "  ${BOLD}systemd:${NC}"
    echo -e "     sudo systemctl start quark-cli   # 启动服务"
    echo ""
fi

if $GENERATE_DOCKER; then
    echo -e "  ${BOLD}Docker:${NC}"
    echo -e "     cd $INSTALL_DIR && docker compose up -d"
    echo ""
fi

echo -e "  ${CYAN}GitHub: https://github.com/zhangjian3032/quark-cli${NC}"
echo ""
