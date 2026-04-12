#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  Face Scan 人脸识别门禁系统 — 一键部署脚本
#  支持: 本机部署 / Docker 全容器部署 / 混合部署
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
ENV_FILE="$BACKEND_DIR/.env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.standalone.yml"
PYTHON="$BACKEND_DIR/venv/bin/python3"
PIP="$BACKEND_DIR/venv/bin/pip"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ============================================================
# 1. 交互式配置
# ============================================================

confirm() {
  local prompt="$1" default_val="$2"
  if [ -n "$default_val" ]; then
    read -rp "$(echo -e "${BLUE}$prompt${NC} [${default_val}]: ")" input
    echo "${input:-$default_val}"
  else
    read -rp "$(echo -e "${BLUE}$prompt${NC}: ")" input
    echo "$input"
  fi
}

confirm_yes() {
  local prompt="$1"
  read -rp "$(echo -e "${BLUE}$prompt${NC} [Y/n]: ")" input
  [[ "$input" =~ ^[Yy]$ ]]
}

generate_jwt_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

collect_config() {
  echo ""
  echo "=========================================="
  echo "  Face Scan 部署配置向导"
  echo "=========================================="
  echo ""

  # --- 部署模式 ---
  echo "--- 部署模式 ---"
  echo "  1) Docker 全容器部署 (推荐生产环境)"
  echo "  2) 本机部署 (Docker 跑中间件，应用直接运行)"
  echo "  3) 混合部署 (外部 PG/Redis/MinIO + 本机应用)"
  MODE=$(confirm "选择部署模式" "2")
  case "$MODE" in
    1) MODE="docker" ;;
    2) MODE="local" ;;
    3) MODE="hybrid" ;;
    *) error "无效模式，请输入 1/2/3" ;;
  esac

  # --- PostgreSQL ---
  echo ""
  echo "--- PostgreSQL 配置 ---"
  if [ "$MODE" = "docker" ]; then
    PG_HOST="localhost"
    PG_PORT=$(confirm "PG 端口" "5432")
    PG_NAME=$(confirm "数据库名" "facedb")
    PG_USER=$(confirm "用户名" "postgres")
    PG_PASS=$(confirm "密码" "postgres123")
    PG_SOURCE="docker"
  else
    PG_SOURCE=$(confirm "PG 来源" "external")
    if [ "$PG_SOURCE" = "external" ]; then
      PG_HOST=$(confirm "PG 主机地址" "10.244.255.92")
    else
      PG_HOST="localhost"
    fi
    PG_PORT=$(confirm "PG 端口" "5432")
    PG_NAME=$(confirm "数据库名" "facedb")
    PG_USER=$(confirm "用户名" "postgres")
    PG_PASS=$(confirm "密码" "")
    if [ -z "$PG_PASS" ]; then
      echo -e "${RED}PG 密码不能为空${NC}"
      exit 1
    fi
  fi

  # --- Redis ---
  echo ""
  echo "--- Redis 配置 ---"
  if [ "$MODE" = "docker" ]; then
    REDIS_HOST="localhost"
    REDIS_PORT=$(confirm "Redis 端口" "6379")
    REDIS_PASS=""
    REDIS_SOURCE="docker"
  else
    REDIS_SOURCE=$(confirm "Redis 来源" "external")
    if [ "$REDIS_SOURCE" = "external" ]; then
      REDIS_HOST=$(confirm "Redis 主机地址" "192.168.3.85")
    else
      REDIS_HOST="localhost"
    fi
    REDIS_PORT=$(confirm "Redis 端口" "6379")
    REDIS_PASS=$(confirm "Redis 密码 (无密码直接回车)" "")
  fi

  # --- MinIO ---
  echo ""
  echo "--- MinIO 对象存储配置 ---"
  if [ "$MODE" = "docker" ]; then
    S3_ENDPOINT="localhost:9000"
    S3_ACCESS=$(confirm "Access Key" "minioadmin")
    S3_SECRET=$(confirm "Secret Key" "minioadmin123")
    S3_SOURCE="docker"
  else
    S3_SOURCE=$(confirm "MinIO 来源" "docker")
    if [ "$S3_SOURCE" = "external" ]; then
      S3_ENDPOINT=$(confirm "MinIO 地址" "localhost:9000")
    else
      S3_ENDPOINT="localhost:9000"
    fi
    S3_ACCESS=$(confirm "Access Key" "minioadmin")
    S3_SECRET=$(confirm "Secret Key" "minioadmin123")
  fi

  # --- 应用配置 ---
  echo ""
  echo "--- 应用配置 ---"
  JWT_SECRET=$(confirm "JWT 密钥" "$(generate_jwt_secret)")
  ADMIN_PWD=$(confirm "管理员密码" "admin123")
  FACE_THRESHOLD=$(confirm "人脸识别阈值 (0.1-1.0)" "0.6")
  DEBUG_MODE=$(confirm "开启调试模式 (true/false)" "false")
  CORS_ORIGINS=$(confirm "CORS 允许来源 (逗号分隔)" "http://localhost:5173,http://localhost:80")

  # --- Nginx (仅本机/混合模式) ---
  NGINX_ENABLE="false"
  if [ "$MODE" != "docker" ]; then
    NGINX_ENABLE=$(confirm "启用 Nginx 反向代理 (true/false)" "false")
  fi
}

# ============================================================
# 2. 生成 .env 文件
# ============================================================

generate_env() {
  info "生成 backend/.env ..."

  local db_url
  if [ "$MODE" = "docker" ]; then
    db_url="postgresql+psycopg2://${PG_USER}:${PG_PASS}@${PG_HOST}:${PG_PORT}/${PG_NAME}"
  else
    db_url="postgresql+psycopg2://${PG_USER}:${PG_PASS}@${PG_HOST}:${PG_PORT}/${PG_NAME}"
  fi

  cat > "$ENV_FILE" << EOF
# Face Scan 后端配置 (由 deploy.sh 自动生成)
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')

# ===== 必填 =====
JWT_SECRET_KEY=${JWT_SECRET}
ADMIN_PASSWORD=${ADMIN_PWD}
DEBUG=${DEBUG_MODE}

# ===== 数据库 =====
DATABASE_URL=${db_url}
DB_HOST=${PG_HOST}
DB_PORT=${PG_PORT}
DB_NAME=${PG_NAME}
DB_USER=${PG_USER}
DB_PASSWORD=${PG_PASS}

# ===== Redis =====
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
$( [ -n "$REDIS_PASS" ] && echo "REDIS_PASSWORD=${REDIS_PASS}" )

# ===== MinIO =====
S3_ENDPOINT=${S3_ENDPOINT}
S3_ACCESS_KEY=${S3_ACCESS}
S3_SECRET_KEY=${S3_SECRET}
S3_USE_SSL=false

# ===== 人脸识别 =====
FACE_THRESHOLD=${FACE_THRESHOLD}
LIVENESS_FRAMES=5

# ===== CORS =====
CORS_ORIGINS=["${CORS_ORIGINS//,/\",\"}"]
EOF

  info "backend/.env 已生成"
}

# ============================================================
# 3. Docker 全容器部署
# ============================================================

docker_deploy() {
  info "===== Docker 全容器部署 ====="

  generate_env
  generate_docker_compose

  docker compose -f "$COMPOSE_FILE" up -d --build

  info "等待服务启动..."
  wait_for_service "http://localhost:8000/health" 120
  wait_for_service "http://localhost:80" 60

  show_summary
}

generate_docker_compose() {
  info "生成 docker-compose.standalone.yml ..."

  local redis_cmd="redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru"
  if [ -n "$REDIS_PASS" ]; then
    redis_cmd="redis-server --requirepass ${REDIS_PASS} --maxmemory 512mb --maxmemory-policy allkeys-lru"
  fi

  cat > "$COMPOSE_FILE" << COMPOSE_EOF
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: face-scan-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${PG_NAME}
      POSTGRES_USER: ${PG_USER}
      POSTGRES_PASSWORD: ${PG_PASS}
    volumes:
      - face-postgres-data:/var/lib/postgresql/data
    ports:
      - "${PG_PORT}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER} -d ${PG_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: face-scan-redis
    restart: unless-stopped
    command: ${redis_cmd}
    volumes:
      - face-redis-data:/data
    ports:
      - "${REDIS_PORT}:6379"
    healthcheck:
      test: ["CMD", "redis-cli${REDIS_PASS:+ -a $REDIS_PASS}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    container_name: face-scan-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS}
      MINIO_ROOT_PASSWORD: ${S_SECRET}
    volumes:
      - face-minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: face-scan-backend
    restart: unless-stopped
    env_file:
      - ./backend/.env
    volumes:
      - face-backend-data:/app/data
      - face-minio-data:/data:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: face-scan-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      backend:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    container_name: face-scan-nginx
    restart: unless-stopped
    ports:
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend

volumes:
  face-postgres-data:
  face-redis-data:
  face-minio-data:
  face-backend-data:
COMPOSE_EOF

  info "docker-compose.standalone.yml 已生成"
}

# ============================================================
# 4. 本机 / 混合部署
# ============================================================

local_deploy() {
  info "===== 本机部署 ====="

  # 启动 Docker 中间件 (非 external 的)
  start_docker_middleware

  # 检查 Python venv
  check_python_venv

  # 生成 .env
  generate_env

  # 安装依赖
  install_backend_deps

  # 初始化数据库
  init_database

  # 创建 MinIO buckets
  setup_minio_buckets

  # 启动应用
  start_local_services

  show_summary
}

start_docker_middleware() {
  info "检查 Docker 中间件..."

  if ! command -v docker &>/dev/null; then
    error "Docker 未安装，请先安装 Docker"
  fi

  if ! docker info &>/dev/null; then
    error "Docker 守护进程未运行，请先启动 Docker"
  fi

  # PostgreSQL
  if [ "$PG_SOURCE" = "docker" ]; then
    if docker ps --format '{{.Names}}' | grep -q 'face-scan-postgres'; then
      info "PostgreSQL 容器已在运行"
    else
      info "启动 PostgreSQL 容器..."
      docker run -d \
        --name face-scan-postgres \
        --restart unless-stopped \
        -e POSTGRES_DB="${PG_NAME}" \
        -e POSTGRES_USER="${PG_USER}" \
        -e POSTGRES_PASSWORD="${PG_PASS}" \
        -p "${PG_PORT}:5432" \
        -v face-scan-postgres-data:/var/lib/postgresql/data \
        postgres:15-alpine >/dev/null

      info "等待 PostgreSQL 就绪..."
      for i in $(seq 1 30); do
        if docker exec face-scan-postgres pg_isready -U "${PG_USER}" -d "${PG_NAME}" &>/dev/null; then
          info "PostgreSQL 就绪 (${i}s)"
          break
        fi
        sleep 2
      done
    fi

    # 创建数据库
    docker exec face-scan-postgres psql -U "${PG_USER}" -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='${PG_NAME}'" | grep -q 1 || \
      docker exec face-scan-postgres createdb -U "${PG_USER}" "${PG_NAME}"
    info "数据库 '${PG_NAME}' 已就绪"
  else
    info "使用外部 PostgreSQL: ${PG_HOST}:${PG_PORT}/${PG_NAME}"
    verify_pg_connection
  fi

  # Redis
  if [ "$REDIS_SOURCE" = "docker" ]; then
    if docker ps --format '{{.Names}}' | grep -q 'face-scan-redis'; then
      info "Redis 容器已在运行"
    else
      info "启动 Redis 容器..."
      local redis_cmd="redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru"
      if [ -n "$REDIS_PASS" ]; then
        redis_cmd="redis-server --requirepass ${REDIS_PASS} --maxmemory 512mb --maxmemory-policy allkeys-lru"
      fi
      docker run -d \
        --name face-scan-redis \
        --restart unless-stopped \
        -p "${REDIS_PORT}:6379" \
        -v face-scan-redis-data:/data \
        redis:7-alpine \
        $redis_cmd >/dev/null

      info "等待 Redis 就绪..."
      sleep 2
      info "Redis 就绪"
    fi
  else
    info "使用外部 Redis: ${REDIS_HOST}:${REDIS_PORT}"
    verify_redis_connection
  fi

  # MinIO
  if [ "$S3_SOURCE" = "docker" ]; then
    if docker ps --format '{{.Names}}' | grep -q 'face-scan-minio'; then
      info "MinIO 容器已在运行"
    else
      info "启动 MinIO 容器..."
      mkdir -p "$BACKEND_DIR/data/minio"
      docker run -d \
        --name face-scan-minio \
        --restart unless-stopped \
        -p 9000:9000 \
        -p 9001:9001 \
        -e MINIO_ROOT_USER="${S3_ACCESS}" \
        -e MINIO_ROOT_PASSWORD="${S3_SECRET}" \
        -v "$BACKEND_DIR/data/minio:/data" \
        minio/minio:latest \
        server /data --console-address ":9001" >/dev/null

      info "等待 MinIO 就绪..."
      for i in $(seq 1 15); do
        if curl -s "http://localhost:9000/minio/health/live" &>/dev/null; then
          info "MinIO 就绪 (${i}s)"
          break
        fi
        sleep 2
      done
    fi
  else
    info "使用外部 MinIO: ${S3_ENDPOINT}"
  fi
}

check_python_venv() {
  if [ ! -f "$PYTHON" ]; then
    info "创建 Python 虚拟环境..."
    python3 -m venv "$BACKEND_DIR/venv"
  fi

  if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
    info "安装 Python 依赖..."
    "$PIP" install --upgrade pip -q 2>&1 | tail -1
    "$PIP" install -r "$BACKEND_DIR/requirements.txt" -q 2>&1 | tail -3
  fi

  local pyver
  pyver=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  info "Python $pyver 就绪"
}

install_backend_deps() {
  info "检查后端依赖..."

  if ! "$PYTHON" -c "import fastapi; import uvicorn; import psycopg2; import redis; import minio" 2>/dev/null; then
    warn "缺少依赖，正在安装..."
    "$PIP" install -r "$BACKEND_DIR/requirements.txt" 2>&1 | tail -5
  fi

  info "后端依赖已就绪"
}

init_database() {
  info "初始化数据库..."
  (cd "$BACKEND_DIR" && "$PYTHON" -m app.init_db 2>&1)
}

setup_minio_buckets() {
  if ! "$PYTHON" -c "from minio import Minio; Minio('${S3_ENDPOINT}', access_key='${S3_ACCESS}', secret_key='${S3_SECRET}', secure=False).bucket_exists('faces')" 2>/dev/null; then
    info "创建 MinIO buckets..."
    "$PYTHON" -c "
from minio import Minio
client = Minio('${S3_ENDPOINT}', access_key='${S3_ACCESS}', secret_key='${S3_SECRET}', secure=False)
for b in ['faces', 'encodings', 'snapshots']:
    if not client.bucket_exists(b):
        client.make_bucket(b)
        print(f'  created: {b}')
" 2>&1 | sed 's/^/  /'
  fi
}

start_local_services() {
  # 停止旧进程
  stop_local_services

  info "启动后端服务 (http://localhost:8000)..."
  (cd "$BACKEND_DIR" && setsid "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /tmp/face-scan-backend.log 2>&1 </dev/null &)

  info "启动前端服务 (http://localhost:5173)..."
  (cd "$FRONTEND_DIR" && setsid npx vite --host 0.0.0.0 --port 5173 >> /tmp/face-scan-frontend.log 2>&1 </dev/null &)

  wait_for_service "http://localhost:8000/health" 120
  wait_for_service "http://localhost:5173" 30

  if [ "$NGINX_ENABLE" = "true" ]; then
    start_nginx
  fi
}

start_nginx() {
  if ! command -v nginx &>/dev/null; then
    warn "Nginx 未安装，跳过反向代理配置"
    return
  fi

  info "配置 Nginx 反向代理..."

  local nginx_conf="/etc/nginx/sites-available/face-scan.conf"
  sudo tee "$nginx_conf" > /dev/null << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 20M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX_EOF

  sudo ln -sf "$nginx_conf" /etc/nginx/sites-enabled/face-scan.conf 2>/dev/null
  sudo nginx -t 2>/dev/null && sudo systemctl reload nginx 2>/dev/null && info "Nginx 反向代理已配置 (端口 80)"
}

stop_local_services() {
  # 停止后端
  local backend_pid
  backend_pid=$(lsof -ti :8000 2>/dev/null)
  if [ -n "$backend_pid" ]; then
    kill $backend_pid 2>/dev/null || true
  fi

  # 停止前端
  local frontend_pid
  frontend_pid=$(lsof -ti :5173 2>/dev/null)
  if [ -n "$frontend_pid" ]; then
    kill $frontend_pid 2>/dev/null || true
  fi
}

verify_pg_connection() {
  info "验证 PostgreSQL 连接: ${PG_HOST}:${PG_PORT}/${PG_NAME}..."
  if ! "$PYTHON" -c "
import psycopg2
conn = psycopg2.connect(host='${PG_HOST}', port=${PG_PORT}, user='${PG_USER}', password='${PG_PASS}', dbname='${PG_NAME}', connect_timeout=5)
conn.close()
print('OK')
" 2>&1 | grep -q OK; then
    error "无法连接 PostgreSQL (${PG_HOST}:${PG_PORT}/${PG_NAME})，请检查地址和凭据"
  fi
}

verify_redis_connection() {
  info "验证 Redis 连接: ${REDIS_HOST}:${REDIS_PORT}..."
  if ! "$PYTHON" -c "
import redis
r = redis.Redis(host='${REDIS_HOST}', port=${REDIS_PORT}, socket_timeout=5)
${REDIS_PASS:+r.auth('${REDIS_PASS}')}
r.ping()
print('OK')
" 2>&1 | grep -q OK; then
    error "无法连接 Redis (${REDIS_HOST}:${REDIS_PORT})，请检查地址和配置"
  fi
}

# ============================================================
# 5. 工具函数
# ============================================================

wait_for_service() {
  local url="$1" timeout="${2:-60}"
  info "等待 $url 就绪 (超时 ${timeout}s)..."

  local i=0
  local step=2
  local elapsed=0
  while [ $elapsed -lt $timeout ]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      info "$url 就绪 (${elapsed}s)"
      return 0
    fi
    sleep $step
    i=$((i + 1))
    elapsed=$((i * step))
  done

  warn "$url 未在 ${timeout}s 内就绪"
  return 1
}

show_summary() {
  echo ""
  echo "=========================================="
  echo "  部署完成"
  echo "=========================================="
  echo ""
  echo "  部署模式:     $([ "$MODE" = "docker" ] && echo "Docker 全容器" || [ "$MODE" = "local" ] && echo "本机部署" || echo "混合部署")"
  echo "  PostgreSQL:   ${PG_HOST}:${PG_PORT}/${PG_NAME}"
  echo "  Redis:        ${REDIS_HOST}:${REDIS_PORT}"
  echo "  MinIO:        ${S3_ENDPOINT}"
  echo "  人脸阈值:     ${FACE_THRESHOLD}"
  echo "  管理员密码:   ${ADMIN_PWD}"
  echo ""
  echo "  访问地址:"
  echo "    前端 (开发):   http://localhost:5173"
  echo "    后端 API:     http://localhost:8000"
  echo "    API 文档:     http://localhost:8000/docs"
  echo "    MinIO 控制台:  http://localhost:9001"
  echo ""

  if [ "$MODE" = "docker" ]; then
    echo "  管理命令:"
    echo "    docker compose -f docker-compose.standalone.yml logs -f  # 查看日志"
    echo "    docker compose -f docker-compose.standalone.yml down        # 停止服务"
    echo "    docker compose -f docker-compose.standalone.yml restart     # 重启服务"
  else
    echo "  管理命令:"
    echo "    查看后端日志: tail -f /tmp/face-scan-backend.log"
    echo "    查看前端日志: tail -f /tmp/face-scan-frontend.log"
    echo "    停止服务:     $0 stop"
  fi
  echo ""
}

# ============================================================
# 6. 命令入口
# ============================================================

cmd_start() {
  if [ "$MODE" = "docker" ]; then
    docker_deploy
  else
    local_deploy
  fi
}

cmd_stop() {
  info "停止服务..."

  if [ "$MODE" = "docker" ]; then
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null
  else
    stop_local_services
  fi

  info "服务已停止"
}

cmd_restart() {
  cmd_stop
  sleep 2
  cmd_start
}

cmd_status() {
  echo "=== 服务状态 ==="
  echo ""

  if [ "$MODE" = "docker" ] || [ -f "$COMPOSE_FILE" ]; then
    echo "--- Docker 容器 ---"
    docker compose -f "$COMPOSE_FILE" ps 2>/dev/null || echo "  (未部署)"
    echo ""
  fi

  echo "--- 端口监听 ---"
  for port in 8000 5173 9000 9001 5432 6379 80 443; do
    local pid
    pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
      echo "  :$port  ✓ (PID: $pid)"
    fi
  done

  echo ""

  if [ -f "$ENV_FILE" ]; then
    echo "--- 后端配置 (backend/.env) ---"
    grep -E '^(DATABASE_URL|REDIS_HOST|S3_ENDPOINT|ADMIN_PASSWORD|FACE_THRESHOLD|DEBUG)=' "$ENV_FILE" | \
      sed 's/=.*/  &/' | while read -r line; do echo "  $line"; done
  fi
}

cmd_logs() {
  local service="${1:-backend}"
  case "$service" in
    backend)
      if [ -f /tmp/face-scan-backend.log ]; then
        tail -50 /tmp/face-scan-backend.log
      else
        echo "后端日志文件不存在"
      fi
      ;;
    frontend)
      if [ -f /tmp/face-scan-frontend.log ]; then
        tail -30 /tmp/face-scan-frontend.log
      else
        echo "前端日志文件不存在"
      fi
      ;;
    docker)
      docker compose -f "$COMPOSE_FILE" logs --tail=50 2>/dev/null || echo "Docker 日志不可用"
      ;;
    *)
      echo "用法: $0 logs [backend|frontend|docker]"
      ;;
  esac
}

cmd_clean() {
  warn "此操作将删除所有数据，包括数据库、人脸数据和容器卷"
  confirm_yes "确定要清除所有数据吗？" || exit 0

  info "清除中..."

  # 停止服务
  cmd_stop 2>/dev/null

  # 删除 Docker 资源
  docker rm -f face-scan-postgres face-scan-redis face-scan-minio 2>/dev/null || true
  docker volume rm face-scan-postgres-data face-scan-redis-data face-minio-data face-backend-data 2>/dev/null || true

  # 删除本地数据
  rm -rf "$BACKEND_DIR/data" 2>/dev/null || true
  rm -rf "$FRONTEND_DIR/dist" 2>/dev/null || true
  rm -f /tmp/face-scan-backend.log /tmp/face-scan-face-frontend.log 2>/dev/null || true

  info "清除完成"
}

# ============================================================
# Main
# ============================================================

ACTION="${1:-start}"

case "$ACTION" in
  start)
    # 首次运行或指定 --config 时收集配置，否则用已有 .env
    if [ "$#" -gt 1 ] && [ "$2" = "--config" ] || [ ! -f "$ENV_FILE" ]; then
      collect_config
    else
      info "使用已有 backend/.env 配置"
      # 从已有 .env 解析 MODE
      MODE="local"
      if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'face-scan-backend'; then
        MODE="docker"
      fi
    fi
    cmd_start
    ;;
  stop)
    if [ ! -f "$ENV_FILE" ] && [ ! -f "$COMPOSE_FILE" ]; then
      warn "未找到部署配置"
      exit 0
    fi
    cmd_stop
    ;;
  restart)
    if [ ! -f "$ENV_FILE" ] && [ ! -f "$COMPOSE_FILE" ]; then
      warn "未找到部署配置"
      exit 0
    fi
    cmd_restart
    ;;
  status)
    cmd_status
    ;;
  logs)
    cmd_logs "${2:-backend}"
    ;;
  clean)
    cmd_clean
    ;;
  *)
    echo "Face Scan 人脸识别门禁系统 — 部署管理工具"
    echo ""
    echo "用法: $0 <command> [options]"
    echo ""
    echo "命令:"
    echo "  start [--config]  启动服务 (--config 强制重新配置)"
    echo "  stop            停止服务"
    echo "  restart         重启服务"
    echo "  status          查看服务状态"
    echo "  logs [service]   查看日志 (backend/frontend/docker)"
    echo "  clean           清除所有数据（数据库、容器卷、人脸数据）"
    echo ""
    echo "示例:"
    echo "  $0 start              # 使用已有配置启动"
    echo "  $0 start --config      # 交互式配置后启动"
    echo "  $0 logs backend       # 查看后端日志"
    echo "  $0 clean              # 清除所有数据"
    echo ""
    ;;
esac
