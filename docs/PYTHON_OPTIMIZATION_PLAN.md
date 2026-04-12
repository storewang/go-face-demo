# Python 版 (go-face-demo) 优化改造方案

> **基于版本**: v2.1.0 (main 分支, commit 71b1e16)
> **编制日期**: 2026-04-11
> **前提说明**: Phase 1-5（安全/运维/性能/功能/集群）已全部落地。本文档针对 **当前代码中仍存在的问题** 给出后续改造方案。

---

## 目录

- [改造全景图](#改造全景图)
- [阶段一：核心算法升级（高价值）](#阶段一核心算法升级高价值)
- [阶段二：代码质量与可靠性](#阶段二代码质量与可靠性)
- [阶段三：性能与扩展性](#阶段三性能与扩展性)
- [阶段四：安全加固（增量）](#阶段四安全加固增量)
- [阶段五：用户体验与前端](#阶段五用户体验与前端)
- [实施计划总览](#实施计划总览)

---

## 改造全景图

```
当前状态 (v2.1.0)                          改造目标 (v3.0.0)
─────────────────────                      ─────────────────────
dlib 128维特征              ──→  ArcFace 512维 (精度↑, 安装↓)
特征 .npy 文件本地存储        ──→  MinIO 对象存储 (集群就绪)
线性匹配 O(N)               ──→  FAISS 向量索引 O(logN)
Alembic 空(无迁移)          ──→  完整迁移链
WS process_frame 重复逻辑    ──→  统一调用 verify_user
Excel 全内存导出             ──→  流式写入
活体检测(眨眼+点头)          ──→  增强方案
单 IP 无 WS 连接限制         ──→  Nginx 限流
无 E2E 测试                 ──→  关键路径 E2E
```

---

## 阶段一：核心算法升级（高价值）

### 1.1 特征提取：dlib → InsightFace/ArcFace

**当前问题**:
- dlib 安装极困难（CMake + C++ 编译），是部署的头号障碍
- 128 维特征精度有限，侧脸/光照/遮挡场景误识别率高于 ArcFace
- face_recognition 库底层是 dlib HOG + CNN，并非 SOTA
- 与 Java 版的 ArcFace 512 维特征不兼容，两套系统无法共享特征库

**目标**: 迁移到 InsightFace (ArcFace)，统一为 512 维特征向量。

**涉及文件**:
- `backend/requirements.txt` — 移除 `face-recognition`, `dlib`; 新增 `insightface`, `onnxruntime`
- `backend/app/services/face_service.py` — **核心重写**：检测器、编码器、匹配器
- `backend/app/utils/face_utils.py` — 质量评估保留，编码相关替换
- `backend/app/services/liveness_service.py` — 关键点来源改为 InsightFace 5点/106点
- `backend/app/config.py` — 新增 `FACE_MODEL_NAME`, `FACE_DEVICE` 等配置
- `backend/Dockerfile` — 移除 dlib 编译依赖，简化构建
- `backend/app/init_db.py` — 提供旧特征迁移脚本

**改造前 (face_service.py)**:
```python
import face_recognition

class FaceService:
    def detect_faces(self, image):
        # YuNet/SSD 检测 → face_recognition.face_encodings 编码 (128d)
        encodings = face_recognition.face_encodings(image, locations)
        
    def recognize_face(self, encoding):
        distances = face_recognition.face_distance(self.known_encodings, encoding)
        min_idx = np.argmin(distances)
        confidence = 1 - min_distance
```

**改造后 (face_service.py)**:
```python
import insightface
from insightface.app import FaceAnalysis

class FaceService:
    def __init__(self):
        self._face_app = FaceAnalysis(
            name="buffalo_l",           # 含 SCRFD检测 + ArcFace识别 + 关键点
            providers=["CPUExecutionProvider"]  # 或 CUDAExecutionProvider
        )
        self._face_app.prepare(ctx_id=0, det_size=(640, 640))
        self.dimension = 512  # ArcFace 512 维
        
    def detect_faces(self, image: np.ndarray) -> List[Dict]:
        """检测人脸并提取特征 (一步完成)"""
        faces = self._face_app.get(image)
        
        results = []
        for face in faces:
            bbox = face.bbox.astype(int)  # [x1, y1, x2, y2]
            # 转为 face_recognition 兼容格式 (top, right, bottom, left)
            location = (int(bbox[1]), int(bbox[2]), int(bbox[3]), int(bbox[0]))
            
            quality = FaceUtils.get_face_quality(image, location)
            results.append({
                "box": location,
                "encoding": face.embedding,  # 512 维 ArcFace 特征
                "quality": quality,
                "landmark": face.kps,  # 5 个关键点
                "det_score": float(face.det_score),
            })
        return results
    
    def recognize_face(self, encoding: np.ndarray) -> Tuple[Optional[Dict], float]:
        """余弦相似度匹配 (512 维)"""
        if not self.known_encodings:
            return None, 0.0
        
        # numpy 向量化余弦相似度
        known = np.array(self.known_encodings)
        norm_known = known / np.linalg.norm(known, axis=1, keepdims=True)
        norm_query = encoding / np.linalg.norm(encoding)
        
        similarities = norm_known @ norm_query
        max_idx = np.argmax(similarities)
        confidence = float(similarities[max_idx])
        
        if confidence >= self.threshold:
            return self.known_users[max_idx], confidence
        return None, confidence
```

**旧特征迁移脚本**:
```python
# backend/scripts/migrate_encodings.py
"""
将 dlib 128d 编码迁移为 ArcFace 512d
运行方式: python -m scripts.migrate_encodings
"""
import os
import cv2
import numpy as np
from app.database import SessionLocal
from app.models import User
from app.services.face_service import FaceService

def migrate():
    face_svc = FaceService()
    # 等待模型加载完成
    import time
    while not face_svc.ready:
        time.sleep(1)
    
    db = SessionLocal()
    users = db.query(User).filter(User.face_image_path.isnot(None)).all()
    
    migrated, failed = 0, 0
    for user in users:
        try:
            image = cv2.imread(user.face_image_path)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            faces = face_svc.detect_faces(image)
            if len(faces) == 1:
                encoding = faces[0]["encoding"]
                encoding_path = user.face_encoding_path  # 覆盖旧文件
                np.save(encoding_path, encoding)
                migrated += 1
                print(f"✅ {user.employee_id} ({user.name}) 迁移成功")
            else:
                failed += 1
                print(f"❌ {user.employee_id} 检测到 {len(faces)} 张脸，跳过")
        except Exception as e:
            failed += 1
            print(f"❌ {user.employee_id} 迁移失败: {e}")
    
    db.close()
    print(f"\n迁移完成: 成功 {migrated}, 失败 {failed}")

if __name__ == "__main__":
    migrate()
```

**Dockerfile 简化**:
```dockerfile
# 改造前: 需要 cmake + build-essential 编译 dlib (~15min)
# 改造后: 只需 pip install insightface onnxruntime

FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["python", "run.py"]
```

**验收标准**:
- [ ] `pip install` 无需 CMake/C++ 编译器
- [ ] 特征维度从 128 提升到 512
- [ ] 旧用户特征通过迁移脚本自动升级
- [ ] Docker 构建时间缩短 >50%
- [ ] 识别精度在相同测试集上提升 ≥5%

**预估工时**: 1-2 天

---

### 1.2 活体检测增强

**当前问题**:
- 仅支持眨眼 (EAR) + 点头 (pitch)，依赖 dlib 68 点模型
- 迁移到 InsightFace 后，dlib 的 68 点模型不再可用
- 无法防高清屏幕/视频回放攻击

**目标**: 基于 InsightFace 关键点重写活体检测，并增加辅助策略。

**涉及文件**:
- `backend/app/services/liveness_service.py` — **重写**
- `backend/app/config.py` — 新增 `LIVENESS_MODE` 配置

**改造方案**:

```python
# liveness_service.py — 基于 InsightFace 关键点重写
class LivenessService:
    """
    活体检测策略:
    1. 眨眼检测 (EAR) — 使用 InsightFace 5 点中的眼睛关键点
    2. 头部运动检测 — 使用 InsightFace 5 点估算 pitch/yaw
    3. 时序一致性 — 连续帧特征相似度检查（防静态照片）
    4. 质量门控 — 模糊/过曝/过暗帧直接拒绝
    """
    
    def __init__(self, required_frames: int = 3):  # 5 → 3 帧，降低等待
        self.required_frames = required_frames
        self.ear_threshold = 0.2
        self.pitch_threshold = 12  # 15 → 12，更灵敏
        self.consistency_threshold = 0.95  # 帧间特征相似度
        
    def get_landmarks_from_insightface(self, face_result) -> np.ndarray:
        """从 InsightFace Face 对象提取关键点"""
        return face_result.kps  # shape: (5, 2)
        # 点位: 0=左眼, 1=右眼, 2=鼻尖, 3=左嘴角, 4=右嘴角
        
    def calculate_ear_v2(self, landmarks: np.ndarray) -> float:
        """基于 5 点的近似 EAR (仅有左右眼中心点，需要辅助估算)"""
        left_eye = landmarks[0]
        right_eye = landmarks[1]
        nose = landmarks[2]
        
        # 用眼鼻距离比例估算眼睛开合度
        left_dist = np.linalg.norm(left_eye - nose)
        right_dist = np.linalg.norm(right_eye - nose)
        
        # 眼距与鼻距的比值作为替代指标
        eye_dist = np.linalg.norm(left_eye - right_eye)
        ratio = eye_dist / (left_dist + right_dist + 1e-6)
        return ratio
    
    def check_temporal_consistency(self, encodings: List[np.ndarray]) -> bool:
        """时序一致性检查 — 防止静态照片被识别为活体"""
        if len(encodings) < 2:
            return False
            
        for i in range(1, len(encodings)):
            sim = np.dot(encodings[i], encodings[i-1]) / (
                np.linalg.norm(encodings[i]) * np.linalg.norm(encodings[i-1]) + 1e-6
            )
            if sim < self.consistency_threshold:
                return True  # 帧间有变化，可能是活体
        
        return False  # 所有帧几乎相同，可能是静态照片
    
    def check_liveness(self, face_results: list) -> Dict:
        """
        活体检测入口
        face_results: List[insightface Face 对象]
        """
        if len(face_results) < self.required_frames:
            return {"passed": False, "message": f"需要 {self.required_frames} 帧"}
        
        # 检查 1: 眨眼
        blink = self._check_blink(face_results)
        
        # 检查 2: 头部运动
        nod = self._check_head_movement(face_results)
        
        # 检查 3: 时序一致性 (防照片)
        encodings = [f.embedding for f in face_results if f.embedding is not None]
        consistency = self.check_temporal_consistency(encodings)
        
        passed = blink or nod  # 任一通过即可
        message = "活体检测通过" if passed else "请眨眼或轻微转头"
        
        return {
            "passed": passed,
            "blink_detected": blink,
            "nod_detected": nod,
            "temporal_consistent": consistency,
            "message": message,
        }
```

**验收标准**:
- [ ] 不依赖 dlib 68 点模型
- [ ] 眨眼+点头检测正常工作
- [ ] 新增时序一致性检查（防静态照片）
- [ ] 活体检测帧数从 5 降至 3

**预估工时**: 0.5-1 天

---

## 阶段二：代码质量与可靠性

### 2.1 完成 Alembic 数据库迁移

**当前问题**: `alembic/versions/` 为空，生产环境升级无法安全执行。

**涉及文件**:
- `backend/alembic/versions/` — 新增迁移文件

**操作步骤**:
```bash
cd backend

# 1. 生成 v2.1.0 初始 schema 快照
alembic revision --autogenerate -m "v2.1.0 initial schema: users, attendance_logs, devices, system_config"

# 2. 标记当前数据库为最新（已有数据的情况）
alembic stamp head

# 3. 后续变更流程
# 修改 model → 生成迁移 → 审查 → 应用
alembic revision --autogenerate -m "add user phone field"
alembic upgrade head
```

**验收标准**:
- [ ] `alembic/versions/` 包含初始迁移文件
- [ ] 新数据库可通过 `alembic upgrade head` 建表
- [ ] 现有数据库通过 `alembic stamp head` 兼容

**预估工时**: 1 小时

---

### 2.2 统一 WebSocket 识别流程

**当前问题**: `websocket.py` 的 `process_frame()` 手动组装了 检测→质量→活体→识别 全流程，而 `face_service.verify_user()` 已有完整封装（含 Prometheus 埋点）。两套逻辑不同步，后续改一处漏一处。

**涉及文件**:
- `backend/app/api/websocket.py` — 重构 `process_frame`

**改造前 (websocket.py process_frame, 70+ 行逻辑)**:
```python
async def process_frame(websocket, frame_data, session):
    # 1. 解码图片
    # 2. detect_faces → 检查数量
    # 3. 检查质量
    # 4. 累积帧 → 活体检测
    # 5. recognize_face → 匹配
    # 6. 保存快照 → 写 AttendanceLog
    # 7. 通知推送
    # ... 与 verify_user 重复的逻辑
```

**改造后**:
```python
async def process_frame(websocket, frame_data, session):
    if session.get("processing", False):
        return
    session["processing"] = True
    
    try:
        image_bytes = base64.b64decode(frame_data)
        image = FaceUtils.load_image_from_bytes(image_bytes)
        
        # === 阶段 1: 活体检测 (累积帧) ===
        faces = face_service.detect_faces(image)
        
        if len(faces) == 0:
            await _send_status(websocket, "detecting", "未检测到人脸")
            return
        if len(faces) > 1:
            await _send_status(websocket, "detecting", "检测到多张人脸")
            return
        if faces[0]["quality"] == "poor":
            await _send_status(websocket, "quality_check", "请调整光线")
            return
        
        session["frames"].append(image)
        session["face_results"].append(faces[0])
        
        if len(session["frames"]) < FRAME_BUFFER_SIZE:
            await _send_status(websocket, "liveness_check",
                f"请保持不动 ({len(session['frames'])}/{FRAME_BUFFER_SIZE})")
            return
        
        # 活体检测
        liveness = _check_liveness(session["face_results"])
        if not liveness["passed"]:
            await _send_status(websocket, "liveness_check", liveness["message"])
            _clear_buffers(session)
            return
        
        # === 阶段 2: 复用 FaceService 统一识别流程 ===
        result = face_service.verify_user(image)
        
        if not result["success"]:
            await _send_result(websocket, False, reason=result["reason"])
            _clear_buffers(session)
            return
        
        # === 阶段 3: 考勤记录 (WS 特有逻辑) ===
        user = result["user"]
        confidence = result["confidence"]
        action_type, record = await _record_attendance(session, user, confidence, image)
        
        await _send_result(websocket, True, user=user, confidence=confidence,
                          action_type=action_type, device_name=session.get("device_name"))
        _clear_buffers(session)
        
    except Exception as e:
        log.error("frame_process_error", error=str(e))
        await _send_error(websocket, str(e))
    finally:
        session["processing"] = False
```

**收益**: Prometheus 埋点自动生效，逻辑统一，后续只需维护 `verify_user` 一处。

**验收标准**:
- [ ] WebSocket 识别走 `face_service.verify_user()` 统一入口
- [ ] Prometheus 指标自动覆盖 WS 识别路径
- [ ] 功能行为不变（活体→识别→打卡）

**预估工时**: 3 小时

---

### 2.3 集成 MinIO 对象存储

**当前问题**: `storage_service.py` 已封装 MinIO/本地 双模式，但 `face_service.py` 仍直接使用本地文件路径。

**涉及文件**:
- `backend/app/services/face_service.py` — 替换本地文件操作
- `backend/app/services/storage_service.py` — 确认接口完备
- `backend/app/config.py` — 确认 S3 配置项

**改造要点**:
```python
# face_service.py 改造

from app.services.storage_service import storage_service

class FaceService:
    def register_face(self, user_id, image, db):
        # ... 检测 + 质量检查 ...
        
        # 改造前: 本地文件
        # np.save(str(encoding_path), face["encoding"])
        # cv2.imwrite(str(image_path), image_bgr)
        
        # 改造后: 通过存储服务抽象层
        encoding_bytes = face["encoding"].tobytes()
        storage_service.save_encoding(user.employee_id, encoding_bytes)
        
        image_success = storage_service.save_face_image(
            user.employee_id, 
            cv2.imencode('.jpg', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))[1].tobytes()
        )
        
        # DB 存储引用路径 (本地模式: 文件路径 / MinIO模式: 对象key)
        user.face_encoding_path = storage_service.get_encoding_path(user.employee_id)
        user.face_image_path = storage_service.get_face_image_path(user.employee_id)
        db.commit()
    
    def _load_known_faces(self):
        users = db.query(User).filter(...).all()
        for user in users:
            # 通过存储服务读取，自动适配本地/MinIO
            encoding_bytes = storage_service.load_encoding(
                os.path.basename(user.face_encoding_path)
            )
            if encoding_bytes:
                encoding = np.frombuffer(encoding_bytes, dtype=np.float32)
                self.known_encodings.append(encoding)
                self.known_users.append({...})
```

**验收标准**:
- [ ] 单机模式(S3未配置): 仍使用本地文件，行为不变
- [ ] 集群模式(S3已配置): 人脸数据自动存 MinIO
- [ ] `docker-compose.cluster.yml` 中 MinIO 可正常工作

**预估工时**: 4 小时

---

### 2.4 Excel 导出流式优化

**当前问题**: `export_service.py` 将所有记录加载到内存再生成 Excel。万条记录可能 OOM。

**涉及文件**:
- `backend/app/services/export_service.py` — 改用 write_only 模式

**改造方案**:
```python
from openpyxl import Workbook
from openpyxl.writer.excel import save_workbook

class ExportService:
    @staticmethod
    def export_attendance_to_excel(records, start_date=None, end_date=None):
        output = BytesIO()
        
        # 使用 write_only 模式, 内存占用恒定
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("考勤记录")
        
        # 写表头
        ws.append(["记录ID", "工号", "姓名", "类型", "置信度", "结果", "时间"])
        
        # 逐条写入, 不需要全量 DataFrame
        for record in records:
            ws.append([
                record.id,
                record.employee_id or "",
                record.name or "",
                "上班" if record.action_type == "CHECK_IN" else "下班",
                f"{record.confidence:.2f}" if record.confidence else "",
                "成功" if record.result == "SUCCESS" else "失败",
                record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
            ])
        
        save_workbook(wb, output)
        output.seek(0)
        return output
```

**验收标准**:
- [ ] 万条记录导出内存占用 < 100MB
- [ ] 导出文件格式不变

**预估工时**: 1 小时

---

## 阶段三：性能与扩展性

### 3.1 FAISS 向量索引

**当前问题**: `face_recognition.face_distance()` 线性遍历 O(N)。当前 <50 人可接受，但向集群扩展时需优化。

**触发条件**: 注册用户超过 200 人时实施。

**涉及文件**:
- `backend/requirements.txt` — 新增 `faiss-cpu`
- `backend/app/services/face_service.py` — 新增 FAISS 索引

**改造方案**:
```python
import faiss

class FaceService:
    def __init__(self):
        self.faiss_index = None
        self.dimension = 512  # ArcFace 维度
        
    def _build_faiss_index(self):
        """构建 FAISS 索引"""
        if not self.known_encodings:
            return
        
        encodings = np.array(self.known_encodings).astype('float32')
        
        # 使用内积索引 (配合 L2 归一化 = 余弦相似度)
        self.faiss_index = faiss.IndexFlatIP(self.dimension)
        
        # L2 归一化
        faiss.normalize_L2(encodings)
        self.faiss_index.add(encodings)
        
        log.info("faiss_index_built", count=self.faiss_index.ntotal)
    
    def recognize_face(self, encoding: np.ndarray):
        if self.faiss_index is None or self.faiss_index.ntotal == 0:
            return None, 0.0
        
        # FAISS 搜索
        query = np.array([encoding]).astype('float32')
        faiss.normalize_L2(query)
        
        similarities, indices = self.faiss_index.search(query, 1)
        
        confidence = float(similarities[0][0])
        idx = int(indices[0][0])
        
        if confidence >= self.threshold and idx >= 0:
            return self.known_users[idx], confidence
        return None, confidence
    
    def reload_faces(self, db):
        self.known_encodings = []
        self.known_users = []
        self._load_known_faces_from_db(db)
        self._build_faiss_index()  # 重建索引
```

**性能对比**:
| 用户数 | 当前 (线性) | FAISS | 提升 |
|--------|------------|-------|------|
| 50 | ~2ms | ~0.5ms | 4x |
| 500 | ~20ms | ~1ms | 20x |
| 5000 | ~200ms | ~3ms | 67x |

**验收标准**:
- [ ] 500 用户识别延迟 < 5ms
- [ ] 特征注册后自动重建索引

**预估工时**: 3 小时

---

### 3.2 Nginx WebSocket 连接限流

**当前问题**: 单 IP 可无限建立 WebSocket 连接，存在资源耗尽风险。

**涉及文件**:
- `nginx/nginx.conf` — 添加限流配置

**改造方案**:
```nginx
# nginx.conf
limit_conn_zone $binary_remote_addr zone=ws_limit:10m;
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

upstream face_backend {
    least_conn;
    server backend-1:8000;
    server backend-2:8000;
    server backend-3:8000;
}

server {
    # API 限流
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://face_backend;
    }
    
    # WebSocket 连接数限制
    location /ws/face-stream {
        proxy_pass http://face_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 单 IP 最多 5 个 WS 连接
        limit_conn ws_limit 5;
        
        # WS 超时
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

**验收标准**:
- [ ] 单 IP 超过 5 个 WS 连接时新连接被拒绝
- [ ] API 限流 30r/s 生效

**预估工时**: 1 小时

---

## 阶段四：安全加固（增量）

### 4.1 统计接口查询优化

**当前问题**: `/api/statistics/trend` 365 天模式会扫描大量数据，虽然已用数据库聚合，但可进一步优化。

**涉及文件**:
- `backend/app/api/statistics.py` — 添加查询限制

**改造方案**:
```python
@router.get("/trend", summary="考勤趋势")
async def attendance_trend(
    days: int = Query(30, ge=1, le=90, description="统计天数(最大90)"),  # 限制上限
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # 添加缓存 (5 分钟 TTL)
    cache_key = f"stats:trend:{days}"
    cached = redis_client.get_json(cache_key)
    if cached:
        return cached
    
    # ... 现有查询逻辑 ...
    
    result = {"days": days, "total_employees": total, "trend": trend}
    redis_client.set_json(cache_key, result, settings.CACHE_STATS_TTL)  # 300s
    return result
```

**验收标准**:
- [ ] 趋势查询天数限制为 90
- [ ] 结果缓存 5 分钟

**预估工时**: 1 小时

---

### 4.2 WebSocket 心跳超时检测

**当前问题**: WebSocket 连接断开后服务端不会主动清理死连接。

**涉及文件**:
- `backend/app/api/websocket.py` — 添加心跳超时

**改造方案**:
```python
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session = manager.get_session(websocket)
    
    try:
        while True:
            # 添加接收超时 (30 秒)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.close(code=4000, reason="Heartbeat timeout")
                break
            
            message = json.loads(data)
            
            if message.get("type") == "ping":
                session["last_ping"] = datetime.now().timestamp()
                await manager.send_json(websocket, {"type": "pong"})
            elif message.get("type") == "frame":
                # ... 
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
        log.info("ws_disconnected", active=len(manager.active_connections))
```

**验收标准**:
- [ ] 30 秒无消息自动断开
- [ ] 断开后 session 资源正确清理

**预估工时**: 1 小时

---

## 阶段五：用户体验与前端

### 5.1 前端摄像头参数调优

**当前问题**: 帧率高 (200ms/帧)、分辨率大 (640×480)，带宽消耗高。

**涉及文件**:
- `frontend/src/composables/useCamera.ts` — 调整参数

**改造方案**:
```typescript
// useCamera.ts — 降低帧率和分辨率
const CAPTURE_INTERVAL = 400     // 200ms → 400ms (2.5fps, 够用)
const CAPTURE_WIDTH = 480        // 640 → 480
const CAPTURE_HEIGHT = 360       // 480 → 360
const JPEG_QUALITY = 0.75        // 0.8 → 0.75

// 帧大小估算: 480×360 JPEG Q75 ≈ 25KB, base64 ≈ 33KB
// 带宽: 33KB × 2.5fps ≈ 82KB/s (原来约 200KB/s, 降低 60%)
```

**验收标准**:
- [ ] 带宽消耗降低 >50%
- [ ] 识别精度不下降

**预估工时**: 0.5 小时

---

### 5.2 识别结果 WebSocket 重连机制

**当前问题**: WebSocket 断开后前端无自动重连。

**涉及文件**:
- `frontend/src/composables/useWebSocket.ts` — 添加重连逻辑

**改造方案**:
```typescript
// useWebSocket.ts
export function useWebSocket() {
  const maxRetries = 5
  const baseDelay = 1000  // 初始 1s
  let retryCount = 0
  
  function connect(url: string) {
    ws = new WebSocket(url)
    
    ws.onclose = (event) => {
      if (retryCount < maxRetries && !event.wasClean) {
        const delay = baseDelay * Math.pow(2, retryCount)  // 指数退避
        retryCount++
        setTimeout(() => connect(url), delay)
      }
    }
    
    ws.onopen = () => {
      retryCount = 0  // 连接成功, 重置计数
    }
  }
}
```

**验收标准**:
- [ ] 网络抖动后自动重连 (指数退避)
- [ ] 最多重试 5 次

**预估工时**: 1 小时

---

### 5.3 前端 E2E 测试

**当前问题**: `package.json` 有 `test:e2e` 脚本但无实际测试用例。

**涉及文件**:
- `frontend/e2e/scan.spec.ts` — 新增刷脸流程 E2E
- `frontend/e2e/auth.spec.ts` — 新增登录流程 E2E
- `frontend/playwright.config.ts` — Playwright 配置

**改造方案**:
```typescript
// e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test('登录流程', async ({ page }) => {
  await page.goto('http://localhost:5173/login');
  await page.fill('input[placeholder="密码"]', 'admin123');
  await page.click('button:has-text("登录")');
  await expect(page).toHaveURL(/.*dashboard/, { timeout: 5000 });
});

// e2e/scan.spec.ts
test('扫描页面加载', async ({ page }) => {
  // 需要登录态
  await page.goto('http://localhost:5173/login');
  await page.fill('input[placeholder="密码"]', 'admin123');
  await page.click('button:has-text("登录")');
  
  await page.goto('http://localhost:5173/scan');
  await expect(page.locator('.scan-container')).toBeVisible();
  // 设备下拉框
  await expect(page.locator('select.device-select')).toBeVisible();
});
```

**验收标准**:
- [ ] `npm run test:e2e` 通过
- [ ] 覆盖登录 + 扫描页 + 记录页基础流程

**预估工时**: 4 小时

---

## 实施计划总览

### 按优先级排序

| 序号 | 改造项 | 阶段 | 优先级 | 预估工时 | 依赖 |
|------|--------|------|--------|----------|------|
| **1** | dlib → InsightFace/ArcFace | 一 | **P0** | 1-2天 | 无 |
| **2** | 活体检测重写 | 一 | **P0** | 0.5-1天 | 依赖 #1 |
| **3** | 完成 Alembic 迁移 | 二 | **P1** | 1h | 无 |
| **4** | 统一 WS 识别流程 | 二 | **P1** | 3h | 依赖 #1 |
| **5** | MinIO 集成 | 二 | **P1** | 4h | 无 |
| **6** | Excel 流式导出 | 二 | **P2** | 1h | 无 |
| **7** | FAISS 向量索引 | 三 | **P2** | 3h | 依赖 #1 (512维) |
| **8** | Nginx WS 限流 | 三 | **P1** | 1h | 无 |
| **9** | 统计接口缓存 | 四 | **P2** | 1h | 无 |
| **10** | WS 心跳超时 | 四 | **P2** | 1h | 无 |
| **11** | 前端摄像头调优 | 五 | **P2** | 0.5h | 无 |
| **12** | WS 自动重连 | 五 | **P2** | 1h | 无 |
| **13** | 前端 E2E 测试 | 五 | **P2** | 4h | 无 |

### 建议执行顺序

```
Week 1:
├── Day 1-2: #1 InsightFace 迁移 (核心, 解锁后续)
├── Day 2-3: #2 活体检测重写 (依赖 #1)
└── Day 3:   #3 Alembic 迁移完成 (独立, 快速)

Week 2:
├── Day 1:   #4 统一 WS 流程 (依赖 #1)
├── Day 2:   #5 MinIO 集成
├── Day 3:   #7 FAISS 索引 + #8 Nginx 限流
└── Day 4:   #6 #9 #10 小项

Week 3 (可选):
├── Day 1-2: #11 #12 #13 前端优化与测试
└── Day 3:   集成测试 + 性能压测
```

### 总预估工时

| 阶段 | 工时 | 说明 |
|------|------|------|
| 阶段一 (算法升级) | 2-3天 | 核心改造, 收益最大 |
| 阶段二 (代码质量) | 2天 | 可靠性提升 |
| 阶段三 (性能) | 1天 | 可选 (用户量<200时延后) |
| 阶段四 (安全增量) | 0.5天 | 小项 |
| 阶段五 (前端) | 1.5天 | 可选 |
| **合计** | **~7天** | 含测试 |

---

*文档编制: 2026-04-11*
*适用版本: go-face-demo v2.1.0 (Python)*
*目标版本: v3.0.0*
