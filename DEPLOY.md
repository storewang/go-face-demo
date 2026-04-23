# Face Scan 人脸识别门禁系统 — 部署指南

> 版本：v3.0.0 | 最后更新：2026-04-22

---

## 目录

1. [系统架构](#1-系统架构)
2. [环境要求](#2-环境要求)
3. [开发环境部署](#3-开发环境部署)
4. [生产环境部署](#4-生产环境部署)
5. [集群部署（高可用）](#5-集群部署高可用)
6. [环境变量完整参考](#6-环境变量完整参考)
7. [前端环境变量](#7-前端环境变量)
8. [运维管理](#8-运维管理)
9. [HTTPS 配置](#9-https-配置)
10. [故障排除](#10-故障排除)

---

## 1. 系统架构

### 1.1 单机架构（开发 / 小规模生产）

```
┌──────────────────────────────────────────────────────┐
│                    Docker Compose                     │
│                                                       │
│  ┌────────────────┐       ┌────────────────────────┐ │
│  │   Frontend     │       │       Backend          │ │
│  │  (Nginx:80)    │──────▶│   (FastAPI:8000)       │ │
│  │  Vue 3 + TS    │ API   │   InsightFace/ArcFace  │ │
│  │  Element Plus  │ WS    │   OpenCV               │ │
│  └────────────────┘       │   SQLite / PostgreSQL  │ │
│                           │   Redis (可选)          │ │
│                           └────────────────────────┘ │
│                                    │                  │
│                              ┌─────┴─────┐          │
│                              │  Volume   │           │
│                              │ face-data │           │
│                              └───────────┘          │
└──────────────────────────────────────────────────────┘
```

### 1.2 集群架构（大规模生产）

```
                    ┌──────────────┐
                    │  Nginx (LB)  │ :80
                    │  负载均衡     │
                    └──────┬───────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │Backend-1 │ │Backend-2 │ │Backend-3 │ :8000
        │ FastAPI  │ │ FastAPI  │ │ FastAPI  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │             │             │
        ┌────┴─────────────┴─────────────┴────┐
        │                                      │
   ┌────┴────┐  ┌──────┐  ┌──────┐  ┌────────┐
   │PostgreSQL│  │Redis │  │MinIO │  │Prometheus│
   │  :5432   │  │:6379 │  │:9000 │  │ +Grafana │
   └─────────┘  └──────┘  └──────┘  └──────────┘
```

### 1.3 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + TypeScript 5 + Element Plus | Vite 5 构建 |
| 后端 | Python 3.12 + FastAPI + Uvicorn | Pydantic v2 校验 |
| 人脸 AI | InsightFace (ArcFace) + OpenCV | buffalo_l 模型 |
| 数据库 | SQLite（默认）/ PostgreSQL（生产） | SQLAlchemy ORM |
| 缓存 | Redis 7（可选，支持优雅降级） | 用户/识别结果缓存 |
| 对象存储 | MinIO（集群模式） | 人脸图片/特征值存储 |
| 监控 | Prometheus + Grafana（集群模式） | API 指标 + 告警 |
| 容器 | Docker + Docker Compose | 多阶段构建 |

---

## 2. 环境要求

### 2.1 硬件要求

| 项目 | 开发环境 | 生产环境（单机） | 生产环境（集群） |
|------|---------|----------------|----------------|
| CPU | 2 核 | 4 核 | 4+ 核 × 3 节点 |
| **内存** | **4GB** | **8GB+** | **8GB+** 每节点 |
| 磁盘 | 5GB | 20GB+ | 50GB+（含人脸图片） |
| 网络 | localhost | 内网 | 千兆内网 |

> ⚠️ **内存提示**：InsightFace buffalo_l 模型加载约需 1.5GB 内存。确保系统可用内存 ≥ 4GB，否则首次启动可能 OOM。

### 2.2 软件要求

| 软件 | 开发环境 | 生产环境 |
|------|---------|---------|
| Docker | 24.0+ | 24.0+ |
| Docker Compose | V2 | V2 |
| Node.js | 18+ | —（容器内构建） |
| Python | 3.12+ | —（容器内运行） |
| Git | 2.0+ | 2.0+ |

### 2.3 端口规划

| 端口 | 服务 | 开发环境 | 生产环境 | 集群模式 |
|------|------|---------|---------|---------|
| 80 | Frontend (Nginx) | ✗ | ✓ | ✓（LB） |
| 5173 | Vite Dev Server | ✓ | ✗ | ✗ |
| 8000 | Backend (FastAPI) | ✓ | ✓ | ✓（内部） |
| 8080 | Frontend (部署模式) | ✗ | ✓ | ✗ |
| 8081 | Backend (部署模式) | ✗ | ✓ | ✗ |
| 5432 | PostgreSQL | ✗ | 可选 | ✓ |
| 6379 | Redis | ✗ | 可选 | ✓ |
| 9000 | MinIO API | ✗ | 可选 | ✓ |
| 9001 | MinIO Console | ✗ | 可选 | ✓ |
| 9090 | Prometheus | ✗ | ✗ | ✓ |
| 3000 | Grafana | ✗ | ✗ | ✓ |

---

## 3. 开发环境部署

### 3.1 方式一：本机直接运行（推荐开发调试）

适合需要频繁修改代码、调试断点的开发场景。

#### 步骤 1：克隆代码

```bash
git clone https://github.com/storewang/go-face-demo.git
cd go-face-demo
```

#### 步骤 2：配置后端环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，开发环境最小配置：

```env
# ===== 开发环境最小配置 =====
DEBUG=true
JWT_SECRET_KEY=dev-secret-key-do-not-use-in-production
ADMIN_PASSWORD=admin123

# 使用 SQLite（零配置）
DATABASE_URL=sqlite:///./data/face_scan.db

# CORS 允许本地前端
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

> 💡 **开发环境无需配置 Redis、MinIO、PostgreSQL**。系统会自动降级：
> - 无 Redis → 缓存功能禁用，不影响核心业务
> - 无 MinIO → 人脸图片存储到本地磁盘
> - 无 PostgreSQL → 使用 SQLite

#### 步骤 3：启动后端

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（首次运行）
python -m app.init_db

# 启动开发服务器（支持热重载）
python run.py
# 或直接用 uvicorn：
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后访问：
- API 服务：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

#### 步骤 4：启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（支持热重载）
npm run dev
```

前端启动后访问：http://localhost:5173

> 前端开发服务器的 API 代理已在 `vite.config.ts` 中配置：
> - `/api/*` → `http://localhost:8082`（后端 API）
> - `/ws/*` → `ws://localhost:8082`（WebSocket）
>
> 如果后端端口不是 8082，需修改 `frontend/vite.config.ts` 中的 `proxy.target`。

#### 步骤 5：验证

```bash
# 后端健康检查
curl http://localhost:8000/health

# 前端页面
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
# 预期输出：200
```

### 3.2 方式二：Docker Compose 开发模式

适合需要完整中间件（PostgreSQL、Redis）的开发场景，且支持代码热重载。

#### 步骤 1：配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`：

```env
DEBUG=true
JWT_SECRET_KEY=dev-secret-key-do-not-use-in-production
ADMIN_PASSWORD=admin123
DATABASE_URL=sqlite:///./data/face_scan.db
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

#### 步骤 2：启动服务

```bash
# 启动开发环境（支持后端代码热重载）
docker compose -f docker-compose.dev.yml up -d --build
```

#### 步骤 3：查看日志

```bash
# 查看后端日志
docker compose -f docker-compose.dev.yml logs -f backend

# 查看前端日志
docker compose -f docker-compose.dev.yml logs -f frontend
```

#### 开发模式特性

| 特性 | 说明 |
|------|------|
| 后端热重载 | `--reload` 模式，修改 `app/` 代码自动重启 |
| 代码挂载 | `./backend/app:/app/app` 挂载，即时生效 |
| DEBUG=true | 开启调试日志、详细错误信息 |
| CORS 宽松 | 允许 localhost:5173 和 localhost:3000 |

### 3.3 方式三：混合模式（本机应用 + Docker 中间件）

适合需要真实 PostgreSQL/Redis 但又要保留断点调试能力的场景。

```bash
# 1. 只启动 PostgreSQL 和 Redis 容器
docker run -d --name face-dev-postgres \
  -e POSTGRES_DB=facedb -e POSTGRES_USER=face -e POSTGRES_PASSWORD=face123 \
  -p 5432:5432 postgres:15-alpine

docker run -d --name face-dev-redis \
  -p 6379:6379 redis:7-alpine

# 2. 修改 backend/.env 连接本地中间件
DATABASE_URL=postgresql+psycopg2://face:face123@localhost:5432/facedb
REDIS_HOST=localhost
REDIS_PORT=6379

# 3. 本机启动后端（可断点调试）
cd backend && source venv/bin/activate
python run.py
```

---

## 4. 生产环境部署

### 4.1 方式一：Docker Compose 单机部署（推荐）

适合 < 50 用户、单门禁点的生产场景。

#### 步骤 1：准备服务器

```bash
# 确保 Docker 已安装
docker --version
docker compose version

# 建议增加 Swap（内存不足时）
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 步骤 2：克隆代码

```bash
git clone https://github.com/storewang/go-face-demo.git
cd go-face-demo
```

#### 步骤 3：配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，⚠️ 标记为生产环境**必须修改**的项：

```env
# ===== ⚠️ 安全配置（必须修改） =====
JWT_SECRET_KEY=<用下面命令生成>
ADMIN_PASSWORD=<你的强密码>

# 生成 JWT 密钥：
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# 示例输出：a8Kj3mN9pQr2sT5vW8xY1zB4cD6fG0hJ2kL5nM8pR

# ===== 应用配置 =====
DEBUG=false
FACE_THRESHOLD=0.6
LIVENESS_FRAMES=5

# ===== 数据库 =====
# SQLite（简单部署，适合 < 50 用户）
DATABASE_URL=sqlite:///./data/face_scan.db

# PostgreSQL（推荐，适合长期运行）
# DATABASE_URL=postgresql+psycopg2://face:your_db_password@db-host:5432/facedb

# ===== CORS =====
# 替换为你的实际域名或 IP
CORS_ORIGINS=http://YOUR_SERVER_IP:8080,http://YOUR_SERVER_IP:80

# ===== 可选：Redis 缓存 =====
# REDIS_HOST=localhost
# REDIS_PORT=6379

# ===== 可选：MinIO 对象存储 =====
# S3_ENDPOINT=localhost:9000
# S3_ACCESS_KEY=minioadmin
# S3_SECRET_KEY=minioadmin123
# S3_USE_SSL=false

# ===== 可选：生物特征加密 =====
# 生产环境建议配置 Fernet 密钥加密人脸特征数据
# 生成密钥：python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# BIOMETRIC_ENCRYPTION_KEY=<生成的 Fernet 密钥>
```

#### 步骤 4：修改前端构建参数

编辑 `docker-compose.deploy.yml`，将构建参数替换为你的服务器地址：

```yaml
frontend:
  build:
    args:
      # 留空表示前端通过 nginx.conf 中的 proxy_pass 访问后端
      # 如果前后端分离部署，需要填写实际地址
      VITE_API_BASE_URL:        # 例：http://192.168.1.100:8081
      VITE_WS_URL:               # 例：ws://192.168.1.100:8081/ws/face-stream
```

> 💡 当前 `frontend/nginx.conf` 配置了 `proxy_pass http://host.docker.internal:8082`，
> 即前端 Nginx 会自动代理 API 请求到后端。如果前后端在同一台服务器上，
> `VITE_API_BASE_URL` 和 `VITE_WS_URL` 可留空。

#### 步骤 5：构建并启动

```bash
# 构建并启动（首次约 10-20 分钟，主要是下载 InsightFace 模型 ~300MB）
docker compose -f docker-compose.deploy.yml up -d --build

# 查看构建日志
docker compose -f docker-compose.deploy.yml logs -f
```

#### 步骤 6：验证部署

```bash
# 检查容器状态
docker compose -f docker-compose.deploy.yml ps

# 后端健康检查
curl http://localhost:8081/health | python3 -m json.tool

# 前端访问检查
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
# 预期输出：200
```

健康检查预期返回：

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

#### 步骤 7：访问系统

| 服务 | 地址 |
|------|------|
| 前端管理界面 | http://YOUR_SERVER_IP:8080 |
| 后端 API 文档 | http://YOUR_SERVER_IP:8081/docs |
| 健康检查 | http://YOUR_SERVER_IP:8081/health |
| 管理员登录 | 用户名 `admin`，密码为 `.env` 中的 `ADMIN_PASSWORD` |

### 4.2 方式二：一键部署脚本

项目提供了交互式部署脚本 `deploy.sh`，支持三种模式：

```bash
# 交互式配置并启动（首次运行）
./deploy.sh start --config

# 使用已有配置启动
./deploy.sh start

# 其他命令
./deploy.sh stop       # 停止服务
./deploy.sh restart    # 重启服务
./deploy.sh status     # 查看状态
./deploy.sh logs       # 查看日志
./deploy.sh clean      # 清除所有数据
```

脚本支持三种部署模式：

| 模式 | 说明 | 适合场景 |
|------|------|---------|
| Docker 全容器 | 所有服务都在 Docker 中运行 | 快速部署、标准化 |
| 本机部署 | 中间件 Docker，应用直接运行 | 调试、定制化 |
| 混合部署 | 使用外部 PG/Redis/MinIO | 企业已有基础设施 |

### 4.3 方式三：跨机器构建 + 镜像导入

适合目标服务器内存不足、无法完成构建的场景。

```bash
# === 在构建机上（内存 ≥ 8GB） ===

# 1. 构建镜像
docker compose -f docker-compose.deploy.yml build

# 2. 导出镜像
docker save face-demo-backend:latest face-demo-frontend:latest \
  | gzip > face-demo-images.tar.gz

# 3. 传输到目标服务器
scp face-demo-images.tar.gz user@target-server:/home/dev/

# === 在目标服务器上 ===

# 4. 导入镜像
docker load < face-demo-images.tar.gz

# 5. 修改 docker-compose.deploy.yml，将 build 替换为 image：
#    backend:
#      image: face-demo-backend:latest  # 替换 build: ...
#    frontend:
#      image: face-demo-frontend:latest  # 替换 build: ...

# 6. 启动
docker compose -f docker-compose.deploy.yml up -d
```

---

## 5. 集群部署（高可用）

适合大规模生产场景（> 50 用户、多门禁点），包含 3 后端节点 + PostgreSQL + Redis + MinIO + Prometheus + Grafana。

### 5.1 配置集群环境变量

```bash
cd deploy/cluster
cp .env.cluster.example .env.cluster
```

编辑 `.env.cluster`：

```env
# ⚠️ 必须修改
DB_PASSWORD=<强密码>
JWT_SECRET_KEY=<随机密钥，至少 32 字符>
S3_ACCESS_KEY=<MinIO Access Key>
S3_SECRET_KEY=<MinIO Secret Key>
GRAFANA_PASSWORD=<Grafana 管理员密码>
```

### 5.2 启动集群

```bash
cd deploy/cluster
docker compose -f docker-compose.cluster.yml up -d --build
```

### 5.3 集群组件说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx (负载均衡) | :80 | least_conn 轮询 3 后端节点 |
| Backend × 3 | :8000（内部） | FastAPI 应用 |
| PostgreSQL | :5432 | 主数据库 |
| Redis | :6379 | 缓存（512MB，LRU 淘汰） |
| MinIO | :9000 / :9001 | 人脸图片存储 / 管理控制台 |
| Prometheus | :9090 | 监控指标采集（30 天保留） |
| Grafana | :3000 | 监控仪表盘 |

### 5.4 Nginx 负载均衡配置

集群模式的 Nginx 配置位于 `nginx/nginx.conf`：

```nginx
upstream face_backend {
    least_conn;                        # 最少连接数策略
    server backend-1:8000 max_fails=3 fail_timeout=30s;
    server backend-2:8000 max_fails=3 fail_timeout=30s;
    server backend-3:8000 max_fails=3 fail_timeout=30s;
}
```

- API 请求限流：30 req/s，burst 20
- WebSocket 并发限制：每 IP 5 连接
- `/metrics` 和 `/docs` 仅内网可访问
- WebSocket 超时：3600s

---

## 6. 环境变量完整参考

### 6.1 后端环境变量（`backend/.env`）

配置由 `backend/app/config.py` 的 `Settings` 类管理，使用 pydantic-settings，支持 `.env` 文件和环境变量两种方式。

#### 🔒 安全配置（必须设置）

| 变量 | 类型 | 默认值 | 开发环境 | 生产环境 | 说明 |
|------|------|--------|---------|---------|------|
| `JWT_SECRET_KEY` | str | **无（必填）** | `dev-secret-key-do-not-use-in-production` | ⚠️ 随机密钥 ≥ 32 字符 | JWT Token 签名密钥 |
| `ADMIN_PASSWORD` | str | `None` | `admin123` | ⚠️ 强密码 | 管理员明文密码（首次启动自动哈希） |
| `ADMIN_PASSWORD_HASH` | str | `None` | — | bcrypt 哈希 | 管理员密码哈希（与上面二选一） |
| `BIOMETRIC_ENCRYPTION_KEY` | str | `""` | 留空 | ⚠️ Fernet 密钥 | 人脸特征数据加密密钥 |

**生成密钥命令：**

```bash
# JWT 密钥
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 生物特征加密密钥（Fernet）
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 管理员密码哈希（如需预设哈希）
python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your_password'))"
```

#### ⚙️ 应用基础配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `APP_NAME` | str | `Face Scan API` | 应用名称 |
| `DEBUG` | bool | `false` | 调试模式。开启后：详细错误信息、uvicorn 热重载、结构化日志为 console 格式 |
| `CORS_ORIGINS` | list[str] | `["http://localhost:5173","http://localhost:80"]` | CORS 允许的来源。支持逗号分隔字符串：`http://a.com,http://b.com` |

#### 🗄️ 数据库配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DATABASE_URL` | str | `sqlite:///./data/face_scan.db` | 数据库连接串。支持 `sqlite:///` 和 `postgresql+psycopg2://` |
| `DB_HOST` | str | `localhost` | PostgreSQL 主机（仅当构建 `DATABASE_URL` 时使用） |
| `DB_PORT` | int | `5432` | PostgreSQL 端口 |
| `DB_NAME` | str | `facedb` | PostgreSQL 数据库名 |
| `DB_USER` | str | `face` | PostgreSQL 用户名 |
| `DB_PASSWORD` | str | `""` | PostgreSQL 密码 |

> **`DATABASE_URL` 构建逻辑**：
> 1. 如果设置了 `DATABASE_URL` 环境变量 → 直接使用
> 2. 否则如果设置了 `DB_PASSWORD` → 自动构建 `postgresql+psycopg2://user:pass@host:port/db`
> 3. 否则 → 使用默认 SQLite

#### 👤 人脸识别配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `FACE_THRESHOLD` | float | `0.6` | 人脸比对阈值（0.0-1.0）。越小越严格，推荐 0.5-0.7 |
| `LIVENESS_FRAMES` | int | `5` | 活体检测需要的连续帧数（3-5） |
| `FACE_MODEL_NAME` | str | `buffalo_l` | InsightFace 模型包名 |
| `FACE_DET_SIZE` | int | `640` | 人脸检测输入分辨率（像素） |
| `FACE_PROVIDER` | str | `CPUExecutionProvider` | ONNX Runtime 推理后端。可选 `CUDAExecutionProvider`（GPU） |
| `INSIGHTFACE_HOME` | str | `""` | 自定义模型存储目录。为空时使用默认 `~/.insightface` |

#### 📂 数据存储路径

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DATA_DIR` | Path | `./data` | 数据根目录 |
| `FACES_DIR` | Path | `./data/faces` | 人脸数据目录 |
| `IMAGES_DIR` | Path | `./data/faces/images` | 人脸图片目录 |
| `ENCODINGS_DIR` | Path | `./data/faces/encodings` | 特征向量目录 |

> 路径均为相对路径，基于后端工作目录解析。Docker 部署时对应 `/app/data/`。

#### 🔄 Redis 缓存配置（可选）

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `REDIS_HOST` | str | `localhost` | Redis 主机 |
| `REDIS_PORT` | int | `6379` | Redis 端口 |
| `REDIS_DB` | int | `0` | Redis 数据库编号 |
| `CACHE_USER_TTL` | int | `600` | 用户信息缓存 TTL（秒），10 分钟 |
| `CACHE_RECOG_TTL` | int | `3` | 识别结果缓存 TTL（秒） |
| `CACHE_STATS_TTL` | int | `300` | 统计数据缓存 TTL（秒），5 分钟 |

> 不配置 Redis 时，缓存功能自动降级为无缓存，不影响核心业务。

#### ☁️ MinIO / S3 对象存储配置（可选）

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `S3_ENDPOINT` | str | `localhost:9000` | MinIO/S3 端点地址 |
| `S3_ACCESS_KEY` | str | `""` | Access Key |
| `S3_SECRET_KEY` | str | `""` | Secret Key |
| `S3_USE_SSL` | bool | `false` | 是否使用 SSL |
| `S3_FACE_BUCKET` | str | `faces` | 人脸图片桶名 |
| `S3_ENCODING_BUCKET` | str | `encodings` | 特征向量桶名 |
| `S3_SNAPSHOT_BUCKET` | str | `snapshots` | 抓拍图桶名 |

> 不配置 MinIO 时，图片存储到本地磁盘（`DATA_DIR` 下）。

#### 🕐 数据生命周期配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DATA_RETENTION_DAYS` | int | `90` | 考勤记录保留天数 |
| `SNAPSHOT_RETENTION_DAYS` | int | `30` | 抓拍图保留天数 |
| `AUDIT_RETENTION_DAYS` | int | `365` | 审计日志保留天数 |
| `FACE_DATA_DELETE_ON_RESIGN` | bool | `true` | 员工离职是否自动删除人脸数据 |

#### 🔑 JWT 配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `JWT_SECRET_KEY` | str | **必填** | JWT 签名密钥 |
| `JWT_ALGORITHM` | str | `HS256` | JWT 签名算法 |
| `JWT_EXPIRE_HOURS` | int | `8` | Token 过期时间（小时） |

### 6.2 环境变量配置模板

#### 开发环境 `.env`

```env
# ========== 开发环境配置 ==========
# 生成时间：手动创建

# --- 安全 ---
DEBUG=true
JWT_SECRET_KEY=dev-secret-key-do-not-use-in-production
ADMIN_PASSWORD=admin123

# --- 数据库（SQLite 零配置） ---
DATABASE_URL=sqlite:///./data/face_scan.db

# --- 人脸识别 ---
FACE_THRESHOLD=0.6
LIVENESS_FRAMES=3

# --- CORS ---
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# --- 以下可选，不配置则自动降级 ---
# REDIS_HOST=localhost
# REDIS_PORT=6379
# S3_ENDPOINT=localhost:9000
# S3_ACCESS_KEY=minioadmin
# S3_SECRET_KEY=minioadmin123
```

#### 生产环境 `.env`

```env
# ========== 生产环境配置 ==========
# 生成时间：按实际情况填写
# ⚠️ 请妥善保管此文件，不要提交到版本控制

# --- 安全（⚠️ 必须修改） ---
DEBUG=false
JWT_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_PASSWORD=<你的强密码>
# BIOMETRIC_ENCRYPTION_KEY=<python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# --- JWT ---
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# --- 数据库 ---
# 方式一：SQLite（简单部署）
DATABASE_URL=sqlite:///./data/face_scan.db

# 方式二：PostgreSQL（推荐）
# DATABASE_URL=postgresql+psycopg2://face:your_strong_password@db-host:5432/facedb
# DB_HOST=db-host
# DB_PORT=5432
# DB_NAME=facedb
# DB_USER=face
# DB_PASSWORD=your_strong_password

# --- 人脸识别 ---
FACE_THRESHOLD=0.6
LIVENESS_FRAMES=5
FACE_MODEL_NAME=buffalo_l
FACE_DET_SIZE=640
FACE_PROVIDER=CPUExecutionProvider

# --- CORS ---
CORS_ORIGINS=http://YOUR_SERVER_IP:8080,http://YOUR_DOMAIN

# --- Redis 缓存（推荐开启） ---
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CACHE_USER_TTL=600
CACHE_RECOG_TTL=3
CACHE_STATS_TTL=300

# --- MinIO 对象存储（大规模部署推荐） ---
# S3_ENDPOINT=localhost:9000
# S3_ACCESS_KEY=your_access_key
# S3_SECRET_KEY=your_secret_key
# S3_USE_SSL=false

# --- 数据生命周期 ---
DATA_RETENTION_DAYS=90
SNAPSHOT_RETENTION_DAYS=30
AUDIT_RETENTION_DAYS=365
FACE_DATA_DELETE_ON_RESIGN=true
```

#### 集群环境 `.env.cluster`

```env
# ========== 集群部署配置 ==========
# 位于 deploy/cluster/.env.cluster

# ⚠️ 必须修改
DB_PASSWORD=<强密码>
JWT_SECRET_KEY=<随机密钥至少32字符>
S3_ACCESS_KEY=<MinIO Access Key>
S3_SECRET_KEY=<MinIO Secret Key>
GRAFANA_PASSWORD=<Grafana 管理员密码>
```

---

## 7. 前端环境变量

前端使用 Vite 的环境变量机制，在构建时注入。

### 7.1 变量说明

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE_URL` | 后端 API 基础地址。留空时使用相对路径（通过 Nginx 代理） |
| `VITE_WS_URL` | WebSocket 连接地址。留空时使用相对路径 |

### 7.2 环境文件

| 文件 | 场景 | 内容 |
|------|------|------|
| `frontend/.env.development` | `npm run dev` | `VITE_API_BASE_URL=http://localhost:8000/api` |
| `frontend/.env.production` | `npm run build` | 留空（通过 Nginx 代理） |

### 7.3 各环境推荐配置

**开发环境** (`frontend/.env.development`)：

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/face-stream
```

**生产环境 — 通过 Nginx 代理** (`frontend/.env.production`)：

```env
VITE_API_BASE_URL=
VITE_WS_URL=
```

**生产环境 — 前后端分离部署**（Docker build args 或 `.env.production`）：

```env
VITE_API_BASE_URL=http://YOUR_SERVER_IP:8081
VITE_WS_URL=ws://YOUR_SERVER_IP:8081/ws/face-stream
```

### 7.4 Docker 构建时传入

在 `docker-compose.deploy.yml` 中通过 `build.args` 传入：

```yaml
frontend:
  build:
    args:
      VITE_API_BASE_URL: http://YOUR_SERVER_IP:8081
      VITE_WS_URL: ws://YOUR_SERVER_IP:8081/ws/face-stream
```

---

## 8. 运维管理

### 8.1 日常操作

```bash
# 查看日志
docker compose -f docker-compose.deploy.yml logs -f backend     # 后端日志
docker compose -f docker-compose.deploy.yml logs -f frontend    # 前端日志

# 重启服务
docker compose -f docker-compose.deploy.yml restart backend     # 只重启后端
docker compose -f docker-compose.deploy.yml restart             # 全部重启

# 停止服务（保留数据）
docker compose -f docker-compose.deploy.yml down

# ⚠️ 危险：停止并删除数据卷
docker compose -f docker-compose.deploy.yml down -v
```

### 8.2 更新部署

```bash
cd go-face-demo
git pull origin main

# 重新构建并启动（只重建有变化的镜像）
docker compose -f docker-compose.deploy.yml up -d --build

# 如果只更新了后端代码
docker compose -f docker-compose.deploy.yml up -d --build backend
```

### 8.3 数据备份与恢复

```bash
# 备份 SQLite 数据库
docker cp face-backend:/app/data/face_scan.db ./backup/face_scan_$(date +%Y%m%d).db

# 备份完整数据卷
docker run --rm \
  -v go-face-demo_face-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/face-data-$(date +%Y%m%d).tar.gz /data

# 恢复数据卷
docker run --rm \
  -v go-face-demo_face-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/face-data-YYYYMMDD.tar.gz -C /
```

### 8.4 资源监控

```bash
# 容器资源占用
docker stats face-backend face-frontend --no-stream

# Prometheus 监控（集群模式）
# 访问 http://YOUR_SERVER_IP:9090

# Grafana 仪表盘（集群模式）
# 访问 http://YOUR_SERVER_IP:3000
```

### 8.5 数据库迁移

使用 Alembic 管理数据库版本：

```bash
cd backend

# 生成迁移脚本（模型变更后）
alembic revision --autogenerate -m "描述变更"

# 执行迁移
alembic upgrade head

# 查看当前版本
alembic current

# 回退一个版本
alembic downgrade -1
```

---

## 9. HTTPS 配置

### 9.1 自签证书（测试用）

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout ssl/server.key -out ssl/server.crt \
  -subj "/CN=your-domain.com" \
  -addext "subjectAltName=DNS:your-domain.com,IP:YOUR_SERVER_IP"
```

### 9.2 Nginx SSL 配置

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

    client_max_body_size 20M;

    location /api/ {
        proxy_pass http://face-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://face-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://face-frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

前端构建参数需改为 HTTPS 地址：

```yaml
VITE_API_BASE_URL: https://your-domain.com
VITE_WS_URL: wss://your-domain.com/ws/face-stream
```

---

## 10. 故障排除

### 10.1 InsightFace 模型加载失败 / OOM

**症状**：容器被 SIGKILL，日志中模型下载或加载中断。

**解决**：
1. 增加系统 Swap（见 §4.1 步骤 1）
2. 设置 `FACE_DET_SIZE=320`（降低分辨率，减少内存占用）
3. 使用跨机器构建（见 §4.3）

### 10.2 bcrypt `$` 符号被 docker-compose 解析

**症状**：使用 `ADMIN_PASSWORD_HASH` 时认证失败，因为 `$` 被 Compose 当变量解析。

**解决**：使用 `ADMIN_PASSWORD` 明文密码（系统首次启动会自动生成 bcrypt 哈希），不要在 docker-compose 中直接写 `ADMIN_PASSWORD_HASH`。

### 10.3 CORS_ORIGINS 格式错误

**症状**：启动报错 `Input should be a valid list`。

**解决**：`.env` 中支持两种格式：

```env
# 格式一：逗号分隔字符串（推荐）
CORS_ORIGINS=http://localhost:5173,http://localhost:80

# 格式二：JSON 数组
CORS_ORIGINS=["http://localhost:5173","http://localhost:80"]
```

### 10.4 数据库连接失败

**症状**：`no such table` 或 `connection refused`。

**解决**：
```bash
# SQLite：确认数据库文件存在
docker exec face-backend ls -la /app/data/

# PostgreSQL：确认连接参数
docker exec face-backend python -c "
from app.database import engine
with engine.connect() as conn:
    print('DB OK')
"
```

### 10.5 WebSocket 连接失败

**症状**：前端摄像头画面正常但识别无响应。

**解决**：
1. 确认 Nginx 配置中 `/ws/` 的 WebSocket 代理正确
2. 确认 `VITE_WS_URL` 使用 `ws://` 或 `wss://` 协议
3. 检查防火墙是否放行 WebSocket 端口
4. 查看 Nginx 错误日志：`docker exec face-frontend cat /var/log/nginx/error.log`

### 10.6 健康检查失败

```bash
# 查看详细健康状态
curl http://localhost:8081/health | python3 -m json.tool

# 检查磁盘空间
df -h

# 检查容器日志
docker compose -f docker-compose.deploy.yml logs --tail=100 backend
```

### 10.7 重新部署后数据丢失

**原因**：使用了 `docker compose down -v`（`-v` 会删除数据卷）。

**解决**：始终使用 `docker compose down`（不带 `-v`）停止服务。

### 10.8 Redis 连接失败

**症状**：日志中出现 Redis 连接错误，但系统仍可运行。

**说明**：这是正常行为。系统实现了 Redis 优雅降级 — 连接失败时自动切换为无缓存模式。如需启用缓存，确认 Redis 正在运行且 `REDIS_HOST`/`REDIS_PORT` 配置正确。

---

## 附录

### A. Docker Compose 文件速查

| 文件 | 用途 | 适用环境 |
|------|------|---------|
| `docker-compose.yml` | 基础配置（SQLite） | 快速体验 |
| `docker-compose.dev.yml` | 开发模式（热重载） | 开发环境 |
| `docker-compose.deploy.yml` | 生产部署 | 生产环境 |
| `deploy/cluster/docker-compose.cluster.yml` | 集群部署（3 节点） | 大规模生产 |

### B. 关键 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| GET | `/api/users/` | 用户列表 |
| POST | `/api/users/register` | 注册用户（含人脸） |
| POST | `/api/face/recognize` | 人脸识别（单张） |
| WS | `/ws/face-stream` | 实时人脸识别流 |
| GET | `/api/attendance/` | 考勤记录 |
| GET | `/api/statistics/attendance` | 考勤统计 |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标 |

### C. 一键部署脚本命令

```bash
./deploy.sh start [--config]  # 启动（--config 强制重新配置）
./deploy.sh stop              # 停止
./deploy.sh restart           # 重启
./deploy.sh status            # 查看状态
./deploy.sh logs [service]    # 查看日志（backend/frontend/docker）
./deploy.sh clean             # 清除所有数据
```
