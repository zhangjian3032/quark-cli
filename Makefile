#!/usr/bin/env bash
# ============================================================
# Quark CLI — 打包脚本
#
# 用法:
#   make build           构建前端 + Python wheel
#   make dist            构建开箱即用 tar.gz 发行包
#   make docker          构建 Docker 镜像
#   make clean           清理构建产物
#
# 依赖:
#   Python ≥ 3.8, pip, Node.js ≥ 18, npm
# ============================================================

.PHONY: help build dist docker clean frontend wheel install dev test lint

SHELL  := /bin/bash
NAME   := quark-cli
VERSION := $(shell python3 -c "from quark_cli import __version__; print(__version__)")

# ── 默认 ──
help:
	@echo ""
	@echo "  $(NAME) v$(VERSION) — 构建工具"
	@echo ""
	@echo "  make build       构建前端 + Python wheel"
	@echo "  make dist        构建开箱即用 tar.gz (含前端+wheel+启动脚本)"
	@echo "  make docker      构建 Docker 镜像"
	@echo "  make install     pip install 本地开发版 (可编辑模式)"
	@echo "  make dev         安装开发依赖"
	@echo "  make test        运行测试"
	@echo "  make clean       清理构建产物"
	@echo ""

# ── 前端构建 ──
frontend:
	@echo "▸ 构建前端..."
	cd web && npm ci --no-audit --no-fund 2>/dev/null || cd web && npm install
	cd web && npm run build
	@echo "✓ 前端构建完成 → quark_cli/web/static/"

# ── Python wheel ──
wheel: frontend
	@echo "▸ 构建 Python wheel..."
	pip install --quiet build
	python3 -m build --wheel --outdir dist/
	@echo "✓ wheel → dist/"

# ── 完整构建 ──
build: wheel
	@echo "✓ 构建完成: $(NAME) v$(VERSION)"

# ── 开箱即用发行包 ──
dist: frontend
	@echo "▸ 打包开箱即用发行包..."
	$(eval DIST_DIR := dist/$(NAME)-$(VERSION))
	rm -rf $(DIST_DIR) dist/$(NAME)-$(VERSION).tar.gz

	mkdir -p $(DIST_DIR)

	# 核心 Python 包
	cp -r quark_cli $(DIST_DIR)/
	cp pyproject.toml $(DIST_DIR)/
	cp README.md $(DIST_DIR)/ 2>/dev/null || true
	cp LICENSE $(DIST_DIR)/ 2>/dev/null || true
	cp MANIFEST.in $(DIST_DIR)/

	# 前端构建产物已在 quark_cli/web/static/ 中

	# 启动脚本
	cp scripts/install.sh $(DIST_DIR)/
	cp scripts/start.sh $(DIST_DIR)/

	# 配置模板
	cp scripts/config.example.json $(DIST_DIR)/

	# Docker 支持
	cp Dockerfile $(DIST_DIR)/
	cp docker-compose.yml $(DIST_DIR)/

	# 打包
	cd dist && tar czf $(NAME)-$(VERSION).tar.gz $(NAME)-$(VERSION)/
	rm -rf $(DIST_DIR)

	@echo "✓ 发行包 → dist/$(NAME)-$(VERSION).tar.gz"
	@ls -lh dist/$(NAME)-$(VERSION).tar.gz

# ── Docker 镜像 ──
docker:
	@echo "▸ 构建 Docker 镜像..."
	docker build -t $(NAME):$(VERSION) -t $(NAME):latest .
	@echo "✓ Docker 镜像: $(NAME):$(VERSION)"

# ── 开发安装 ──
install:
	pip install -e ".[all]"
	@echo "✓ 已安装 (可编辑模式)"

dev:
	pip install -e ".[all,dev]"
	@echo "✓ 已安装 (开发模式)"

# ── 测试 ──
test:
	python3 -m pytest tests/ -v

# ── 清理 ──
clean:
	rm -rf dist/ build/ *.egg-info
	rm -rf quark_cli/web/static/
	rm -rf web/node_modules/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ 已清理"
