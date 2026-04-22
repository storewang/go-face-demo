# 人脸识别门禁系统 — 完善改造方案

> **版本**: v2.1.0 → v3.0.0
> **定位**: <50 用户，单门禁点，PC + USB 摄像头
> **目标**: 从「功能完整的 Demo」升级为「可放心交付的生产系统」
> **总工期**: 约 5-6 周（1 人全职）或 3 周（2 人并行）

---

## 当前系统评估

### ✅ 已完成的优势
| 维度 | 评价 |
|------|------|
| 功能完整度 | ⭐⭐⭐⭐⭐ 注册→识别→考勤→管理→统计 全链路闭环 |
| API 设计 | ⭐⭐⭐⭐ 27+ 端点，RBAC 三级角色，RESTful 规范 |
| 运维体系 | ⭐⭐⭐⭐ Prometheus + 结构化日志 + 健康检查 + 自动备份 |
| 部署灵活性 | ⭐⭐⭐⭐ Docker 单机/集群/K8s 三级方案 |
| 安全基础 | ⭐⭐⭐ JWT + bcrypt + CORS 白名单 + 速率限制 + 安全头 |

### ⚠️ 核心问题（Oracle + 代码审查发现）

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **过度工程** | 🔴 高 | K8s + HPA + FAISS 对 <50 用户单门禁场景完全不需要，引入无谓的运维复杂度 |
| 2 | **生物特征数据未加密** | 🔴 高 | `.npy` 特征向量明文存储，违反个人信息保护法规 |
| 3 | **无后备开门方式** | 🔴 高 | 摄像头故障或 AI 服务崩溃 = 门打不开 |
| 4 | **WebSocket 传输瓶颈** | 🟡 中 | base64 JPEG over WS，带宽浪费大，CPU 开销高 |
| 5 | **测试覆盖不均衡** | 🟡 中 | 后端 79 集成测试 ✅，前端 0 单元测试 ❌，2 E2E 测试 |
| 6 | **模型管理无自动化** | 🟡 中 | InsightFace buffalo_l 模型首次部署需手动下载 |
| 7 | **无 CI/CD 流水线** | 🟡 中 | 所有测试和部署全靠手动 |
| 8 | **无审计日志** | 🟡 中 | 门禁事件无防篡改记录，不符合安防审计要求 |
| 9 | **集群 WS 状态不共享** | 🟢 低 | 当前单节点无影响，但集群模式下 WS 会话丢失 |
| 10 | **无 API 版本管理** | 🟢 低 | 所有端点在 `/api/` 下，未来 breaking change 无隔离 |

---

## 改造方案：6 个阶段

---

### Phase 6 — 基础设施瘦身（去过度工程化）

**目标**: 简化部署，减少依赖，降低运维成本
**工期**: 3-4 天
**优先级**: P0 — 其他一切的基础

#### 6.1 移除 FAISS，保留 NumPy 暴力搜索

**理由**: FAISS 为百万级向量设计。<50 用户 = 50×512 维矩阵，NumPy 矩阵乘法 <0.1ms，完全够用。

**改动**:
```
- 移除 requirements.txt 中的 faiss-cpu
- 移除 face_service.py 中 _build_faiss_index()、_recognize_faiss()
- 保留 _recognize_numpy() 作为唯一识别路径
- 移除所有 HAS_FAISS 条件分支
- KNOWN_FACES_GAUGE 等指标保持不变
```

**涉及文件**:
- `backend/app/services/face_service.py` — 删除 FAISS 相关代码 (~40 行)
- `backend/requirements.txt` — 删除 `faiss-cpu>=1.7.4`
- `backend/tests/test_integration.py` — 更新 mock（移除 faiss mock）

**验证**: `pytest` 全部通过 + 注册→识别流程功能测试

#### 6.2 简化部署方案：Docker Compose 为一等公民

**理由**: 单门禁场景用 K8s 是杀鸡用牛刀。保留集群代码但不作为推荐部署。

**改动**:
- `docker-compose.yml` 保持不变（单机部署主方案）
- `docker-compose.cluster.yml` 和 `k8s/` 移到 `deploy/cluster/` 目录（归档，非推荐）
- 新增 `docker-compose.dev.yml`（开发环境热重载配置）
- 更新 `DEPLOY.md`：推荐 Docker Compose 单机部署，集群作为可选

**新文件结构**:
```
docker-compose.yml          ← 生产单机（推荐）
docker-compose.dev.yml      ← 开发热重载
deploy/
  cluster/
    docker-compose.cluster.yml
    k8s/
    ...
```

#### 6.3 自动化 InsightFace 模型管理

**问题**: `buffalo_l` 模型约 300MB，首次启动需下载但无自动化。

**改动**:
```python
# backend/app/services/model_manager.py（新建）
class ModelManager:
    """InsightFace 模型自动下载与校验"""
    
    MODEL_DIR = Path("./models")
    MODEL_NAME = "buffalo_l"
    MODEL_HASH = "sha256:..."  # 锁定版本完整性
    
    def ensure_model(self) -> Path:
        """确保模型已下载且完整性校验通过"""
        model_path = self.MODEL_DIR / self.MODEL_NAME
        if model_path.exists() and self._verify_hash(model_path):
            return model_path
        log.info("downloading_model", model=self.MODEL_NAME)
        self._download(model_path)
        return model_path
    
    def _verify_hash(self, path: Path) -> bool:
        """校验模型文件 SHA256"""
        ...
    
    def _download(self, path: Path):
        """从 InsightFace 官方源下载"""
        ...
```

- `Dockerfile` 中增加 `RUN python -c "from app.services.model_manager import ModelManager; ModelManager().ensure_model()"`
- `face_service.py._init_insightface()` 改为先调 `ModelManager().ensure_model()`

**涉及文件**:
- 新建 `backend/app/services/model_manager.py`
- 修改 `backend/app/services/face_service.py`
- 修改 `backend/Dockerfile`

---

### Phase 7 — 安全加固（生物特征保护 + 后备通道）

**目标**: 满足个人信息保护合规要求，确保门禁可用性
**工期**: 5-6 天
**优先级**: P0 — 合规 + 安全底线

#### 7.1 生物特征向量加密存储

**问题**: `.npy` 文件明文存储 512 维浮点向量。一旦被窃取可直接用于伪造。

**方案**: 使用 Fernet 对称加密（密钥通过环境变量注入）

```python
# backend/app/utils/crypto.py（新建）
from cryptography.fernet import Fernet
from app.config import settings

class BiometricCrypto:
    """生物特征数据加密/解密"""
    
    def __init__(self):
        self._fernet = Fernet(settings.BIOMETRIC_ENCRYPTION_KEY.encode())
    
    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)
    
    def decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)

biometric_crypto = BiometricCrypto()
```

**改动**:
- `config.py` 新增 `BIOMETRIC_ENCRYPTION_KEY: str`（必填，32 字节 base64）
- `face_service.py._save_encoding()` — 保存前加密
- `face_service.py._load_encoding()` — 加载后解密
- `storage_service.py` — MinIO 模式同样加密
- 数据迁移脚本: `scripts/encrypt_existing_encodings.py`（现有明文数据一次性加密）

**涉及文件**:
- 新建 `backend/app/utils/crypto.py`
- 修改 `backend/app/config.py`
- 修改 `backend/app/services/face_service.py`
- 新建 `backend/scripts/encrypt_existing_encodings.py`
- 修改 `backend/requirements.txt` — 添加 `cryptography>=41.0`

#### 7.2 门禁后备通道：PIN 码开门

**问题**: 摄像头故障/AI 服务崩溃时，用户无法开门。

**方案**: 每个用户分配 6 位 PIN 码，通过 Web UI 或硬件键盘输入

```python
# 数据模型变更
class User(Base):
    ...
    pin_code: str = Column(String(255), nullable=True)  # bcrypt 哈希存储
    
# API 端点
POST /api/auth/pin-verify
    Request: {"pin_code": "123456", "device_code": "DOOR-001"}
    Response: {"success": true, "user": {...}, "action": "door_open"}
```

**改动**:
- `models/user.py` — 新增 `pin_code` 字段
- `schemas/user.py` — 新增 PIN 相关 schema
- `api/auth.py` — 新增 PIN 验证端点
- 前端 `Scan.vue` — 新增「PIN 码开门」切换标签
- Alembic 迁移脚本

**涉及文件**:
- 修改 `backend/app/models/user.py`
- 修改 `backend/app/schemas/user.py`
- 修改 `backend/app/api/auth.py`
- 新建 `frontend/src/views/PinEntry.vue`（或 Scan.vue 内嵌）
- 新建 `backend/alembic/versions/002_add_pin_code.py`

#### 7.3 审计日志（防篡改）

**问题**: 门禁事件无不可抵赖的审计记录。

**方案**: 独立审计表 + HMAC 签名

```python
# backend/app/models/audit.py（新建）
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: int                  # 主键
    event_type: str          # door_open / door_deny / pin_open / face_register
    user_id: int             # 操作用户
    device_id: int           # 门禁设备
    confidence: float        # 识别置信度
    snapshot_path: str       # 抓拍图路径
    raw_data: str            # 原始事件 JSON
    hmac_signature: str      # HMAC-SHA256(event_type + user_id + timestamp + SECRET)
    created_at: datetime     # 时间戳
    
    # HMAC 密钥从 settings 读取，写入后不可修改
    # 定期导出到不可变存储（如只读 NFS / WORM S3）
```

**涉及文件**:
- 新建 `backend/app/models/audit.py`
- 修改 `backend/app/api/websocket.py` — 识别成功后写审计日志
- 新建 `backend/app/api/audit.py` — 审计查询 API
- 新建 `backend/alembic/versions/003_add_audit_logs.py`

#### 7.4 数据自动清理策略

```python
# config.py 新增
DATA_RETENTION_DAYS: int = 90  # 审计日志保留 90 天
SNAPSHOT_RETENTION_DAYS: int = 30  # 抓拍图保留 30 天
FACE_DATA_DELETE_ON_RESIGN: bool = True  # 员工离职自动删除人脸数据

# services/cleanup_service.py（新建）
class CleanupService:
    """数据生命周期管理"""
    
    def cleanup_expired_data(self, db: Session):
        """清理过期数据和已离职员工的人脸数据"""
        ...
```

---

### Phase 8 — 实时通信优化

**目标**: 降低带宽消耗，提升识别响应速度
**工期**: 3-4 天
**优先级**: P1 — 直接影响用户体验

#### 8.1 WebSocket 帧传输优化

**问题**: 当前前端将 canvas 截图 → base64 JPEG → JSON → WebSocket 发送。一帧约 100-200KB base64，带宽浪费约 33%。

**方案 A（短期，推荐）**: 二进制 WebSocket 帧

```
前端改动:
- canvas.toBlob('image/jpeg', 0.8) → ArrayBuffer
- ws.send(arrayBuffer)  // 直接发送二进制，不经过 base64

后端改动:
- websocket.receive_bytes() 替代 receive_text()
- 帧头协议: [1 byte type][N bytes payload]
  - type=0x01: register (JSON)
  - type=0x02: frame (JPEG bytes)
  - type=0x03: ping
```

**带宽节省**: ~33%（移除 base64 编码开销）

**方案 B（中期）**: 降低帧率 + 服务端 ROI 裁剪

```
- 前端帧率从实时降到 3-5 FPS
- 前端做人脸框检测后，只裁剪人脸区域发送（约 5-10KB/帧）
- 服务端收到裁剪图直接做识别
```

**涉及文件**:
- 修改 `frontend/src/composables/useWebSocket.ts` — 支持二进制发送
- 修改 `frontend/src/composables/useCamera.ts` — canvas → Blob
- 修改 `backend/app/api/websocket.py` — 接收二进制帧
- 修改 `backend/app/websocket/manager.py` — 二进制消息支持

#### 8.2 识别结果实时推送优化

**当前问题**: 识别成功后只在 WS 连接内推送结果，Dashboard 等页面无法实时感知。

**方案**: Redis Pub/Sub 跨页面广播

```python
# 已有 notification_service.py 基于 Redis Pub/Sub
# 扩展: 前端 Dashboard 通过 SSE (Server-Sent Events) 订阅

GET /api/events/stream  ← SSE 端点
    → 事件类型: face_recognized / attendance_recorded / device_status_change
    → 前端 EventSource 自动接收
```

**涉及文件**:
- 新建 `backend/app/api/events.py` — SSE 端点
- 修改 `frontend/src/views/Dashboard.vue` — SSE 集成

---

### Phase 9 — 测试与质量保障

**目标**: 建立可持续的质量保障体系
**工期**: 5-7 天
**优先级**: P1 — 变更信心

#### 9.1 后端测试增强

**现状**: 79 个集成测试，覆盖所有 API 端点，Mock 了 InsightFace/CV2。质量不错。

**缺失**:
- ❌ 单元测试（service 层、utils 层）
- ❌ 性能基准测试
- ❌ WebSocket 端到端测试

**新增测试**:

| 测试类型 | 目标 | 文件 |
|----------|------|------|
| **Service 单元测试** | face_service 核心逻辑独立于 FastAPI | `tests/test_face_service.py` |
| **加密单元测试** | crypto 模块加解密正确性 | `tests/test_crypto.py` |
| **审计日志测试** | HMAC 签名、防篡改验证 | `tests/test_audit.py` |
| **并发识别测试** | 多线程同时调 face_service 不冲突 | `tests/test_concurrency.py` |
| **数据库迁移测试** | Alembic upgrade/downgrade 正确 | `tests/test_migrations.py` |

**目标**: 后端测试覆盖率 ≥ 80%

#### 9.2 前端测试补全

**现状**: 2 个 Playwright E2E 测试，0 个单元测试。

**策略**: 先 E2E 覆盖核心流程，再补充 Store 单元测试。

**E2E 测试扩展** (Playwright):
```
frontend/e2e/
├── navigation.spec.ts    ← 已有
├── scan.spec.ts          ← 已有
├── auth.spec.ts          ← 新增: 登录/登出/Token 过期
├── register.spec.ts      ← 新增: 用户注册 + 人脸采集
├── users.spec.ts         ← 新增: 用户 CRUD
├── devices.spec.ts       ← 新增: 设备管理
├── records.spec.ts       ← 新增: 考勤记录查询 + 导出
└── dashboard.spec.ts     ← 新增: 统计仪表盘
```

**Store 单元测试** (Vitest):
```
frontend/tests/
├── stores/
│   ├── auth.test.ts      ← 登录/登出状态管理
│   ├── user.test.ts      ← 用户 CRUD 操作
│   └── attendance.test.ts ← 考勤数据获取
├── composables/
│   └── useCamera.test.ts ← 摄像头控制逻辑
└── utils/
    └── image.test.ts     ← 图像处理工具
```

**目标**: 前端核心流程 E2E 覆盖 100%，Store 单元测试覆盖率 ≥ 70%

#### 9.3 CI/CD 流水线

```yaml
# .github/workflows/ci.yml（新建）
name: CI

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install deps
        run: cd backend && pip install -r requirements.txt
      - name: Run tests
        run: cd backend && pytest -v --tb=short
        
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install deps
        run: cd frontend && npm ci
      - name: Type check
        run: cd frontend && npm run typecheck
      - name: Unit tests
        run: cd frontend && npx vitest run --coverage
      - name: Build
        run: cd frontend && npm run build
```

**涉及文件**:
- 新建 `.github/workflows/ci.yml`
- 新建 `backend/tests/test_face_service.py`
- 新建 `backend/tests/test_crypto.py`
- 新建 `backend/tests/test_audit.py`
- 新建 `frontend/tests/stores/auth.test.ts`
- 新建 `frontend/tests/stores/user.test.ts`
- 新建 `frontend/e2e/auth.spec.ts`
- 新建 `frontend/e2e/register.spec.ts`

---

### Phase 10 — 前端体验升级

**目标**: 提升操作效率和视觉一致性
**工期**: 4-5 天
**优先级**: P2 — 用户满意度

#### 10.1 离线提示与优雅降级

```typescript
// composables/useOnlineStatus.ts（新建）
export function useOnlineStatus() {
  const isOnline = ref(navigator.onLine)
  // 监听 online/offline 事件
  // 离线时显示全局提示横幅
  // WS 断开时自动切换到 "离线模式" 标签
}

// Scan.vue 降级逻辑:
// 1. WS 断开 → 显示 "网络断开，请使用 PIN 码开门"
// 2. 摄像头不可用 → 显示 "摄像头不可用，请使用 PIN 码"
// 3. 人脸服务异常 → 显示 "服务维护中，请使用 PIN 码"
```

#### 10.2 操作反馈优化

- 识别成功/失败增加音效提示（叮/咚）
- 全局 loading 状态统一管理（app store 已有基础）
- 错误提示统一格式（ElMessage + 错误码 + 可操作建议）
- 表格空状态设计（空数据时的友好提示）

#### 10.3 响应式优化

- 当前已有基础响应式（MainLayout drawer），需细化：
  - Scan 页面在小屏设备上的摄像头全屏体验
  - Dashboard 卡片在移动端的折叠展示
  - 表格在移动端切换为卡片列表

#### 10.4 国际化基础架构（可选）

```typescript
// frontend/src/i18n/index.ts（新建）
// 仅搭建框架，中文为默认语言
// 使用 vue-i18n，所有 UI 字符串抽取到 locales/zh-CN.ts
// 为未来英文支持预留接口
```

**涉及文件**:
- 新建 `frontend/src/composables/useOnlineStatus.ts`
- 修改 `frontend/src/views/Scan.vue` — 降级逻辑 + PIN 切换
- 修改 `frontend/src/stores/app.ts` — 全局错误/离线状态
- 修改 `frontend/src/views/Dashboard.vue` — 移动端优化
- 新建 `frontend/src/i18n/` 目录（可选）

---

### Phase 11 — 文档与交付

**目标**: 可维护、可交付、可交接
**工期**: 2-3 天
**优先级**: P2 — 长期可维护性

#### 11.1 整合设计文档

将分散在 `docs/` 下的 32 个文件整合为：

```
docs/
├── architecture.md          ← 整合 specs/ + plans/ 的架构总览
│   （系统架构图、数据流、技术选型、模块划分）
├── api-reference.md         ← 整合 face-api-docs.md，所有端点文档
├── deployment-guide.md      ← 整合 deployment.md + docker-deployment.md
├── security.md              ← 新增：安全设计、加密方案、合规说明
├── testing-strategy.md      ← 新增：测试策略和覆盖目标
└── archive/                 ← 原始计划和设计文档归档
    ├── superpowers/
    ├── optimization/
    └── ...
```

#### 11.2 运维手册

```
docs/runbook.md（新建）
├── 日常运维: 启动/停止/备份/恢复
├── 故障排查: 常见问题诊断流程图
│   ├── 人脸识别失败排查
│   ├── WebSocket 连接异常排查
│   ├── 数据库连接池耗尽排查
│   └── 磁盘空间不足处理
├── 应急预案: 摄像头故障/网络中断/服务崩溃
├── 数据恢复: 备份恢复操作步骤
└── 监控告警: Prometheus 告警规则说明
```

#### 11.3 API 版本管理

```
# 当前: /api/users, /api/face/detect, ...
# 改为: /api/v1/users, /api/v1/face/detect, ...

# backend/app/api/__init__.py
api_router = APIRouter(prefix="/api/v1")
```

保留 `/api/` 作为兼容别名（deprecated），v4.0 移除。

---

## 实施优先级与时间线

```
Week 1:  Phase 6 (基础设施瘦身)  +  Phase 7.1 (特征加密)
         ├── Day 1-2: 移除 FAISS, 简化部署, 模型自动化
         └── Day 3-5: crypto 模块, 数据加密迁移

Week 2:  Phase 7.2-7.4 (后备通道 + 审计 + 清理)
         ├── Day 1-3: PIN 码开门 (前后端)
         └── Day 4-5: 审计日志 + 数据清理策略

Week 3:  Phase 8 (实时通信优化)
         ├── Day 1-2: WebSocket 二进制帧
         └── Day 3-4: SSE 推送 + Dashboard 实时更新

Week 4:  Phase 9 (测试与 CI/CD)
         ├── Day 1-3: 后端新增测试 + CI 流水线
         └── Day 4-5: 前端 E2E + Store 单元测试

Week 5:  Phase 10 (前端体验升级)
         ├── Day 1-2: 离线降级 + PIN 切换 UI
         ├── Day 3-4: 操作反馈 + 响应式优化
         └── Day 5: i18n 基础（可选）

Week 6:  Phase 11 (文档与交付)
         ├── Day 1-2: 文档整合
         └── Day 3: API 版本化 + 运维手册 + 最终验收
```

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 特征加密后识别性能下降 | 低 | 中 | Fernet 加密 512 维向量 <0.1ms，对识别总耗时影响 <1% |
| PIN 码安全性不足 | 中 | 中 | 6 位 PIN + 速率限制 (3 次/分钟) + bcrypt 哈希 + 异常告警 |
| WebSocket 二进制迁移破坏兼容性 | 中 | 高 | 新增协议版本号，旧客户端降级到 base64 JSON 模式 |
| 数据迁移脚本失败 | 低 | 高 | 迁移前自动备份 + dry-run 模式 + 回滚脚本 |
| 前端 E2E 测试不稳定 | 中 | 低 | Playwright retry 机制 + 等待策略 + 截图对比 |

## 成功标准

- [ ] 所有生物特征数据加密存储（零明文向量）
- [ ] PIN 码后备通道可用（摄像头故障时仍可开门）
- [ ] 后端测试 ≥ 100 用例，覆盖率 ≥ 80%
- [ ] 前端 E2E 覆盖 8+ 核心流程
- [ ] CI/CD 流水线自动运行
- [ ] 单机 Docker Compose 一键部署（含模型自动下载）
- [ ] 审计日志完整记录所有门禁事件
- [ ] 文档齐全：架构、API、部署、运维、安全
