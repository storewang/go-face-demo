# 04 - 功能扩展方案

## 目标
扩展系统功能，提升用户体验和业务覆盖范围。

---

## 1. 角色权限管理（RBAC）

### 现状
仅有一个 admin 密码，无角色区分，所有登录用户权限相同。

### 改造方案
- 三种角色：**超级管理员** / **部门管理员** / **普通员工**
- 权限矩阵：

| 功能 | 超级管理员 | 部门管理员 | 普通员工 |
|------|-----------|-----------|---------|
| 用户管理（全部） | ✅ | ❌ | ❌ |
| 用户管理（本部门） | ✅ | ✅ | ❌ |
| 考勤记录（全部） | ✅ | ✅ | ❌ |
| 考勤记录（自己） | ✅ | ✅ | ✅ |
| 数据导出 | ✅ | ✅ | ❌ |
| 系统配置 | ✅ | ❌ | ❌ |
| 人脸识别打卡 | ✅ | ✅ | ✅ |
| 人脸注册 | ✅ | ✅ | ✅ |

### 涉及文件
- `backend/app/models/user.py` — 新增 `role` 字段
- `backend/app/utils/auth.py` — JWT payload 加入角色信息
- `backend/app/utils/permissions.py` — 新增权限装饰器
- `backend/app/api/users.py` — 部门管理员过滤
- `backend/app/api/attendance.py` — 权限过滤
- `backend/app/schemas/user.py` — 新增角色相关 schema
- `frontend/src/types/user.ts` — 新增角色类型
- `frontend/src/stores/auth.ts` — 存储角色信息
- `frontend/src/views/Users.vue` — 按角色显示/隐藏操作
- Alembic migration — `ALTER TABLE users ADD COLUMN role`

### 代码示例

```python
# models/user.py
class RoleType(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    DEPT_ADMIN = "dept_admin"
    EMPLOYEE = "employee"

class User(Base):
    role: Mapped[str] = mapped_column(String(20), default=RoleType.EMPLOYEE, nullable=False)

# utils/permissions.py
from functools import wraps
from fastapi import HTTPException

def require_role(*roles: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user["role"] not in roles:
                raise HTTPException(status_code=403, detail="权限不足")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# api/users.py
@router.get("/users")
@require_role("super_admin", "dept_admin")
def list_users(current_user: dict, db: Session):
    query = db.query(User)
    if current_user["role"] == "dept_admin":
        query = query.filter(User.department == current_user["department"])
    return query.all()
```

---

## 2. 多门禁点管理

### 现状
系统仅支持单门禁点，所有识别共用一个 WebSocket 连接。

### 改造方案
- 新增 `Device`（设备）模型，管理多个门禁终端
- 每个设备有独立 ID、名称、位置、状态
- WebSocket 连接时携带设备 ID
- 考勤记录关联设备
- 设备管理界面（增删改查、启用/禁用）

### 涉及文件
- `backend/app/models/device.py` — 新增 Device 模型
- `backend/app/schemas/device.py` — 新增 Device schema
- `backend/app/api/devices.py` — 新增设备管理 API
- `backend/app/api/websocket.py` — WebSocket 携带 device_id
- `backend/app/models/attendance.py` — 新增 device_id 外键
- `frontend/src/views/Devices.vue` — 新增设备管理页面
- `frontend/src/types/device.ts` — 新增类型定义
- `frontend/src/router/index.ts` — 新增路由

### 数据模型

```python
# models/device.py
class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # 设备编号
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 设备名称
    location: Mapped[Optional[str]] = mapped_column(String(200))  # 安装位置
    status: Mapped[int] = mapped_column(default=1)  # 1=在线, 0=离线, 2=维护中
    last_heartbeat: Mapped[Optional[datetime]]  # 最后心跳时间
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

### WebSocket 协议扩展
```json
// 客户端连接时发送
{"type": "register", "device_id": "DOOR_001"}

// 服务端响应
{"type": "registered", "device_name": "正门入口"}
```

---

## 3. 通知推送系统

### 现状
打卡成功仅在前端页面显示，无其他通知渠道。

### 改造方案

### A. 企业微信/钉钉 Webhook 通知
- 打卡成功/失败推送
- 异常告警（多次识别失败、设备离线）

### B. 邮件通知
- 每日考勤汇总报告
- 异常打卡提醒（迟到、早退、缺卡）

### C. WebSocket 实时通知
- 管理员实时接收打卡事件
- 新用户注册通知

### 涉及文件
- `backend/app/services/notification_service.py` — 新增通知服务
- `backend/app/services/email_service.py` — 新增邮件服务
- `backend/app/api/notifications.py` — 新增通知配置 API
- `backend/app/config.py` — 新增通知相关配置
- `backend/requirements.txt` — 新增 `httpx`（Webhook）、`aiosmtplib`（邮件）
- `frontend/src/components/NotificationCenter.vue` — 新增通知中心组件

### 代码示例

```python
# services/notification_service.py
class NotificationService:
    async def send_webhook(self, url: str, message: dict):
        async with httpx.AsyncClient() as client:
            await client.post(url, json=message)

    async def notify_check_in(self, user: dict, device: str, confidence: float):
        """打卡成功通知"""
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"### 👤 打卡通知\n"
                           f"**姓名**: {user['name']}\n"
                           f"**部门**: {user['department']}\n"
                           f"**设备**: {device}\n"
                           f"**时间**: {datetime.now().strftime('%H:%M:%S')}\n"
                           f"**置信度**: {confidence:.1%}"
            }
        }
        # 发送到配置的 Webhook URL
        for url in settings.NOTIFICATION_WEBHOOKS:
            await self.send_webhook(url, message)

    async def send_daily_summary(self, db: Session):
        """每日考勤汇总"""
        today = datetime.now().date()
        # 查询今日考勤统计
        # 生成汇总报告
        # 发送邮件/Webhook
```

---

## 4. 考勤统计与分析

### 现状
仅记录打卡日志，无统计和分析功能。

### 改造方案

### A. 考勤报表
- 每日出勤率统计
- 部门出勤对比
- 个人考勤明细
- 迟到/早退/缺卡标记

### B. 工作时间规则
- 配置工作时间段（如 09:00-18:00）
- 迟到阈值（如 09:15）
- 早退阈值（如 17:45）
- 自动计算工作时长

### C. 数据可视化
- 出勤率趋势图（日/周/月）
- 部门出勤热力图
- 个人打卡时间分布

### 涉及文件
- `backend/app/models/schedule.py` — 新增排班规则模型
- `backend/app/services/attendance_analytics.py` — 新增统计分析服务
- `backend/app/api/analytics.py` — 新增统计 API
- `frontend/src/views/Analytics.vue` — 新增分析页面
- `frontend/src/views/Dashboard.vue` — 新增仪表盘
- 新增前端图表依赖：`echarts` 或 `chart.js`

### 代码示例

```python
# services/attendance_analytics.py
class AttendanceAnalytics:
    def daily_summary(self, db: Session, date: date) -> dict:
        total_users = db.query(User).filter(User.status == 1).count()
        checked_in = db.query(AttendanceLog.user_id).filter(
            AttendanceLog.action_type == ActionType.CHECK_IN,
            func.date(AttendanceLog.created_at) == date
        ).distinct().count()

        return {
            "date": date.isoformat(),
            "total_users": total_users,
            "checked_in": checked_in,
            "absent": total_users - checked_in,
            "attendance_rate": checked_in / total_users if total_users else 0,
            "late_count": self._count_late(db, date),
            "early_leave_count": self._count_early_leave(db, date),
        }

    def department_summary(self, db: Session, date: date) -> list:
        """各部门出勤统计"""
        departments = db.query(User.department).distinct().all()
        results = []
        for (dept,) in departments:
            dept_total = db.query(User).filter(User.department == dept, User.status == 1).count()
            dept_checked = db.query(AttendanceLog.user_id).join(User).filter(
                User.department == dept,
                AttendanceLog.action_type == ActionType.CHECK_IN,
                func.date(AttendanceLog.created_at) == date
            ).distinct().count()
            results.append({
                "department": dept,
                "total": dept_total,
                "checked_in": dept_checked,
                "rate": dept_checked / dept_total if dept_total else 0
            })
        return results
```

---

## 5. 用户自助服务

### 现状
用户必须管理员帮助注册人脸，无自助入口。

### 改造方案
- 用户可通过工号 + 短信验证码/邮箱验证码自助注册
- 自助更新人脸（需管理员审核或直接覆盖）
- 个人考勤记录查看
- 个人信息修改（手机号、邮箱等）

### 涉及文件
- `backend/app/api/self_service.py` — 新增自助服务 API
- `backend/app/services/sms_service.py` — 新增短信服务（可选）
- `backend/app/models/user.py` — 新增 phone, email 字段
- `frontend/src/views/SelfRegister.vue` — 新增自助注册页
- `frontend/src/views/Profile.vue` — 新增个人中心页
- `frontend/src/router/index.ts` — 新增路由

---

## 6. API 文档增强

### 现状
FastAPI 自带 Swagger UI，但无业务说明。

### 改造方案
- 为每个 API 端点添加详细的 `description` 和 `response_model`
- 添加请求/响应示例
- 生成 Postman Collection 导出
- 添加 API 版本前缀 `/api/v1/`

### 涉及文件
- `backend/app/main.py` — API 版本前缀
- 所有 `backend/app/api/*.py` — 补充文档
- 所有 `backend/app/schemas/*.py` — 补充 `example` 字段

---

## 改造优先级

| 序号 | 改造项 | 优先级 | 预估工时 | 风险 |
|------|--------|--------|----------|------|
| 1 | 角色权限管理 | 🔴 P0 | 4h | 中 |
| 2 | 多门禁点管理 | 🟡 P1 | 4h | 中 |
| 3 | 考勤统计与分析 | 🟡 P1 | 4h | 低 |
| 4 | 通知推送系统 | 🟡 P1 | 3h | 低 |
| 5 | 用户自助服务 | 🟢 P2 | 3h | 中 |
| 6 | API 文档增强 | 🟢 P2 | 2h | 低 |

**总预估工时：20h**

---

## 验收标准
- [ ] 三种角色权限正确隔离
- [ ] 部门管理员只能查看本部门数据
- [ ] 支持添加/管理多个门禁设备
- [ ] 打卡成功可推送到企业微信/钉钉
- [ ] 考勤统计页面展示出勤率、迟到率等数据
- [ ] 用户可通过验证码自助注册
- [ ] API 文档包含完整的请求/响应示例
