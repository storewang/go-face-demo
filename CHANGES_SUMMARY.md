# 设备管理与识别流程串联 - 功能实现总结

## 实现日期
2026-04-08

## 功能概述
实现了设备管理与人脸识别流程的完整串联，包括设备心跳检测、WebSocket 设备绑定、考勤记录设备信息关联等功能。

---

## 后端修改

### 1. `/backend/app/api/devices.py`
**新增功能：**
- 新增 `POST /api/devices/heartbeat` 端点
  - 根据 device_code 查找设备
  - 验证设备状态（status=2 时返回 403）
  - 更新 last_heartbeat 为当前时间，status 设为 1（在线）
  - 返回设备信息

- 修改 `GET /api/devices` 端点
  - 动态计算设备在线状态（is_online 字段）
  - 基于 last_heartbeat 判断：60 秒内为在线

**新增 Schema：**
- `HeartbeatRequest`: 设备心跳请求体
- `DeviceWithOnlineResponse`: 带在线状态的设备响应

---

### 2. `/backend/app/websocket/manager.py`
**修改功能：**
- session 数据中增加设备相关字段：
  - `device_id`: 设备 ID
  - `device_code`: 设备编号
  - `device_name`: 设备名称

---

### 3. `/backend/app/api/websocket.py`
**修改功能：**
- `websocket_endpoint` 增加"register" 消息处理
  - 验证设备是否存在
  - 验证设备是否被禁用
  - 将设备信息存入 session
  - 发送注册成功响应

- `process_frame` 修改
  - 识别成功写入 AttendanceLog 时，如果 session 中有 device 信息，写入 device_id
  - 响应消息中增加 device_name 字段

---

### 4. `/backend/app/schemas/attendance.py`
**修改功能：**
- `AttendanceResponse` 增加：
  - `device_id: Optional[int]` - 设备 ID
  - `device_name: Optional[str]` - 设备名称

---

### 5. `/backend/app/api/attendance.py`
**修改功能：**
- `list_attendance` 增加：
  - `device_id: Optional[int]` 参数 - 设备筛选
  - 查询时关联 Device 表获取设备名称
  - 响应中包含 device_name 字段

---

## 前端修改

### 6. `/frontend/src/composables/useWebSocket.ts`
**修改功能：**
- `connect` 方法增加可选 `deviceCode` 参数
- 连接成功后如果传了 deviceCode，自动发送 "register" 消息
- 增加 `onRegistered` 回调
- 增加 `registeredDevice` 响应式变量，存储注册成功的设备信息
- 增加 `RegisterResult` 接口定义

---

### 7. `/frontend/src/views/Scan.vue`
**修改功能：**
- 增加"选择设备"下拉框（位于"开始识别"按钮上方）
- 调用 `/api/devices` 获取设备列表
- 显示设备在线/离线状态标签
- 选择设备后，连接 WebSocket 时带上 device_code
- 连接成功后在状态区域显示当前设备名称（"当前设备: xxx"）
- 如果不选择设备，行为和之前一样（匿名连接）

---

### 8. `/frontend/src/views/Records.vue`
**修改功能：**
- 筛选区域增加"设备"下拉框
- 调用 `/api/devices` 获取设备列表
- queryParams 增加 `device_id` 字段
- 表格增加"设备"列，显示 device_name
- device_name 为空显示 "-"
- 详情弹窗增加设备信息显示

---

### 9. `/frontend/src/views/Devices.vue`
**修改功能：**
- "最后心跳"列优化显示：
  - 心跳在 60 秒内：绿色"在线"标签 + 相对时间（如"3秒前"、"5分钟前"）
  - 超过 60 秒但不超过 24 小时：黄色"离线"标签 + 绝对时间
  - 超过 24 小时或无心跳：灰色"从未连接"标签

- 增加自动刷新：
  - 每 10 秒自动刷新设备列表
  - onBeforeUnmount 清理定时器

- 新增辅助函数：
  - `isOnline()`: 判断设备是否在线
  - `isRecentlyOffline()`: 判断设备是否最近离线
  - `formatRelativeTime()`: 格式化相对时间

- 新增样式：
  - `.heartbeat-status`: 心跳状态容器
  - `.heartbeat-status.online`: 在线状态样式
  - `.heartbeat-status.offline`: 离线状态样式

---

## 关键改动点

### 后端关键改动
1. **设备心跳 API** - 支持设备定期上报状态
2. **WebSocket 设备绑定** - 支持 register 消息注册设备
3. **考勤记录关联设备** - device_id 字段被正确使用
4. **动态在线状态** - 基于心跳时间动态计算设备是否在线

### 前端关键改动
1. **useWebSocket 支持设备注册** - 连接时可选绑定设备
2. **Scan.vue 设备选择** - 可选设备进行识别
3. **Records.vue 设备筛选** - 支持按设备筛选考勤记录
4. **Devices.vue 状态优化** - 直观显示设备在线状态 + 自动刷新

---

## 向后兼容性
✅ 所有修改保持向后兼容：
- 不传 device_code 的 WebSocket 连接行为与之前一致（匿名连接）
- 考勤记录的 device_id 字段为 Optional，不影响现有数据
- 设备列表的 is_online 字段为新增字段，不影响现有 API

---

## 技术栈
- 后端：FastAPI + SQLAlchemy + Pydantic
- 前端：Vue 3 + TypeScript + Element Plus
- 通信：WebSocket

---

## 测试建议
1. 测试设备心跳 API（调用 /api/devices/heartbeat）
2. 测试 WebSocket 设备注册（发送 register 消息）
3. 测试 Scan.vue 选择设备后的识别流程
4. 测试 Records.vue 设备筛选功能
5. 测试 Devices.vue 在线状态显示和自动刷新
6. 测试向后兼容性（不选择设备的匿名连接）
