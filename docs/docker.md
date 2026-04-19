# Docker 部署

## 快速启动

```bash
mkdir -p data/config
docker compose up -d
```

访问 `http://your-ip:9090` 进入 Web 面板。

## docker-compose.yml

```yaml
version: "3.8"

services:
  quark-cli:
    image: ghcr.io/zhangjian3032/quark-cli:main
    container_name: quark-cli
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      # 配置持久化 (config.json + 历史数据库)
      - ./data/config:/root/.quark-cli
      # WebDAV 挂载 (Alist 挂载的夸克网盘, 仅同步功能需要)
      # - /mnt/alist:/mnt/alist:ro
      # NAS 本地存储 (同步目标目录, 仅同步功能需要)
      # - /mnt/nas/media:/mnt/nas/media
    environment:
      - TZ=Asia/Shanghai
      # 可选: 飞书机器人通知
      # - FEISHU_APP_ID=cli_xxx
      # - FEISHU_APP_SECRET=xxx
      # - FEISHU_NOTIFY_OPEN_ID=ou_xxx
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:9090/api/health').raise_for_status()"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## 镜像来源

| 镜像 | 说明 |
|------|------|
| `ghcr.io/zhangjian3032/quark-cli:main` | GitHub CI 自动构建，跟随 main 分支 |

> 也可以本地构建：`docker build -t quark-cli .`

## 卷挂载说明

| 容器路径 | 宿主路径（示例） | 必需 | 说明 |
|----------|------------------|------|------|
| `/root/.quark-cli` | `./data/config` | ✅ | 配置文件和历史数据库持久化 |
| `/mnt/alist` | `/mnt/alist` | 可选 | WebDAV 挂载目录（文件同步源） |
| `/mnt/nas/media` | `/mnt/nas/media` | 可选 | NAS 本地存储（同步目标） |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TZ` | 时区 | `UTC` |
| `FEISHU_APP_ID` | 飞书 App ID | - |
| `FEISHU_APP_SECRET` | 飞书 App Secret | - |
| `FEISHU_NOTIFY_OPEN_ID` | 飞书通知目标用户 open_id | - |
| `QUARK_COOKIE` | Cookie（优先于配置文件） | - |

## 常用操作

```bash
# 查看日志
docker compose logs -f quark-cli

# 重启
docker compose restart

# 更新镜像
docker compose pull && docker compose up -d

# 进入容器执行 CLI 命令
docker exec -it quark-cli quark-cli account info

# 停止并删除
docker compose down
```

## 文件同步场景

如果你使用 Alist 将夸克网盘挂载为 WebDAV，需要额外配置挂载卷：

```yaml
volumes:
  - ./data/config:/root/.quark-cli
  - /mnt/alist:/mnt/alist:ro          # WebDAV 挂载 (只读)
  - /mnt/nas/media:/mnt/nas/media      # NAS 物理存储
```

然后在 Web 面板的「同步」页面配置源目录和目标目录。

## 本地构建

如果不想使用预构建镜像：

```yaml
services:
  quark-cli:
    build: .
    # 其余配置同上
```

```bash
docker compose build
docker compose up -d
```
