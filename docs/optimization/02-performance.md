# 02 - 性能优化方案

## 目标
优化系统性能瓶颈，支持 1000+ 用户场景，降低响应延迟。

---

## 1. 特征向量存储迁移

### 现状
```python
# face_service.py - 内存全量加载
class FaceService:
    def _load_known_faces(self):
        # 启动时从 .npy 文件加载所有用户特征到内存
        # 1000 用户 = 1000 × 128维 float64 = ~1MB，可接受
        # 10000 用户 = ~10MB，仍可接受但加载变慢
        # 100000 用户 = ~100MB，启动时间过长
```

### 短期方案（保持 .npy，优化加载）
- **增量加载**：启动时仅加载元数据索引，按需加载特征向量
- **延迟加载**：首次识别时才加载对应向量
- **预加载缓存**：高频用户常驻内存

### 中期方案（引入 FAISS）
- 使用 Facebook FAISS 库做向量相似度搜索
- 支持十万人级别的毫秒级检索
- 替换 `face_recognition.face_distance()` 为 FAISS `IndexFlatL2`

### 涉及文件
- `backend/requirements.txt` — 新增 `faiss-cpu`
- `backend/app/services/face_service.py` — 重写 `recognize_face()`
- `backend/app/services/encoding_store.py` — 新增向量存储抽象层

### 代码示例

```python
# services/encoding_store.py
import faiss
import numpy as np
from typing import List, Tuple, Optional, Dict

class FAISSFaceStore:
    """基于 FAISS 的高性能人脸特征向量存储"""

    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)  # 精确搜索
        self.user_map: Dict[int, int] = {}  # faiss_id -> user_info
        self.next_id = 0

    def add_face(self, user_id: int, employee_id: str, name: str,
                 department: str, encoding: np.ndarray):
        faiss_id = self.next_id
        self.index.add(np.array([encoding], dtype=np.float32))
        self.user_map[faiss_id] = {
            "id": user_id, "employee_id": employee_id,
            "name": name, "department": department
        }
        self.next_id += 1

    def search(self, encoding: np.ndarray, threshold: float = 0.6,
               top_k: int = 1) -> List[Tuple[Dict, float]]:
        encoding_f32 = np.array([encoding], dtype=np.float32)
        distances, indices = self.index.search(encoding_f32, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            user = self.user_map.get(int(idx))
            if user:
                confidence = 1 - float(dist)
                if confidence >= threshold:
                    results.append((user, confidence))
        return results

    def remove_face(self, user_id: int):
        # FAISS 不支持直接删除，需要重建索引
        # 对于小规模可以直接重建，大规模用 IndexIDMap
        pass

    def get_total_count(self) -> int:
        return self.index.ntotal
```

---

## 2. Redis 缓存层

### 现状
每次人脸识别、用户查询都直接访问 SQLite，无缓存。

### 改造方案
- 用户信息缓存（TTL 10分钟）
- 识别结果缓存（同一用户 3 秒内不重复查询）
- Session 缓存（WebSocket session 信息）
- Token 黑名单（登出时写入，TTL = Token 剩余有效期）

### 涉及文件
- `docker-compose.yml` — 新增 Redis 服务
- `backend/requirements.txt` — 新增 `redis[hiredis]`
- `backend/app/cache.py` — 新增 Redis 连接和缓存工具
- `backend/app/utils/auth.py` — Token 黑名单存 Redis
- `backend/app/api/users.py` — 用户查询走缓存
- `backend/app/services/face_service.py` — 识别结果缓存

### 代码示例

```python
# cache.py
import redis
from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

def cache_user(user_id: int, data: dict, ttl: int = 600):
    redis_client.setex(f"user:{user_id}", ttl, json.dumps(data))

def get_cached_user(user_id: int) -> Optional[dict]:
    data = redis_client.get(f"user:{user_id}")
    return json.loads(data) if data else None
```

```yaml
# docker-compose.yml 新增
redis:
  image: redis:7-alpine
  container_name: face-scan-redis
  restart: unless-stopped
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

volumes:
  redis-data:
```

---

## 3. WebSocket 帧处理优化

### 现状
```python
# 每 200ms 发送一帧，Base64 编码后传输
# 每帧 ~50-100KB（640x480 JPEG Base64）
# 带宽消耗：~500KB/s
# 处理瓶颈：每帧都要 Base64 解码 + 人脸检测
```

### 改造方案

**A. 帧采样优化**
- 客户端端降低帧率：200ms → 500ms（够用了）
- 服务端跳帧：如果上一帧还在处理，丢弃当前帧

**B. 图像压缩**
- 客户端压缩分辨率：640x480 → 320x240（人脸识别不需要高清）
- 使用 JPEG quality=70（默认 85）

**C. 帧缓冲批量处理**
- 累积帧时不每帧都做人脸检测
- 只对最后一帧做人脸检测，其他帧仅用于活体检测

### 涉及文件
- `frontend/src/views/Scan.vue` — 调整帧率、分辨率
- `frontend/src/composables/useCamera.ts` — 新增压缩参数
- `backend/app/api/websocket.py` — 跳帧逻辑、处理状态锁

### 代码示例

```typescript
// useCamera.ts - 降低帧率和分辨率
const CAPTURE_INTERVAL = 500  // 200ms -> 500ms
const CAPTURE_WIDTH = 320     // 降低分辨率
const CAPTURE_HEIGHT = 240
const JPEG_QUALITY = 0.7      // 压缩质量
```

```python
# websocket.py - 跳帧
class SessionState:
    def __init__(self):
        self.frames = []
        self.processing = False  # 处理锁

    def try_push_frame(self, frame):
        if self.processing:
            return False  # 正在处理，丢弃
        self.frames.append(frame)
        return True
```

---

## 4. 异步任务队列

### 现状
人脸注册时同步处理：检测 → 编码 → 保存 → 重新加载全部特征。用户量大时重新加载耗时长。

### 改造方案
- 使用 Celery + Redis 作为任务队列
- 人脸注册 → 异步任务（用户提交后立即返回，后台处理）
- Excel 导出 → 异步任务（导出完成后通知下载）
- 特征库重载 → 后台异步

### 涉及文件
- `docker-compose.yml` — 新增 Celery Worker 服务
- `backend/requirements.txt` — 新增 `celery[redis]`
- `backend/app/tasks.py` — 新增 Celery 任务定义
- `backend/app/api/face.py` — 注册改为异步
- `backend/app/api/attendance.py` — 导出改为异步

### 代码示例

```python
# tasks.py
from celery import Celery

celery_app = Celery("face_scan", broker=settings.CELERY_BROKER_URL)

@celery_app.task(bind=True, max_retries=3)
def async_register_face(self, user_id: int, image_data: str):
    try:
        face_service.register_face(user_id, image_data)
        return {"status": "success", "user_id": user_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)

@celery_app.task
def async_export_attendance(self, start_date: str, end_date: str, format: str):
    # 生成 Excel/PDF
    # 上传到临时存储
    # 返回下载链接
    pass
```

---

## 5. 数据库优化

### 现状
- SQLite 单文件数据库
- 无连接池配置
- 考勤查询无索引优化

### 改造方案

**A. 连接池优化**
```python
# database.py
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    echo=settings.DEBUG
)
```

**B. 索引优化**
```python
# models/attendance.py
class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    __table_args__ = (
        Index("idx_user_date", "user_id", "created_at"),
        Index("idx_created_at", "created_at"),
        Index("idx_employee_id", "employee_id"),
    )
```

**C. 查询优化**
- 考勤记录列表分页查询优化
- 今日打卡次数查询增加复合索引

### 涉及文件
- `backend/app/database.py` — 连接池配置
- `backend/app/models/attendance.py` — 添加索引
- `backend/app/models/user.py` — 添加索引

---

## 6. 启动优化

### 现状
服务启动时同步加载所有人脸特征向量，用户量大时启动慢。

### 改造方案
- 后台线程加载特征库，主服务先启动
- 加载进度通过 `/health` 端点暴露
- 健康检查在加载完成后才返回 healthy

### 代码示例

```python
import threading

class FaceService:
    def __init__(self):
        self.ready = False
        self.loading_thread = threading.Thread(target=self._load_async, daemon=True)
        self.loading_thread.start()

    def _load_async(self):
        self._load_known_faces()
        self.ready = True

    @property
    def health(self):
        return {
            "status": "healthy" if self.ready else "loading",
            "known_faces": len(self.known_encodings),
            "ready": self.ready
        }
```

---

## 改造优先级

| 序号 | 改造项 | 优先级 | 预估工时 | 风险 |
|------|--------|--------|----------|------|
| 1 | FAISS 向量搜索 | 🟡 P1 | 3h | 中 |
| 2 | Redis 缓存层 | 🟡 P1 | 2h | 低 |
| 3 | WebSocket 帧优化 | 🟢 P2 | 1.5h | 低 |
| 4 | 异步任务队列 | 🟢 P2 | 3h | 中 |
| 5 | 数据库优化 | 🟢 P2 | 1h | 低 |
| 6 | 启动优化 | 🟢 P2 | 1h | 低 |

**总预估工时：11.5h**

---

## 验收标准
- [ ] 1000 用户人脸识别延迟 < 200ms
- [ ] Redis 缓存命中率 > 80%
- [ ] WebSocket 带宽消耗降低 50%
- [ ] 人脸注册响应时间 < 500ms（异步）
- [ ] 服务启动时间 < 5s（特征库后台加载）
- [ ] 考勤记录查询（1万条）< 100ms
