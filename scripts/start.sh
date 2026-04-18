#!/usr/bin/env bash
# ============================================================
# Quark CLI — 一键启动脚本
#
# 用法:
#   ./start.sh                   启动 Web 面板 (默认 9090)
#   ./start.sh --port 8080       自定义端口
#   ./start.sh cli               进入 CLI 模式
#   ./start.sh sync              执行一次文件同步
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# 自动激活虚拟环境
if [ -z "$VIRTUAL_ENV" ] && [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# 检查安装
if ! command -v quark-cli &>/dev/null; then
    echo "⚠ quark-cli 未安装，执行安装..."
    bash "$SCRIPT_DIR/install.sh"
    # 重新激活
    [ -d "$VENV_DIR" ] && source "$VENV_DIR/bin/activate"
fi

MODE="${1:-serve}"

case "$MODE" in
    serve|web|panel)
        shift 2>/dev/null || true
        echo ""
        echo "  🚀 启动 Quark CLI Web 面板"
        echo ""
        exec quark-cli serve "$@"
        ;;
    cli)
        shift
        exec quark-cli "$@"
        ;;
    sync)
        shift
        echo "  📁 执行文件同步..."
        exec quark-cli sync run "$@"
        ;;
    bot)
        shift
        echo "  🤖 启动飞书机器人..."
        exec quark-cli bot "$@"
        ;;
    *)
        # 透传所有参数
        exec quark-cli "$@"
        ;;
esac
