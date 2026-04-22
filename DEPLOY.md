# go-face-demo 部署构建文档

> **推荐部署**: Docker Compose 单机模式 (`docker-compose.deploy.yml`)
> 集群部署方案见 `deploy/cluster/` 目录
> 开发环境使用 `docker-compose.dev.yml` (支持代码热重载)

> 人脸识别考勤系统 — Docker Compose 部署指南
> 版本：v2.1.0 | 最后更新：2026-04-10

---

## 目录

1. [系统架构](#1-系统架构)
2. [环境要求](#2-环境要求)
3. [项目结构](#3-项目结构)
4. [部署步骤](#4-部署步骤)
5. [配置说明](#5-配置说明)
6. [构建优化（模型下载）](#6-构建优化模型下载)
7. [运维管理](#7-运维管理)
8. [扩展部署（HTTPS/Redis/PostgreSQL）](#8-扩展部署httpsredispostgresql)
9. [故障排除](#9-故障排除)

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────┐
│                  Docker Compose                 │
│                                                  │
│  ┌──────────────┐     ┌──────────────────────┐  │
│  │   Frontend   │     │      Backend         │  │
│  │  (Nginx:80)  │────▶│  (FastAPI:8000)      │  │
│  │  Vue 3 + TS  │ API │  InsightFace/ArcFace  │  │
│  │  Element Plus│ WS  │  OpenCV               │  │
│  │  └──────────────┘     │  SQLite / PostgreSQL  │  │
│                        │  Redis (可选)         │  │
│                        └──────────────────────┘  │
│                               │                   │
│                          ┌────┴────┐             │
│                          │  Volume │             │
│                          │ face-data│             │
│                          └─────────┘             │
└─────────────────────────────────────────────────┘
         │                          │
      :8080                      :8081
   (前端页面)               (API + WebSocket)
```

**技术栈：**
| 组件 | 技术 | 版本 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus | - |
| 构建工具 | Vite 5 | - |
| 后端 | FastAPI + Uvicorn | 0.109.2 / 0.27.1 |
| 人脸识别 | InsightFace/ArcFace + OpenCV | - |
| 图像处理 | OpenCV (headless) | 4.8.1 |
| 数据库 | SQLite（默认）/ PostgreSQL（可选） | - |
| 缓存 | Redis（可选，降级为无缓存） | 5.0.4 |
| 容器 | Docker + Docker Compose | - |


---

## 2. 环境要求

### 硬件要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| **内存** | **4GB** | **8GB+** |
| 磁盘 | 10GB | 20GB+（人脸图片+模型文件） |
| 网络 | 内网可通 | 公网可访问（可选 HTTPS） |

> ⚠️ **模型加载**：首次启动时会加载 InsightFace 模型，建议确保系统可用内存 ≥ 4GB。

### 软件要求

| 软件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Docker | 19.03 | 24.0+ |
| Docker Compose | 1.27 | 2.0+（V2） |
| Git | 2.0 | 最新 |

### 端口规划

| 端口 | 服务 | 说明 |
|------|------|------|
| 8080 | Frontend (Nginx) | Web 管理界面 |
| 8081 | Backend (FastAPI) | API + WebSocket |
| 6379 | Redis（可选） | 缓存服务 |
| 5432 | PostgreSQL（可选） | 数据库 |

---

## 3. 项目结构

```
go-face-demo/
├── docker-compose.yml          # 基础 Compose 文件
├── docker-compose.deploy.yml   # 生产部署 Compose 文件
├── docker-compose.dev.yml      # 开发热重载 Compose 文件
├── deploy/
│   └── cluster/                # 集群部署配置 (K8s/Swarm)
│       ├── docker-compose.cluster.yml
│       └── k8s/
├── backend/
│   ├── Dockerfile              # 后端镜像构建
│   ├── Dockerfile.test         # 测试镜像构建
│   ├── requirements.txt        # Python 依赖
│   ├── .env                    # 环境变量配置 ⚠️ 不要提交到 Git
│   ├── tests/
│   │   └── test_integration.py # 集成测试（67 个用例）
│   └── app/
│       ├── main.py             # FastAPI 入口
│       ├── config.py           # 配置管理（pydantic-settings）
│       ├── database.py         # 数据库连接（SQLite/PG 双支持）
│       ├── init_db.py          # 数据库初始化
│       ├── cache.py            # Redis 缓存（优雅降级）
│       ├── rate_limit.py       # 速率限制
│       ├── logging_config.py   # 结构化日志
│       ├── api/                # API 路由
│       │   ├── auth.py         # 登录/认证
│       │   ├── users.py        # 用户管理
│       │   ├── face.py         # 人脸注册/识别
│       │   ├── attendance.py   # 考勤记录
│       │   ├── devices.py      # 设备管理
│       │   ├── statistics.py   # 统计报表
│       │   ├── self_service.py # 用户自助服务
│       │   └── health.py       # 健康检查
│       ├── models/             # SQLAlchemy 模型
│       ├── schemas/            # Pydantic 模式
│       ├── services/           # 业务服务（face_service 等）
│       ├── websocket/          # WebSocket 处理
│       └── utils/              # 工具函数
└── frontend/
    ├── Dockerfile              # 前端镜像构建（多阶段）
    ├── nginx.conf              # Nginx 配置
    ├── vite.config.ts          # Vite 构建配置
    ├── package.json            # Node 依赖
    └── src/                    # Vue 源码
```

---

## 4. 部署步骤

### 4.1 克隆代码

```bash
git clone https://github.com/storewang/go-face-demo.git
cd go-face-demo
```

### 4.2 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`（必须修改的项用 ⚠️ 标注）：

```env
# ===== 数据库 =====
DATABASE_URL=sqlite:///./data/face_scan.db

# ===== 安全 ⚠️ 生产环境必须修改 =====
ADMIN_PASSWORD=your_strong_password_here    # ⚠️ 管理员密码
JWT_SECRET_KEY=your_random_secret_key_here  # ⚠️ JWT 密钥（随机字符串）

# ===== 人脸识别 =====
FACE_THRESHOLD=0.6     # 人脸比对阈值（越小越严格，范围 0.0-1.0）
# FACE_DETECTOR=ssd    # 检测器选择：默认(hog/cnn) | ssd

# ===== 跨域 =====
CORS_ORIGINS=["http://YOUR_SERVER_IP:8080"]

# ===== 调试 =====
DEBUG=false            # ⚠️ 生产环境设为 false
```

> **生成随机密钥：** `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

### 4.3 修改前端构建参数

编辑 `docker-compose.deploy.yml`，将构建参数中的 IP 替换为你的服务器地址：

```yaml
frontend:
  build:
    args:
      VITE_API_BASE_URL: http://YOUR_SERVER_IP:8081
      VITE_WS_URL: ws://YOUR_SERVER_IP:8081/ws/face-stream
```

### 4.4 构建并启动

```bash
# 方式一：直接构建（需要足够内存）
DOCKER_BUILDKIT=0 CMAKE_BUILD_PARALLEL_LEVEL=1 \
  docker-compose -f docker-compose.deploy.yml up -d --build

# 方式二：先构建镜像再启动（推荐，方便调试）
DOCKER_BUILDKIT=0 CMAKE_BUILD_PARALLEL_LEVEL=1 \
  docker-compose -f docker-compose.deploy.yml build
docker-compose -f docker-compose.deploy.yml up -d
```

> **首次构建约 20-40 分钟**（主要是 dlib C++ 编译），后续构建有缓存会快很多。

### 4.5 验证部署

```bash
# 检查容器状态
docker-compose -f docker-compose.deploy.yml ps

# 后端健康检查
curl http://localhost:8081/health

# 前端访问
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
```

预期 health 返回：
```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "healthy"},
    "face_service": {"status": "healthy", "known_faces": 0},
    "disk": {"status": "healthy"},
    "storage": {"status": "healthy"}
  }
}
```

### 4.6 访问系统

- **前端界面：** http://YOUR_SERVER_IP:8080
- **API 文档：** http://YOUR_SERVER_IP:8081/docs
- **管理员登录：** 用户名 `admin`，密码即 `.env` 中的 `ADMIN_PASSWORD`

---

## 5. 配置说明

### 5.1 环境变量完整列表

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./data/face_scan.db` | 数据库连接串 |
| `ADMIN_PASSWORD` | — | 管理员密码（首次启动自动哈希） |
| `ADMIN_PASSWORD_HASH` | — | 管理员密码哈希（与上面二选一） |
| `JWT_SECRET_KEY` | — | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 过期时间（分钟） |
| `FACE_THRESHOLD` | `0.6` | 人脸比对阈值 |
| `FACE_DETECTOR` | `default` | 检测器：`default`(HOG/CNN) / `ssd` |
| `CORS_ORIGINS` | — | 允许的跨域来源（JSON 数组） |
| `DEBUG` | `false` | 调试模式 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接（不可用时自动降级） |
| `STORAGE_TYPE` | `local` | 存储类型：`local` / `s3` |
| `S3_ENDPOINT` | — | MinIO/S3 端点 |
| `S3_ACCESS_KEY` | — | S3 访问密钥 |
| `S3_SECRET_KEY` | — | S3 密钥 |
| `S3_BUCKET` | `face-demo` | S3 桶名 |

### 5.2 角色权限

| 角色 | 说明 |
|------|------|
| `super_admin` | 超级管理员，全部权限 |
| `dept_admin` | 部门管理员，管理本部门用户和考勤 |
| `employee` | 普通员工，查看自己信息和考勤记录 |

### 5.3 主要 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/users/` | 用户列表 |
| POST | `/api/users/register` | 注册用户（含人脸） |
| DELETE | `/api/users/{id}` | 删除用户 |
| POST | `/api/face/recognize` | 人脸识别（单张） |
| WS | `/ws/face-stream` | 人脸识别流（摄像头实时） |
| GET | `/api/attendance/` | 考勤记录 |
| GET | `/api/devices/` | 设备列表 |
| POST | `/api/devices/heartbeat` | 设备心跳（无需认证） |
| GET | `/api/statistics/attendance` | 考勤统计 |
| GET | `/health` | 健康检查 |

完整 API 文档访问：`http://YOUR_SERVER_IP:8081/docs`

---

## 6. 构建优化（模型下载）

InsightFace 使用预训练模型，构建时会自动下载。如果服务器网络受限，建议手动下载并挂载。

### 6.1 手动下载模型

1. 从 InsightFace 官方仓库或镜像站下载 `buffalo_l` 模型包。
2. 解压到 `backend/app/models/insightface/models/buffalo_l/`。

### 6.2 镜像预热

在生产环境部署前，建议先在本地构建并推送到私有仓库，避免在生产服务器上进行耗时的构建操作。

```bash
# 本地构建
docker-compose -f docker-compose.deploy.yml build

# 导出镜像
docker save face-demo-backend:latest | gzip > backend.tar.gz
```


### 6.2 增加系统 Swap（内存不足时）

```bash
# 创建 4GB swap 文件
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 验证
free -h

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 6.3 跨机器构建（推荐）

在内存充足的机器上构建，导出后传到目标服务器：

```bash
# 在构建机上
cd go-face-demo
DOCKER_BUILDKIT=0 CMAKE_BUILD_PARALLEL_LEVEL=1 \
  docker-compose -f docker-compose.deploy.yml build

# 导出镜像
docker save face-demo-backend:latest face-demo-frontend:latest | gzip > face-demo-images.tar.gz

# 传到目标服务器
scp face-demo-images.tar.gz user@target-server:/home/dev/

# 在目标服务器上
docker load < face-demo-images.tar.gz

# 修改 docker-compose.deploy.yml 中的 build 为 image：
# backend:
#   image: face-demo-backend:latest
# frontend:
#   image: face-demo-frontend:latest
docker-compose -f docker-compose.deploy.yml up -d
```

### 6.4 预编译镜像方案

修改 `docker-compose.deploy.yml`，使用预构建镜像：

```yaml
services:
  backend:
    image: face-demo-backend:latest    # 替换 build 部分
    # build: ...                        # 注释掉
    container_name: face-backend
    # ...其余不变

  frontend:
    image: face-demo-frontend:latest    # 替换 build 部分
    # build: ...                        # 注释掉
    container_name: face-frontend
    # ...其余不变
```

---

## 7. 运维管理

### 7.1 日常操作

```bash
# 查看日志
docker-compose -f docker-compose.deploy.yml logs -f backend
docker-compose -f docker-compose.deploy.yml logs -f frontend

# 重启服务
docker-compose -f docker-compose.deploy.yml restart

# 停止服务
docker-compose -f docker-compose.deploy.yml down

# 更新代码并重新部署
cd go-face-demo
git pull origin main
scp -r backend/app/ user@server:/path/to/go-face-demo/backend/app/
scp backend/Dockerfile backend/requirements.txt user@server:/path/to/go-face-demo/backend/
ssh user@server "cd /path/to/go-face-demo && docker-compose -f docker-compose.deploy.yml up -d --build backend"
```

### 7.2 数据备份

```bash
# 备份数据卷
docker run --rm -v go-face-demo_face-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/face-data-backup-$(date +%Y%m%d).tar.gz /data

# 备份数据库文件（SQLite）
docker cp face-backend:/app/data/face_scan.db ./face_scan.db.bak
```

### 7.3 数据恢复

```bash
# 恢复数据卷
docker run --rm -v go-face-demo_face-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/face-data-backup-YYYYMMDD.tar.gz -C /
```

### 7.4 查看资源占用

```bash
docker stats face-backend face-frontend --no-stream
```

---

## 8. 扩展部署（HTTPS/Redis/PostgreSQL）

### 8.1 HTTPS（自签证书）

```bash
# 生成自签证书（10 年有效期）
mkdir -p ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout ssl/server.key -out ssl/server.crt \
  -subj "/CN=your-domain.com" \
  -addext "subjectAltName=DNS:your-domain.com,IP:YOUR_SERVER_IP"
```

在 `docker-compose.deploy.yml` 中添加 SSL 代理容器：

```yaml
  ssl-proxy:
    image: nginx:alpine
    container_name: face-ssl
    ports:
      - "443:443"
    volumes:
      - ./ssl/server.crt:/etc/nginx/ssl/server.crt:ro
      - ./ssl/server.key:/etc/nginx/ssl/server.key:ro
      - ./nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - frontend
    restart: unless-stopped
```

`nginx-ssl.conf`：
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;

    location / {
        proxy_pass http://face-frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

前端构建参数需要改为 HTTPS 地址：
```yaml
VITE_API_BASE_URL: https://your-domain.com
VITE_WS_URL: wss://your-domain.com/ws/face-stream
```

### 8.2 Redis（缓存加速）

在 `docker-compose.deploy.yml` 中添加：

```yaml
  redis:
    image: redis:7-alpine
    container_name: face-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped

volumes:
  face-data:
  redis-data:          # 新增
```

修改 `backend/.env`：
```env
REDIS_URL=redis://redis:6379/0    # Docker 内部 DNS
```

> 不部署 Redis 时，缓存会自动降级为无缓存模式，不影响功能。

### 8.3 PostgreSQL（替代 SQLite）

```yaml
  postgres:
    image: postgres:15-alpine
    container_name: face-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: face_demo
      POSTGRES_USER: face
      POSTGRES_PASSWORD: your_db_password
    volumes:
      - pg-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  face-data:
  pg-data:            # 新增
```

修改 `backend/.env`：
```env
DATABASE_URL=postgresql://face:your_db_password@postgres:5432/face_demo
```

> SQLite 数据可通过项目中的迁移脚本转为 PostgreSQL（见 `backend/scripts/migrate_sqlite_to_pg.py`）。

---

## 9. 故障排除

### 9.1 dlib 编译 OOM

**症状：** 构建过程中容器被 SIGKILL，日志中看到 `Building wheel for dlib` 后中断。

**解决：**
1. 增加系统 Swap（见 6.2）
2. 使用单线程编译：`CMAKE_BUILD_PARALLEL_LEVEL=1`
3. 停掉其他容器释放内存
4. 或在另一台机器构建后导出（见 6.3）

### 9.2 bcrypt $ 符号被 docker-compose 解析

**症状：** 管理员密码中包含 `$` 字符导致认证失败。

**解决：** 使用 `ADMIN_PASSWORD` 明文（系统会自动 bcrypt 哈希），不要使用 `ADMIN_PASSWORD_HASH`。

### 9.3 CORS_ORIGINS 格式错误

**症状：** 启动报错 `Input should be a valid list`。

**解决：** `.env` 中 CORS_ORIGINS 必须是 JSON 数组格式：
```env
CORS_ORIGINS=["http://192.168.1.100:8080","https://your-domain.com"]
```

### 9.4 face_service 报 "no such table"

**症状：** 启动日志中出现 `no such table: users` 警告。

**解决：** 正常现象，face_service 在模块加载时检查数据库，表会在 init_db 阶段创建。如果持续出现，检查数据库文件权限：
```bash
docker exec face-backend ls -la /app/data/
```

### 9.5 WebSocket 连接失败

**症状：** 前端摄像头画面正常但识别无响应。

**解决：**
1. 确认 nginx.conf 中 `/ws/` 的 WebSocket 代理配置正确
2. 确认 VITE_WS_URL 使用 `ws://` 或 `wss://` 协议
3. 检查防火墙是否放行 WebSocket 端口

### 9.6 健康检查失败

```bash
# 查看详细状态
curl http://localhost:8081/health | python3 -m json.tool

# 检查数据库连接
docker exec face-backend python -c "from app.database import engine; engine.connect(); print('DB OK')"

# 检查磁盘空间
df -h
```

### 9.7 重新部署后数据丢失

**解决：** 确保使用 `docker-compose down`（不删除 volume），不要使用 `docker-compose down -v`。

```bash
# ✅ 安全：保留数据
docker-compose -f docker-compose.deploy.yml down

# ❌ 危险：会删除数据卷
docker-compose -f docker-compose.deploy.yml down -v
```

---

## 附录

### A. Docker Compose 完整示例（含 Redis + PostgreSQL）

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: face-backend
    ports:
      - "8081:8000"
    volumes:
      - face-data:/app/data
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql://face:your_db_password@postgres:5432/face_demo
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: http://YOUR_SERVER_IP:8081
        VITE_WS_URL: ws://YOUR_SERVER_IP:8081/ws/face-stream
    container_name: face-frontend
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: face-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: face_demo
      POSTGRES_USER: face
      POSTGRES_PASSWORD: your_db_password
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U face"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: face-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  face-data:
  pg-data:
  redis-data:

networks:
  default:
    name: go-face-demo_default
```

### B. 测试

```bash
# 构建测试镜像（跳过 dlib，约 2 分钟）
docker build -f backend/Dockerfile.test -t face-demo-test ./backend

# 运行 67 个集成测试
docker run --rm face-demo-test pytest tests/test_integration.py -v

# 预期结果：67/67 passed
```

### C. 系统架构概览（API 路由）

| 分类 | 路由数 | 说明 |
|------|--------|------|
| 认证 | 3 | 登录/登出/Token 验证 |
| 用户 | 8 | CRUD + 人脸注册 |
| 人脸 | 4 | 单张识别 + WebSocket 流 |
| 考勤 | 6 | 记录查询 + 导出 |
| 设备 | 6 | CRUD + 心跳 + 状态 |
| 统计 | 5 | 考勤/部门/趋势 |
| 自助 | 4 | 个人信息 + 修改密码 |
| 健康 | 3 | health/ready/live |
| 权限 | 3 | RBAC 中间件 |
| **合计** | **42** | — |
