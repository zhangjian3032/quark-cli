FROM python:3.11-slim AS builder

# 构建前端
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY web/package.json web/package-lock.json* ./web/
RUN cd web && npm ci --no-audit --no-fund
COPY web/ ./web/
COPY quark_cli/ ./quark_cli/
RUN cd web && npm run build

# ── 运行镜像 ──
FROM python:3.11-slim

LABEL maintainer="quark-cli"
LABEL description="夸克网盘 CLI + Web 管理面板"

WORKDIR /app

# 安装 Python 依赖
COPY pyproject.toml README.md ./
COPY quark_cli/ ./quark_cli/
RUN pip install --no-cache-dir ".[all]"

# 拷贝前端构建产物
COPY --from=builder /build/quark_cli/web/static/ ./quark_cli/web/static/

# 配置目录 (可挂载)
RUN mkdir -p /root/.quark-cli
VOLUME ["/root/.quark-cli"]

# WebDAV 挂载点 + NAS 存储 (可挂载)
VOLUME ["/mnt/alist"]
VOLUME ["/mnt/nas"]

ENV PYTHONUNBUFFERED=1

EXPOSE 9090

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:9090/api/health').raise_for_status()"

ENTRYPOINT ["quark-cli"]
CMD ["serve", "--host", "0.0.0.0", "--port", "9090", "--no-open"]
