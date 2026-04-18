#!/usr/bin/env bash
# ============================================================
# Quark CLI — 一键安装脚本
#
# 用法:
#   chmod +x install.sh && ./install.sh
#
# 功能:
#   1. 检查 Python ≥ 3.8
#   2. 创建 venv (可选)
#   3. pip install 含所有依赖
#   4. 验证安装
#   5. 初始化配置文件
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}▸${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
fail()    { echo -e "${RED}✗${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║      Quark CLI — 一键安装             ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── 检查 Python ──
info "检查 Python 版本..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ] 2>/dev/null; then
            PYTHON="$cmd"
            success "Python $ver ($cmd)"
            break
        fi
    fi
done

[ -z "$PYTHON" ] && fail "需要 Python ≥ 3.8，请先安装"

# ── 虚拟环境 ──
USE_VENV=true
VENV_DIR="$SCRIPT_DIR/.venv"

if [ -n "$VIRTUAL_ENV" ]; then
    info "检测到已激活的虚拟环境: $VIRTUAL_ENV"
    USE_VENV=false
elif [ "$1" = "--no-venv" ]; then
    info "跳过虚拟环境创建 (--no-venv)"
    USE_VENV=false
fi

if [ "$USE_VENV" = true ]; then
    if [ ! -d "$VENV_DIR" ]; then
        info "创建虚拟环境..."
        $PYTHON -m venv "$VENV_DIR"
        success "虚拟环境: $VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    PYTHON="python"
    success "已激活虚拟环境"
fi

# ── 安装依赖 ──
info "安装 Quark CLI + 所有依赖..."

cd "$SCRIPT_DIR"
$PYTHON -m pip install --upgrade pip -q
$PYTHON -m pip install ".[all]" -q

success "依赖安装完成"

# ── 验证 ──
info "验证安装..."
VERSION=$(quark-cli --version 2>/dev/null || $PYTHON -m quark_cli.cli --version 2>/dev/null || echo "unknown")
success "quark-cli $VERSION"

# ── 初始化配置 ──
CONFIG_DIR="$HOME/.quark-cli"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    info "初始化配置文件..."
    mkdir -p "$CONFIG_DIR"
    if [ -f "$SCRIPT_DIR/config.example.json" ]; then
        cp "$SCRIPT_DIR/config.example.json" "$CONFIG_FILE"
    else
        quark-cli config show >/dev/null 2>&1 || true
    fi
    success "配置文件: $CONFIG_FILE"
else
    info "配置文件已存在: $CONFIG_FILE"
fi

# ── 完成 ──
echo ""
echo "  ════════════════════════════════════════"
echo ""
success "安装完成！"
echo ""

if [ "$USE_VENV" = true ]; then
    echo "  激活环境:  source $VENV_DIR/bin/activate"
fi

echo "  设置Cookie: quark-cli config set-cookie \"你的Cookie\""
echo "  启动面板:   quark-cli serve"
echo "  查看帮助:   quark-cli --help"
echo ""

if [ -f "$SCRIPT_DIR/start.sh" ]; then
    echo "  快速启动:   ./start.sh"
fi

echo ""
