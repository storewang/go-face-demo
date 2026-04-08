# CHANGELOG

## [2.1.0] - 2026-04-08

系统全面升级：安全加固、运维标准化、性能优化、功能扩展、集群部署支持。
总计 73 次文件变更，+4,611 / -144 行代码。

---

### Phase 1 - 安全加固 `bb753a7`

**安全评分：5/10 → 9/10**

- **JWT 认证**：替换内存 token 集为 JWT（python-jose + passlib），支持无状态验证和过期控制
- **密码安全**：移除硬编码 `admin123`，bcrypt 哈希存储，首次登录自动生成密码
- **CORS 白名单**：`["*"]` → 可配置域名白名单
- **速率限制**：slowapi — 登录 5/min、注册 10/min、全局 60/min
- **文件上传校验**：类型/尺寸/维度验证 + 路径遍历防护（`utils/validators.py`）
- **安全头**：starlette-secure-headers（HSTS、X-Frame-Options、X-Content-Type-Options 等）

**新增依赖**：`python-jose[cryptography]`, `passlib[bcrypt]`, `slowapi`, `secure`

---

### Phase 2 - 运维改进 `4778cd3`

**可观测性：无 → 全链路**

- **结构化日志**：structlog JSON 格式替换所有 `print`，支持生产/调试模式切换
- **数据库迁移**：Alembic 初始化，支持版本化 schema 管理
- **健康检查**：增强 `/health`（数据库/人脸服务/磁盘状态）+ K8s `/health/ready` + `/health/live`
- **Prometheus 监控**：HTTP 指标 + 人脸识别指标（请求/成功/失败/耗时/已注册数）
- **数据库连接池**：pool_size=10, max_overflow=20, pool_pre_ping, pool_recycle
- **自动备份**：`scripts/backup.sh`（数据库+人脸+编码，7 天自动清理）

**新增依赖**：`structlog`, `alembic`, `prometheus-fastapi-instrumentator`, `prometheus-client`

---

### Phase 3 - 性能优化 `d46434d`

**响应速度：显著提升（Redis 缓存 + 后台加载）**

- **Redis 缓存层**：`cache.py` 封装，自动降级（Redis 不可用时退化为无缓存模式）
- **识别结果缓存**：同一用户 3 秒内直接返回（O(1)），新增 `face_recognition_cache_hits` 指标
- **用户信息缓存**：查询缓存 10 分钟，变更时自动清除
- **特征库后台加载**：daemon 线程异步加载，应用启动不再阻塞
- **WebSocket 跳帧**：`processing` 标志防止并发帧处理积压
- **数据库索引**：`attendance_logs` 表自动创建复合索引

**新增依赖**：`redis[hiredis]`

---

### Phase 4 - 功能扩展 `61f0387`

**API 端点：12 → 27（+15 个新端点）**

#### RBAC 权限系统
- 三级角色：`super_admin` / `dept_admin` / `employee`
- 权限装饰器：`require_role()` / `require_permission()`
- JWT payload 包含角色信息
- 用户角色修改接口（仅超级管理员）

#### 门禁设备管理
- 设备 CRUD API（5 个端点）
- Device 模型 + Schema
- AttendanceLog 新增 `device_id` 关联

#### 考勤统计
- `GET /api/statistics/daily` — 每日出勤率、签到人数、缺勤人数
- `GET /api/statistics/user/{id}` — 个人考勤详情（每日首末次打卡）
- `GET /api/statistics/trend` — N 天趋势（出勤/缺勤/比率）

#### 通知推送
- Redis Pub/Sub 实时通知服务
- 三个频道：人脸识别 / 考勤打卡 / 系统告警

#### 用户自助服务
- `GET /api/self/profile` — 个人信息
- `GET /api/self/attendance` — 我的考勤记录
- `GET /api/self/attendance/today` — 今日签到/签退状态
- `DELETE /api/self/face` — 注销人脸数据

---

### Phase 5 - 集群扩展 `f3ce9b3`

**部署模式：单机 → 集群（2-10 节点弹性伸缩）**

#### 后端适配
- **PostgreSQL 兼容**：`DATABASE_URL` 动态生成，SQLite/PG 双模式
- **JWT 跨节点共享**：Token 黑名单从内存迁移到 Redis
- **对象存储抽象层**：`storage_service.py`（MinIO 优先，本地文件降级）

#### K8s 部署
- `k8s/` 完整配置：namespace、configmap、secret
- PostgreSQL StatefulSet + PVC（10Gi）
- Redis Deployment（512MB 限制，LRU 淘汰）
- MinIO Deployment + PVC（20Gi）
- Backend Deployment（3 副本）+ Service + HPA（2-10 弹性伸缩）

#### Docker Compose 集群版
- `docker-compose.cluster.yml`：3 后端 + Nginx + PostgreSQL + Redis + MinIO + Prometheus + Grafana
- `.env.cluster.example` 环境变量模板

#### 负载均衡 & 监控
- `nginx/nginx.conf`：least_conn 策略 + WebSocket 长连接支持 + /metrics 内网限制
- `prometheus/prometheus.yml`：K8s 服务发现自动采集
- Grafana 默认集成

#### 数据迁移
- `scripts/migrate_sqlite_to_pg.py`：SQLite → PostgreSQL 自动迁移

**新增依赖**：`psycopg2-binary`, `minio`

---

## [1.0.0] - 初始版本

- FastAPI 后端：人脸注册、识别、考勤签到/签退
- Vue 3 前端：首页、注册、扫描、记录、用户管理
- SQLite 数据库、WebSocket 实时推送
- Docker 单机部署
