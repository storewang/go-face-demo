# 05 - 集群部署改造方案

## 目标
将系统从单机单实例改造为支持多机集群部署，具备水平扩展和 K8s 弹性伸缩能力。

---

## 1. 数据库迁移：SQLite → PostgreSQL

### 现状
```python
# config.py
DATABASE_URL: str = "sqlite:///./data/face_scan.db"
```
SQLite 单文件数据库，不支持多进程并发写入，多实例会触发 `database is locked`。

### 改造方案
- 迁移到 PostgreSQL 15+
- 使用 SQLAlchemy 的 PostgreSQL dialect
- 利用 Alembic 管理迁移（见运维方案 03-operations.md）
- 连接池使用 `pg8000` 或 `asyncpg`（异步）

### 涉及文件
- `backend/app/config.py` — `DATABASE_URL` 改为 PostgreSQL 格式
- `backend/app/database.py` — 连接池配置调整
- `backend/requirements.txt` — 新增 `psycopg2-binary` 或 `asyncpg`
- `docker-compose.yml` — 新增 PostgreSQL 服务
- `backend/.env.example` — 新增 `DATABASE_URL` 示例

### 代码示例

```python
# config.py
DATABASE_URL: str = "postgresql+psycopg2://face:password@postgres:5432/facedb"

# database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # 每个实例的连接池大小
    max_overflow=20,        # 最大溢出连接数
    pool_timeout=30,
    pool_recycle=1800,      # 30分钟回收
    pool_pre_ping=True,     # 自动检测断连
)
```

```yaml
# docker-compose.yml
postgres:
  image: postgres:15-alpine
  container_name: face-scan-postgres
  restart: unless-stopped
  environment:
    POSTGRES_DB: facedb
    POSTGRES_USER: face
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  ports:
    - "5432:5432"
  volumes:
    - postgres-data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U face -d facedb"]
    interval: 10s
    timeout: 5s
    retries: 5

volumes:
  postgres-data:
```

### 迁移步骤
```bash
# 1. 导出 SQLite 数据
python scripts/export_sqlite.py > dump.sql

# 2. 启动 PostgreSQL
docker-compose up postgres

# 3. 导入数据（注意 SQLite 的自增序列需要重置）
psql -h localhost -U face -d facedb < dump.sql

# 4. 运行 Alembic 标记版本
alembic stamp head
```

---

## 2. JWT 无状态认证（跨节点共享）

### 现状
```python
# utils/auth.py
_active_tokens: Set[str] = set()  # 内存存储，实例间不共享
```

### 改造方案
- JWT 本身无状态，任何节点都能验证（详见 01-security.md）
- Token 黑名单（登出时）使用 **Redis Set** 共享
- 黑名单 TTL = Token 剩余有效期

### 涉及文件
- `backend/app/utils/auth.py` — 黑名单操作改用 Redis
- `backend/app/cache.py` — Redis 客户端

### 代码示例

```python
# utils/auth.py - 黑名单存 Redis
def revoke_token(token: str):
    """登出时将 Token 加入黑名单"""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    expire = payload.get("exp", 0)
    ttl = max(expire - int(time.time()), 0)
    if ttl > 0:
        redis_client.setex(f"token_blacklist:{token}", ttl, "1")

def is_token_blacklisted(token: str) -> bool:
    return redis_client.exists(f"token_blacklist:{token}")

def verify_token(token: str) -> Optional[dict]:
    if is_token_blacklisted(token):
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
```

---

## 3. 共享存储：本地文件 → MinIO/S3

### 现状
```python
# 人脸图片、编码、快照全部存本地磁盘
settings.IMAGES_DIR / "snapshots" / snapshot_filename
```
多实例时各节点文件不共享，A 节点注册的人脸图片 B 节点看不到。

### 改造方案
- 使用 **MinIO**（自建，兼容 S3 协议）或云厂商 OSS
- 人脸图片、编码文件、快照全部迁移到对象存储
- 通过预签名 URL 实现安全的文件访问

### 架构对比

| 方案 | 适用场景 | 成本 | 运维 |
|------|----------|------|------|
| MinIO（自建） | 内网部署、数据不出企业 | 低 | 中 |
| 阿里云 OSS | 阿里云生态 | 低 | 低 |
| AWS S3 | 海外/多云 | 中 | 低 |
| 腾讯云 COS | 腾讯云生态 | 低 | 低 |

### 涉及文件
- `backend/requirements.txt` — 新增 `minio` 或 `boto3`
- `backend/app/services/storage_service.py` — 新增存储抽象层
- `backend/app/services/face_service.py` — 注册/识别改用存储服务
- `backend/app/api/websocket.py` — 快照上传改用存储服务
- `backend/app/config.py` — 新增存储配置
- `docker-compose.yml` — 新增 MinIO 服务
- `backend/.env.example` — 新增存储配置

### 代码示例

```python
# services/storage_service.py
from minio import Minio
from minio.error import S3Error
import io

class StorageService:
    """对象存储抽象层，兼容 MinIO/S3/OSS"""

    def __init__(self):
        self.client = Minio(
            settings.S3_ENDPOINT,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_USE_SSL,
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        for bucket in ["faces", "encodings", "snapshots"]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    def upload_face_image(self, employee_id: str, image_bytes: bytes, content_type: str = "image/jpeg"):
        self.client.put_object(
            "faces", f"{employee_id}.jpg",
            io.BytesIO(image_bytes), len(image_bytes),
            content_type=content_type
        )

    def get_face_image(self, employee_id: str) -> bytes:
        response = self.client.get_object("faces", f"{employee_id}.jpg")
        return response.read()

    def upload_encoding(self, employee_id: str, encoding: np.ndarray):
        buf = io.BytesIO()
        np.save(buf, encoding)
        buf.seek(0)
        self.client.put_object(
            "encodings", f"{employee_id}.npy",
            buf, buf.getbuffer().nbytes,
            content_type="application/octet-stream"
        )

    def get_encoding(self, employee_id: str) -> np.ndarray:
        response = self.client.get_object("encodings", f"{employee_id}.npy")
        buf = io.BytesIO(response.read())
        return np.load(buf)

    def upload_snapshot(self, filename: str, image_bytes: bytes):
        self.client.put_object(
            "snapshots", filename,
            io.BytesIO(image_bytes), len(image_bytes),
            content_type="image/jpeg"
        )

    def get_presigned_url(self, bucket: str, object_name: str, expires: int = 3600) -> str:
        return self.client.presigned_get_object(bucket, object_name, expires=expires)


storage_service = StorageService()
```

```yaml
# docker-compose.yml
minio:
  image: minio/minio:latest
  container_name: face-scan-minio
  restart: unless-stopped
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: ${S3_ACCESS_KEY:-minioadmin}
    MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY:-minioadmin123}
  ports:
    - "9000:9000"   # API
    - "9001:9001"   # Console
  volumes:
    - minio-data:/data
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 10s
    timeout: 5s
    retries: 5

volumes:
  minio-data:
```

---

## 4. WebSocket 跨节点消息广播

### 现状
WebSocket 连接绑定在单个进程上，管理器使用内存字典：
```python
# websocket/manager.py
class ConnectionManager:
    active_connections: List[WebSocket] = []  # 仅当前进程
```

### 改造方案
使用 **Redis Pub/Sub** 实现跨节点消息广播：

```
客户端 A ──→ 节点1 ──→ Redis Pub/Sub ──→ 节点2 ──→ 客户端 B
客户端 C ──→ 节点3 ──↗                    ↘──→ 客户端 D
```

### 涉及文件
- `backend/app/websocket/manager.py` — 重写为 Redis Pub/Sub 模式
- `backend/app/api/websocket.py` — 适配新的 manager
- `backend/app/cache.py` — Redis Pub/Sub 工具

### 代码示例

```python
# websocket/manager.py
import asyncio
import json
import redis.asyncio as aioredis
from fastapi import WebSocket
from typing import Set, Dict

class ClusterConnectionManager:
    """支持集群的 WebSocket 连接管理器"""

    def __init__(self):
        # 本节点的连接（内存）
        self.local_connections: Dict[str, WebSocket] = {}  # client_id -> ws
        # Redis Pub/Sub
        self.redis_sub = None
        self.redis_pub = None
        self.channel_name = "ws:broadcast"

    async def init_redis(self, redis_url: str):
        """初始化 Redis Pub/Sub（应用启动时调用）"""
        self.redis = aioredis.from_url(redis_url)
        self.redis_sub = self.redis.pubsub()
        await self.redis_sub.subscribe(self.channel_name)
        asyncio.create_task(self._listen_broadcast())

    async def _listen_broadcast(self):
        """监听其他节点的广播消息"""
        async for message in self.redis_sub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                target_id = data.get("target_id")
                # 转发给本节点的连接
                if target_id and target_id in self.local_connections:
                    ws = self.local_connections[target_id]
                    try:
                        await ws.send_json(data["payload"])
                    except:
                        del self.local_connections[target_id]

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.local_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.local_connections.pop(client_id, None)

    async def send_json(self, client_id: str, data: dict):
        """发送消息（优先本节点，否则广播）"""
        if client_id in self.local_connections:
            await self.local_connections[client_id].send_json(data)
        else:
            # 通过 Redis 广播到其他节点
            await self.redis.publish(
                self.channel_name,
                json.dumps({"target_id": client_id, "payload": data})
            )

    async def broadcast(self, data: dict, exclude: str = None):
        """广播给所有连接（含跨节点）"""
        # 本节点
        for cid, ws in self.local_connections.items():
            if cid != exclude:
                try:
                    await ws.send_json(data)
                except:
                    pass
        # 其他节点
        await self.redis.publish(
            self.channel_name,
            json.dumps({"target_id": "__all__", "payload": data, "exclude": exclude})
        )


manager = ClusterConnectionManager()
```

---

## 5. 人脸特征库跨节点同步

### 现状
```python
class FaceService:
    def __init__(self):
        self.known_encodings = []  # 每个实例独立加载
        self.known_users = []
```
A 节点注册新人脸后，B 节点的特征库不会更新。

### 改造方案

### 方案 A：Redis 共享编码（推荐，< 10000 用户）
- 所有特征向量存储在 Redis Hash 中
- 注册/注销时通过 Redis Pub/Sub 通知所有节点刷新
- 节点启动时从 Redis 加载全量特征

### 方案 B：集中式 FAISS 服务（> 10000 用户）
- 独立部署 FAISS 微服务
- 所有节点通过 HTTP/gRPC 调用
- 详见 02-performance.md

### 方案 A 代码示例

```python
# services/face_service.py
import json
import redis.asyncio as aioredis
import numpy as np

class DistributedFaceService:
    """支持集群的人脸特征服务"""

    REDIS_KEY = "face:encodings"
    REDIS_USERS_KEY = "face:users"
    SYNC_CHANNEL = "face:sync"

    def __init__(self):
        self.known_encodings: List[np.ndarray] = []
        self.known_users: List[Dict] = []
        self.redis: aioredis.Redis = None
        self._sync_task = None

    async def init(self, redis_url: str):
        """启动时从 Redis 加载全量特征"""
        self.redis = aioredis.from_url(redis_url)
        await self._load_from_redis()
        # 启动同步监听
        self._sync_task = asyncio.create_task(self._listen_sync())

    async def _load_from_redis(self):
        """从 Redis 加载全量特征向量"""
        # 加载用户元数据
        users_json = await self.redis.hgetall(self.REDIS_USERS_KEY)
        self.known_users = [json.loads(v) for v in users_json.values()]

        # 加载特征向量
        encodings_data = await self.redis.hgetall(self.REDIS_KEY)
        self.known_encodings = []
        for user_id, enc_base64 in encodings_data.items():
            enc_bytes = base64.b64decode(enc_base64)
            encoding = np.frombuffer(enc_bytes, dtype=np.float64)
            self.known_encodings.append(encoding)

        log.info("faces_loaded_from_redis", count=len(self.known_encodings))

    async def _listen_sync(self):
        """监听特征变更事件"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.SYNC_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                if event["action"] == "add":
                    await self._add_face(event["user_id"], event["employee_id"])
                elif event["action"] == "remove":
                    await self._remove_face(event["user_id"])
                elif event["action"] == "reload":
                    await self._load_from_redis()

    async def register_face(self, user_id: int, employee_id: str, encoding: np.ndarray):
        """注册人脸并同步到所有节点"""
        # 存入 Redis
        enc_base64 = base64.b64encode(encoding.tobytes()).decode()
        await self.redis.hset(self.REDIS_KEY, str(user_id), enc_base64)
        await self.redis.hset(self.REDIS_USERS_KEY, str(user_id), json.dumps({...}))

        # 通知其他节点
        await self.redis.publish(
            self.SYNC_CHANNEL,
            json.dumps({"action": "add", "user_id": user_id, "employee_id": employee_id})
        )

        # 更新本地缓存
        await self._add_face(user_id, employee_id)
```

---

## 6. 负载均衡配置

### Nginx 配置

```nginx
# nginx/nginx.conf
upstream face_backend {
    least_conn;  # 最少连接数策略
    server backend-1:8000 max_fails=3 fail_timeout=30s;
    server backend-2:8000 max_fails=3 fail_timeout=30s;
    server backend-3:8000 max_fails=3 fail_timeout=30s;
}

# WebSocket 需要特殊处理
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name face.example.com;

    # API 请求
    location /api/ {
        proxy_pass http://face_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://face_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;  # WebSocket 长连接
        proxy_send_timeout 3600s;
    }

    # Prometheus 指标（内部访问）
    location /metrics {
        proxy_pass http://face_backend;
        allow 10.0.0.0/8;
        deny all;
    }
}
```

---

## 7. Kubernetes 部署配置

### Deployment 示例

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: face-scan-backend
  labels:
    app: face-scan-backend
spec:
  replicas: 3  # 初始3个副本
  selector:
    matchLabels:
      app: face-scan-backend
  template:
    metadata:
      labels:
        app: face-scan-backend
    spec:
      containers:
      - name: backend
        image: face-scan-backend:2.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: face-scan-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: face-scan-secrets
              key: jwt-secret
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: S3_ENDPOINT
          value: "http://minio-service:9000"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: face-scan-backend-service
spec:
  selector:
    app: face-scan-backend
  ports:
  - port: 8000
  targetPort: 8000
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: face-scan-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: face-scan-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: websocket_connections_active
      target:
        type: AverageValue
        averageValue: "50"  # 每个 Pod 最多 50 个 WebSocket 连接
```

### ConfigMap & Secret

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: face-scan-config
data:
  DEBUG: "false"
  FACE_THRESHOLD: "0.6"
  CORS_ORIGINS: '["https://face.example.com"]'
  REDIS_URL: "redis://redis-service:6379/0"
  S3_ENDPOINT: "http://minio-service:9000"
  S3_USE_SSL: "false"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: face-scan-secrets
type: Opaque
stringData:
  database-url: "postgresql+psycopg2://face:xxx@postgres-service:5432/facedb"
  jwt-secret: "your-random-secret-key"
  s3-access-key: "minioadmin"
  s3-secret-key: "minioadmin123"
```

---

## 8. 完整 docker-compose（集群模拟）

```yaml
# docker-compose.cluster.yml
version: "3.8"

services:
  # 负载均衡
  nginx:
    image: nginx:alpine
    container_name: face-scan-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      backend-1:
        condition: service_healthy
      backend-2:
        condition: service_healthy
      backend-3:
        condition: service_healthy

  # 后端实例 x3
  backend-1:
    build: ./backend
    container_name: face-scan-backend-1
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+psycopg2://face:${DB_PASSWORD}@postgres:5432/facedb
      REDIS_URL: redis://redis:6379/0
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  backend-2:
    <<: *backend-common
    container_name: face-scan-backend-2

  backend-3:
    <<: *backend-common
    container_name: face-scan-backend-3

  # 共享基础设施
  postgres:
    image: postgres:15-alpine
    container_name: face-scan-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: facedb
      POSTGRES_USER: face
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U face"]
      interval: 10s

  redis:
    image: redis:7-alpine
    container_name: face-scan-redis
    restart: unless-stopped
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  minio:
    image: minio/minio:latest
    container_name: face-scan-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY}
    volumes:
      - minio-data:/data
    ports:
      - "9001:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s

  prometheus:
    image: prom/prometheus:latest
    container_name: face-scan-prometheus
    restart: unless-stopped
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    container_name: face-scan-grafana
    restart: unless-stopped
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"

volumes:
  postgres-data:
  redis-data:
  minio-data:
  grafana-data:
```

---

## 改造优先级

| 序号 | 改造项 | 优先级 | 预估工时 | 风险 |
|------|--------|--------|----------|------|
| 1 | SQLite → PostgreSQL | 🔴 P0 | 2h | 中 |
| 2 | JWT 无状态认证 | 🔴 P0 | 1h | 低 |
| 3 | 本地文件 → MinIO/S3 | 🔴 P0 | 3h | 中 |
| 4 | Redis Pub/Sub 广播 | 🟡 P1 | 3h | 中 |
| 5 | 特征库跨节点同步 | 🟡 P1 | 4h | 高 |
| 6 | 负载均衡配置 | 🟡 P1 | 1h | 低 |
| 7 | K8s 部署配置 | 🟢 P2 | 2h | 低 |
| 8 | 集群 docker-compose | 🟢 P2 | 1h | 低 |

**总预估工时：17h**

---

## 与其他方案的关系

| 依赖项 | 来源方案 | 说明 |
|--------|----------|------|
| JWT 认证 | 01-security.md | 安全方案中已规划 |
| Redis 缓存 | 02-performance.md | 性能方案中已规划 |
| Alembic 迁移 | 03-operations.md | 运维方案中已规划 |
| FAISS 向量搜索 | 02-performance.md | 可选升级为集中式服务 |
| HTTPS 反向代理 | 01-security.md | 安全方案中已规划 |

> ⚠️ 建议先完成 Phase 1（安全）和 Phase 2（运维）后再开始集群改造，避免重复工作。

---

## 验收标准
- [ ] PostgreSQL 正常运行，数据迁移完成
- [ ] JWT Token 在任意节点都能验证
- [ ] 人脸图片在任意节点都能访问
- [ ] WebSocket 消息可跨节点推送
- [ ] 任一节点注册人脸，其他节点实时同步
- [ ] Nginx 负载均衡正常分发请求
- [ ] K8s HPA 可自动扩缩容（2-10 副本）
- [ ] 单节点宕机不影响系统整体可用性
