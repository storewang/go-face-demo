# Docker 部署文档

## 1. 概述

项目提供完整的 Docker 部署方案，通过 `docker-compose` 一键启动所有服务。

### 服务架构

```
                  ┌──────────────┐
                  │   浏览器     │
                  └──────┬───────┘
                         │ :80
                  ┌──────┴───────┐
                  │   Nginx      │  ← frontend 容器内
                  │  (前端静态    │
                  │   + 反向代理) │
                  └──┬───────┬───┘
                     │       │
         静态文件     │       │ /api/*  /ws/*
                     │  ┌────┴─────┐
                     │  │ Backend  │  ← backend 容器
                     │  │ Uvicorn  │
                     │  │ :8000    │
                     │  └────┬─────┘
                     │       │
                     │  ┌────┴──────────┐
                     │  │  SQLite       │
                     │  │  (Docker Volume)│
                     │  └───────────────┘
```

### 文件清单

| 文件 | 说明 |
|---|---|
| `docker-compose.yml` | 编排配置（backend + frontend） |
| `backend/Dockerfile` | 后端镜像构建 |
| `backend/.dockerignore` | 后端构建忽略规则 |
| `frontend/Dockerfile` | 前端镜像构建（多阶段：build + nginx） |
| `frontend/.dockerignore` | 前端构建忽略规则 |
| `frontend/nginx.conf` | 容器内 Nginx 配置（SPA 路由 + API 代理 + WebSocket） |

---

## 2. 前置要求

| 软件 | 最低版本 | 安装方式 |
|---|---|---|
| Docker | 20.10+ | [官方安装指南](https://docs.docker.com/engine/install/) |
| Docker Compose | 2.0+ | 随 Docker 一起安装（`docker compose`） |
| 磁盘空间 | 3 GB+ | 后端镜像约 1.5GB（含 dlib 编译） |

验证安装：

```bash
docker --version
docker compose version
```

---

## 3. 快速启动

### 3.1 一键部署

```bash
git clone git@github.com:storewang/go-face-demo.git
cd go-face-demo

docker compose up -d --build
```

首次构建需要 5-15 分钟（主要耗时在 dlib 编译）。

启动完成后访问：

| 地址 | 说明 |
|---|---|
| http://localhost | 前端页面 |
| http://localhost:8000/health | 后端健康检查 |
| http://localhost:8000/docs | Swagger API 文档 |

### 3.2 自定义配置

编辑 `docker-compose.yml` 中的 `environment` 部分修改配置：

```yaml
services:
  backend:
    environment:
      - ADMIN_PASSWORD=your_secure_password   # 修改管理员密码
      - DEBUG=false                            # 生产环境关闭调试
      - FACE_THRESHOLD=0.6                     # 人脸识别阈值
```

修改后重新启动：

```bash
docker compose up -d
```

> 环境变量变更不需要重新构建镜像，只需重启容器。

---

## 4. 配置详解

### 4.1 后端环境变量

在 `docker-compose.yml` 的 `backend.environment` 中配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ADMIN_PASSWORD` | `admin123` | 管理员登录密码 |
| `DEBUG` | `false` | 调试模式（热重载），生产环境设为 `false` |
| `DATABASE_URL` | `sqlite:///./data/face_scan.db` | 数据库路径 |
| `FACE_THRESHOLD` | `0.6` | 人脸识别置信度阈值（0.0-1.0） |
| `LIVENESS_FRAMES` | `5` | 活体检测帧数 |

### 4.2 前端构建参数

在 `docker-compose.yml` 的 `frontend.build.args` 中配置：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | 空（使用相对路径） | 后端 API 地址，留空则通过 Nginx 代理 |
| `VITE_WS_URL` | 空（使用相对路径） | WebSocket 地址，留空则通过 Nginx 代理 |

**默认配置（推荐）**：两个参数都留空，所有请求通过容器内 Nginx 代理转发，无需关心后端地址。

**独立部署场景**：前后端分别部署在不同服务器时，需要指定完整地址：

```yaml
frontend:
  build:
    args:
      - VITE_API_BASE_URL=https://api.your-domain.com
      - VITE_WS_URL=wss://api.your-domain.com/ws/face-stream
```

> 修改 build args 后需要重新构建：`docker compose up -d --build frontend`

### 4.3 数据持久化

Docker Compose 使用命名卷存储数据，容器重建后数据不会丢失：

| 卷名 | 容器内路径 | 内容 |
|---|---|---|
| `face-scan_backend-data` | `/app/data` | SQLite 数据库、人脸图片、特征文件、抓拍截图 |
| `face-scan_backend-models` | `/app/models` | 活体检测模型文件 |

查看卷：

```bash
docker volume ls | grep face-scan
```

查看卷数据：

```bash
docker volume inspect face-scan_backend-data
```

### 4.4 端口映射

| 容器端口 | 宿主机端口 | 服务 |
|---|---|---|
| 80 | 80 | 前端（Nginx） |
| 8000 | 8000 | 后端（Uvicorn，可选暴露） |

如需修改宿主机端口，编辑 `docker-compose.yml`：

```yaml
services:
  frontend:
    ports:
      - "8080:80"    # 改为 8080 端口访问

  backend:
    ports:
      - "9000:8000"  # 改为 9000 端口访问后端
```

---

## 5. 运维操作

### 5.1 常用命令

```bash
# 启动（后台运行）
docker compose up -d

# 启动（查看实时日志）
docker compose up

# 停止
docker compose down

# 停止并删除数据卷（危险！会清空所有数据）
docker compose down -v

# 重启
docker compose restart

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f

# 只看后端日志
docker compose logs -f backend

# 只看前端日志
docker compose logs -f frontend

# 重新构建并启动（代码更新后）
docker compose up -d --build
```

### 5.2 更新部署

```bash
cd go-face-demo

# 拉取最新代码
git pull origin main

# 重新构建并启动
docker compose up -d --build
```

### 5.3 数据备份

```bash
# 备份数据库和人脸数据
docker cp face-scan-backend:/app/data ./backup_$(date +%Y%m%d)

# 恢复数据
docker cp ./backup_20260406 face-scan-backend:/app/data
docker compose restart backend
```

使用 tar 打包备份：

```bash
# 备份
docker run --rm -v face-scan_backend-data:/data -v $(pwd):/backup alpine \
    tar czf /backup/face-scan-data-$(date +%Y%m%d).tar.gz -C /data .

# 恢复
docker run --rm -v face-scan_backend-data:/data -v $(pwd):/backup alpine \
    tar xzf /backup/face-scan-data-20260406.tar.gz -C /data
docker compose restart backend
```

### 5.4 活体检测模型（可选）

```bash
# 下载模型到持久化卷
docker run --rm -v face-scan_backend-models:/models alpine \
    sh -c "wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 -O /models/model.bz2 && bunzip2 /models/model.bz2 && mv /models/model /models/shape_predictor_68_face_landmarks.dat"

# 验证
docker exec face-scan-backend ls -la /app/models/

# 重启后端加载模型
docker compose restart backend
```

### 5.5 进入容器调试

```bash
# 进入后端容器
docker exec -it face-scan-backend bash

# 进入前端容器
docker exec -it face-scan-frontend sh

# 在后端容器内执行命令
docker exec face-scan-backend python -c "from app.services.face_service import face_service; print(f'Known faces: {len(face_service.known_encodings)}')"

# 查看后端容器内文件
docker exec face-scan-backend ls -la /app/data/faces/
```

### 5.6 健康检查

```bash
# 查看健康状态
docker compose ps

# 手动检查
curl http://localhost:8000/health
```

后端配置了健康检查（`docker-compose.yml` 中的 `healthcheck`），每 30 秒检查一次，连续 3 次失败会自动重启容器。

---

## 6. 生产环境优化

### 6.1 使用外部 Nginx + HTTPS

生产环境建议在 Docker 外部再套一层 Nginx，处理 HTTPS 和域名：

```
用户 → HTTPS (Nginx 宿主机) → :80 (Docker frontend)
                                        → /api/* → :8000 (Docker backend)
                                        → /ws/*  → :8000 (Docker backend)
```

宿主机 Nginx 配置 `/etc/nginx/sites-available/face-scan`：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### 6.2 限制资源使用

在 `docker-compose.yml` 中添加资源限制，防止 dlib 编译或人脸识别占用过多资源：

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
        reservations:
          memory: 512M
          cpus: "0.5"

  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"
```

### 6.3 日志管理

防止日志文件无限增长：

```yaml
services:
  backend:
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"

  frontend:
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "3"
```

### 6.4 使用 .env 文件管理配置

在项目根目录创建 `.env` 文件（与 `docker-compose.yml` 同级），Docker Compose 会自动加载：

```bash
# .env（项目根目录，不要提交到 Git）
ADMIN_PASSWORD=your_secure_password
DEBUG=false
FACE_THRESHOLD=0.6
FRONTEND_PORT=80
BACKEND_PORT=8000
```

`docker-compose.yml` 中引用变量：

```yaml
services:
  backend:
    environment:
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
      - DEBUG=${DEBUG:-false}
      - FACE_THRESHOLD=${FACE_THRESHOLD:-0.6}
    ports:
      - "${BACKEND_PORT:-8000}:8000"

  frontend:
    ports:
      - "${FRONTEND_PORT:-80}:80"
```

---

## 7. 镜像构建说明

### 7.1 后端镜像

**基础镜像**: `python:3.8-slim`

**构建步骤**:
1. 安装系统依赖（cmake, build-essential, libopencv-dev）
2. 安装 Python 依赖（含 dlib 从源码编译，约 5-10 分钟）
3. 复制应用代码
4. 创建数据目录
5. 启动时自动初始化数据库

**镜像大小**: 约 1.5 GB（dlib 编译产物较大）

### 7.2 前端镜像

**基础镜像**: 多阶段构建

| 阶段 | 镜像 | 用途 |
|---|---|---|
| build | `node:18-alpine` | 编译 Vue 项目 |
| production | `nginx:alpine` | 运行 Nginx 提供静态文件 |

**构建步骤**:
1. `npm ci` 安装依赖
2. `npm run build` 构建（支持 build args 注入环境变量）
3. 将构建产物复制到 nginx:alpine
4. 复制 Nginx 配置

**镜像大小**: 约 30 MB

### 7.3 加速构建

**后端镜像缓存**（dlib 编译最慢）：

```bash
# 单独构建后端镜像并缓存
docker compose build backend

# 后续构建会使用缓存层
docker compose up -d --build
```

**使用 BuildKit 加速**：

```bash
DOCKER_BUILDKIT=1 docker compose build
```

---

## 8. 常见问题

### Q: 后端构建失败，dlib 编译报错

```
通常原因是内存不足，dlib 编译需要至少 2GB 内存。

解决方案：
1. 增加 Docker 可用内存（Docker Desktop → Settings → Resources）
2. 使用 swap：
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
3. 在物理机上预编译后使用自定义基础镜像
```

### Q: 容器启动后前端页面空白

```
1. 检查前端构建是否成功：docker compose logs frontend
2. 确认 nginx.conf 已正确复制到镜像中
3. 检查 VITE_API_BASE_URL 是否正确（Docker 内部署应留空）
4. 进入容器检查文件：docker exec face-scan-frontend ls /usr/share/nginx/html
```

### Q: WebSocket 连接失败

```
1. 确认 Nginx 配置中 WebSocket 代理的 Upgrade 头已设置
2. 如果使用外部 Nginx，确保外部 Nginx 也配置了 WebSocket 代理
3. 检查防火墙是否放行 8000 端口（如果直接暴露后端）
```

### Q: 摄像头无法访问

```
Docker 容器默认无法访问宿主机 USB 设备。

如需在容器内使用摄像头（WebSocket 实时刷脸需要后端处理视频帧，
但实际摄像头是在浏览器端通过 getUserMedia 访问的，不需要后端直接访问摄像头）。

浏览器端摄像头访问：
1. 确保使用 HTTPS 或 localhost
2. 浏览器设置中允许摄像头权限
3. 摄像头被其他应用占用时需先关闭
```

### Q: 数据丢失了

```
1. 确认使用的是 docker compose down（保留数据卷），而非 docker compose down -v（删除数据卷）
2. 检查数据卷是否存在：docker volume ls | grep face-scan
3. 如果误删了数据卷，需要从备份恢复
```

### Q: 如何完全清理并重新开始

```bash
# 停止并删除所有容器、网络、卷
docker compose down -v

# 删除镜像
docker rmi go-face-demo-backend go-face-demo-frontend

# 重新构建启动
docker compose up -d --build
```

---

## 9. docker-compose.yml 完整参考

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: face-scan-backend
    restart: unless-stopped
    environment:
      - ADMIN_PASSWORD=admin123          # 管理员密码（必改）
      - DEBUG=false                      # 生产环境关闭
      - DATABASE_URL=sqlite:///./data/face_scan.db
      - FACE_THRESHOLD=0.6
    volumes:
      - backend-data:/app/data           # 数据持久化
      - backend-models:/app/models       # 模型持久化
    ports:
      - "8000:8000"                      # 后端 API 端口
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_BASE_URL=             # 留空使用 Nginx 代理
        - VITE_WS_URL=                   # 留空使用 Nginx 代理
    container_name: face-scan-frontend
    restart: unless-stopped
    ports:
      - "80:80"                          # 前端访问端口
    depends_on:
      backend:
        condition: service_healthy

volumes:
  backend-data:                          # 数据库 + 人脸图片
  backend-models:                        # 活体检测模型
```
