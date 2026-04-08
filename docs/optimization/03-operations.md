# 03 - 运维改进方案

## 目标
建立生产级可观测性和运维自动化，提升系统可维护性。

---

## 1. 结构化日志

### 现状
```python
print(f"✅ Loaded {len(self.known_encodings)} known faces")
print(f"Error processing frame: {e}")
print(f"WebSocket error: {e}")
```
使用 `print` 输出，无日志级别，无结构化格式，难以检索和分析。

### 改造方案
- 使用 Python `logging` + `structlog` 实现结构化 JSON 日志
- 日志级别：DEBUG / INFO / WARNING / ERROR / CRITICAL
- 按模块分 logger：`app.api`, `app.services`, `app.websocket`
- 支持输出到 stdout（Docker 友好）和文件

### 涉及文件
- `backend/requirements.txt` — 新增 `structlog`
- `backend/app/logging_config.py` — 新增日志配置
- `backend/app/main.py` — 初始化日志
- 所有使用 `print` 的文件 — 替换为 logger 调用

### 代码示例

```python
# logging_config.py
import structlog
import logging

def setup_logging(debug: bool = False):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# 使用
log = structlog.get_logger()
log.info("faces_loaded", count=len(encodings))
log.error("frame_process_error", error=str(e), websocket_id=id)
```

### 日志输出示例
```json
{"event": "faces_loaded", "count": 42, "level": "info", "timestamp": "2024-01-15T10:30:00Z"}
{"event": "face_recognized", "user": "张三", "confidence": 0.95, "level": "info", "timestamp": "..."}
{"event": "frame_process_error", "error": "Connection reset", "level": "error", "timestamp": "..."}
```

---

## 2. 数据库迁移工具（Alembic）

### 现状
使用 `init_db.py` 脚本手动建表，无版本管理。数据库 schema 变更需要手动处理。

### 改造方案
- 引入 Alembic 管理数据库版本
- 初始化迁移历史
- 后续所有 schema 变更通过 migration 文件管理
- 支持 upgrade / downgrade

### 涉及文件
- `backend/requirements.txt` — 新增 `alembic`
- 新增 `backend/alembic.ini`
- 新增 `backend/alembic/` 目录（env.py, versions/）
- `backend/app/models/` — 确保 Base 声明正确

### 初始化步骤
```bash
cd backend
alembic init alembic
# 编辑 alembic/env.py，导入所有 models
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### 后续 schema 变更
```bash
alembic revision --autogenerate -m "add phone field to user"
alembic upgrade head
# 回滚
alembic downgrade -1
```

---

## 3. Prometheus 指标监控

### 现状
无任何监控指标，无法了解系统运行状态。

### 改造方案

### 监控指标设计

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `face_recognition_total` | Counter | 人脸识别请求总数 |
| `face_recognition_success_total` | Counter | 识别成功数 |
| `face_recognition_duration_seconds` | Histogram | 识别耗时分布 |
| `face_register_total` | Counter | 人脸注册请求总数 |
| `liveness_check_total` | Counter | 活体检测次数 |
| `liveness_check_passed_total` | Counter | 活体通过次数 |
| `websocket_connections_active` | Gauge | 当前 WebSocket 连接数 |
| `attendance_records_total` | Counter | 考勤记录总数 |
| `known_faces_count` | Gauge | 已注册人脸数 |
| `api_request_duration_seconds` | Histogram | API 请求耗时 |
| `api_request_total` | Counter | API 请求总数（按路径、方法、状态码） |

### 涉及文件
- `backend/requirements.txt` — 新增 `prometheus-fastapi-instrumentator`
- `backend/app/main.py` — 注册 Prometheus 中间件
- `backend/app/services/face_service.py` — 识别指标埋点
- `backend/app/api/websocket.py` — WebSocket 连接数指标
- 新增 `docker-compose.yml` — Prometheus + Grafana 服务
- 新增 `prometheus/prometheus.yml`
- 新增 `grafana/provisioning/` — Dashboard 配置

### 代码示例

```python
# main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# face_service.py
from prometheus_client import Counter, Histogram

FACE_RECOG_TOTAL = Counter("face_recognition_total", "Total face recognition attempts")
FACE_RECOG_SUCCESS = Counter("face_recognition_success_total", "Successful recognitions")
FACE_RECOG_DURATION = Histogram("face_recognition_duration_seconds", "Recognition duration")

def recognize_face(self, encoding):
    FACE_RECOG_TOTAL.inc()
    with FACE_RECOG_DURATION.time():
        # ... 识别逻辑
        if user:
            FACE_RECOG_SUCCESS.inc()
```

```yaml
# docker-compose.yml 新增
prometheus:
  image: prom/prometheus:latest
  container_name: face-scan-prometheus
  restart: unless-stopped
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
  depends_on:
    - backend

grafana:
  image: grafana/grafana:latest
  container_name: face-scan-grafana
  restart: unless-stopped
  ports:
    - "3000:3000"
  volumes:
    - grafana-data:/var/lib/grafana
    - ./grafana/provisioning:/etc/grafana/provisioning
  depends_on:
    - prometheus
```

---

## 4. 健康检查增强

### 现状
```python
@app.get("/health")
def health_check():
    return {"status": "healthy"}
```
仅返回固定字符串，不检查实际依赖状态。

### 改造方案
- 检查数据库连接
- 检查 Redis 连接
- 检查人脸特征库加载状态
- 检查磁盘空间
- 区分 liveness（就绪）和 readiness（可用）

### 涉及文件
- `backend/app/api/health.py` — 新增健康检查路由
- `backend/app/main.py` — 替换原有 health 端点

### 代码示例

```python
# api/health.py
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["健康检查"])

@router.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "face_service": check_face_service(),
        "disk": check_disk_space(),
    }

    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "version": "2.0.0"
        }
    )

@router.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe - 仅检查关键依赖"""
    db_ok = await check_database()
    return {"ready": db_ok["status"] == "healthy"}
```

---

## 5. Docker 镜像优化

### 现状
- 单阶段构建
- 每次构建下载所有依赖
- 镜像体积大（含 dlib 编译工具）

### 改造方案
- 多阶段构建（编译阶段 + 运行阶段）
- 利用 Docker 层缓存（先复制 requirements.txt，再安装依赖）
- dlib 预编译 wheel 或使用官方镜像

### 涉及文件
- `backend/Dockerfile` — 重写为多阶段构建
- `frontend/Dockerfile` — 优化前端构建

### 代码示例

```dockerfile
# backend/Dockerfile - 多阶段构建
# 阶段1: 编译 dlib 和安装依赖
FROM python:3.10-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 阶段2: 运行时镜像
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["python", "run.py"]
```

---

## 6. 自动化备份

### 现状
无数据备份策略，SQLite 数据库损坏即丢失所有数据。

### 改造方案
- 每日自动备份数据库和人脸图片到压缩包
- 保留最近 7 天备份
- 备份脚本集成到 Docker
- 支持手动触发备份

### 涉及文件
- 新增 `backend/scripts/backup.sh`
- `docker-compose.yml` — 新增 backup cron 服务或定时任务

### 代码示例

```bash
#!/bin/bash
# scripts/backup.sh
BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

mkdir -p $BACKUP_DIR

# 备份数据库
sqlite3 /app/data/face_scan.db ".backup $BACKUP_DIR/db_${TIMESTAMP}.db"

# 打包人脸数据
tar czf $BACKUP_DIR/faces_${TIMESTAMP}.tar.gz -C /app/data faces/

# 清理旧备份
find $BACKUP_DIR -name "*.db" -mtime +$KEEP_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$KEEP_DAYS -delete

echo "Backup completed: $TIMESTAMP"
```

---

## 改造优先级

| 序号 | 改造项 | 优先级 | 预估工时 | 风险 |
|------|--------|--------|----------|------|
| 1 | 结构化日志 | 🔴 P0 | 2h | 低 |
| 2 | 数据库迁移 | 🔴 P0 | 1.5h | 低 |
| 3 | 健康检查增强 | 🟡 P1 | 1h | 低 |
| 4 | Prometheus 监控 | 🟡 P1 | 3h | 中 |
| 5 | Docker 优化 | 🟢 P2 | 1h | 低 |
| 6 | 自动化备份 | 🟢 P2 | 1.5h | 低 |

**总预估工时：10h**

---

## 验收标准
- [ ] 所有 `print` 替换为结构化 logger
- [ ] 日志输出 JSON 格式，包含 timestamp + level + event
- [ ] Alembic migration 正常运行 upgrade/downgrade
- [ ] `/health` 返回各组件真实状态
- [ ] Prometheus `/metrics` 端点可访问
- [ ] Grafana Dashboard 展示核心指标
- [ ] Docker 镜像体积减少 30%
- [ ] 每日自动备份可正常执行和清理
