# 人脸采集与识别接口对接文档

## 1. 概述

本文档描述人脸识别门禁系统中**人脸采集**和**人脸识别**相关的所有后端接口，供前端或第三方客户端对接使用。

### 基础信息

| 项目 | 值 |
|---|---|
| Base URL | `http://<host>:8000` |
| 协议 | HTTP REST + WebSocket |
| 图片格式 | JPEG（推荐）、PNG |
| 认证方式 | Bearer Token（`Authorization: Bearer <token>`） |

### 权限说明

| 接口分类 | 是否需要认证 |
|---|---|
| 人脸检测 `/api/face/detect` | 否 |
| 人脸识别 `/api/face/recognize` | 否 |
| 人脸比对 `/api/face/compare` | 否 |
| 完整验证 `/api/face/verify` | 否 |
| 人脸注册 `/api/face/register/{user_id}` | 否 |
| 用户注册（含人脸）`/api/users` POST | 否 |
| 刷脸打卡 `/api/attendance/check-in` `check-out` | 否 |
| WebSocket 实时识别 `/ws/face-stream` | 否 |
| 用户管理 `/api/users` GET/PUT/DELETE | 是（管理员） |
| 考勤管理 `/api/attendance` GET | 是（管理员） |

> **认证接口**：`POST /api/auth/login`，请求体 `{"password": "admin123"}`，返回 Token。

### 通用约定

- 所有涉及图片上传的接口，使用 `multipart/form-data` 格式
- **不要**手动设置 `Content-Type`，让客户端自动生成 boundary
- 图片建议分辨率 ≥ 640×480，人脸区域 ≥ 120×120 像素
- 识别阈值默认 `0.6`（置信度 ≥ 0.6 判定为同一人），可在后端配置调整

---

## 2. 人脸质量评估标准

所有涉及人脸检测的接口内部会自动评估人脸质量，返回 `quality` 字段：

| 等级 | 条件 | 能否用于注册/识别 |
|---|---|---|
| `good` | 人脸宽高 ≥ 120px，亮度 80-180，清晰度 ≥ 100 | 可以 |
| `medium` | 人脸宽高 ≥ 80px，亮度 50-200，清晰度 ≥ 50 | 可以（建议重拍） |
| `poor` | 人脸过小、过暗/过亮、或模糊 | 不可以 |

---

## 3. 人脸采集流程（注册）

人脸采集用于将新用户的人脸特征录入系统，分为两种方式：**注册时同步采集**和**独立补采**。

### 3.1 注册新用户（含人脸采集）

**接口**: `POST /api/users`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| employee_id | string (Form) | 是 | 工号，唯一标识，1-50 字符 |
| name | string (Form) | 是 | 姓名，1-100 字符 |
| department | string (Form) | 否 | 部门名称 |
| face_image | file (File) | 否 | 人脸照片，JPEG/PNG |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/users \
  -F "employee_id=001" \
  -F "name=张三" \
  -F "department=技术部" \
  -F "face_image=@photo.jpg"
```

**成功响应** `200`:

```json
{
  "id": 1,
  "employee_id": "001",
  "name": "张三",
  "department": "技术部",
  "status": 1,
  "face_encoding_path": "data/faces/encodings/001.npy",
  "face_image_path": "data/faces/images/001.jpg",
  "created_at": "2026-04-06T14:00:00",
  "updated_at": null,
  "face_detected": true,
  "face_quality": "good"
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 用户 ID（后续接口需要） |
| face_encoding_path | string \| null | 人脸特征文件路径，null 表示未录入人脸 |
| face_detected | bool | 本次请求中是否成功检测并录入人脸 |
| face_quality | string \| null | 人脸质量等级：`good` / `medium` / `poor` / `null` |

**关键行为**:

- `face_image` 为可选字段。不传则仅创建用户，不录入人脸
- 即使传了 `face_image`，如果图片中无人脸或质量为 `poor`，`face_detected` 仍为 `false`，但用户创建成功
- 用户创建成功后可通过 **3.3 独立补采** 重新录入人脸

**错误响应**:

| HTTP 状态码 | 场景 | 响应体 |
|---|---|---|
| 400 | 工号已存在 | `{"detail": "工号已存在"}` |
| 422 | 缺少必填字段 | `{"detail": [{"loc": ["body", "employee_id"], "msg": "field required"}]}` |

---

### 3.2 人脸预检测（注册前校验）

**接口**: `POST /api/face/detect`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| image | file (File) | 是 | 待检测的图片 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/face/detect \
  -F "image=@photo.jpg"
```

**成功响应** `200`:

```json
{
  "faces_detected": 1,
  "faces": [
    {
      "box": {
        "top": 100,
        "right": 400,
        "bottom": 350,
        "left": 150
      },
      "quality": "good"
    }
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| faces_detected | int | 检测到的人脸数量 |
| faces[].box | object | 人脸在图片中的位置（像素坐标） |
| faces[].box.top | int | 上边界 y 坐标 |
| faces[].box.right | int | 右边界 x 坐标 |
| faces[].box.bottom | int | 下边界 y 坐标 |
| faces[].box.left | int | 左边界 x 坐标 |
| faces[].quality | string | 质量等级：`good` / `medium` / `poor` |

**前端对接建议**:

1. 用户拍照后先调用此接口
2. `faces_detected === 0` → 提示"未检测到人脸，请重拍"
3. `faces_detected > 1` → 提示"检测到多张人脸，请确保只有一人"
4. `quality === "poor"` → 提示"人脸质量较差，请调整光线或位置"
5. `quality` 为 `good` 或 `medium` → 允许继续提交注册

---

### 3.3 独立补采人脸（已有用户重新录入）

**接口**: `POST /api/face/register/{user_id}`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | int (Path) | 是 | 用户 ID |
| image | file (File) | 是 | 人脸照片 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/face/register/1 \
  -F "image=@new_photo.jpg"
```

**成功响应** `200`:

```json
{
  "success": true,
  "user_id": 1,
  "face_detected": true,
  "face_quality": "good",
  "message": "人脸注册成功"
}
```

**人脸检测失败响应** `200`:

```json
{
  "success": false,
  "user_id": 1,
  "face_detected": false,
  "face_quality": null,
  "message": "未检测到人脸"
}
```

**人脸质量差响应** `200`:

```json
{
  "success": false,
  "user_id": 1,
  "face_detected": false,
  "face_quality": "poor",
  "message": "人脸质量较差，请调整光线或位置"
}
```

**多张人脸响应** `200`:

```json
{
  "success": false,
  "user_id": 1,
  "face_detected": false,
  "face_quality": null,
  "message": "检测到多张人脸，请确保只有一人"
}
```

**错误响应**:

| HTTP 状态码 | 场景 | 响应体 |
|---|---|---|
| 404 | 用户 ID 不存在 | `{"detail": "用户不存在"}` |

**关键行为**:

- 如果用户此前已有人脸数据，此接口会**覆盖**旧的人脸特征和照片
- 注册成功后系统自动将新特征加载到内存，立即生效（无需重启）

---

### 3.4 推荐的人脸采集前端对接流程

```
用户点击"拍照"
    │
    ▼
Camera 组件 capturePhoto() → 获得 base64 + File
    │
    ▼
调用 POST /api/face/detect（传入 File）
    │
    ├── faces_detected === 0 → 提示重拍，回到拍照
    ├── faces_detected > 1  → 提示重拍，回到拍照
    ├── quality === "poor"  → 提示重拍，回到拍照
    │
    └── quality 为 good/medium
            │
            ▼
        启用"确认提交"按钮
            │
            ▼
        调用 POST /api/users（注册）或
        调用 POST /api/face/register/{user_id}（补采）
            │
            ├── 成功 → 提示成功，刷新列表
            └── 失败 → 显示错误信息
```

---

## 4. 人脸识别流程（门禁打卡）

### 4.1 单次识别（HTTP）

**接口**: `POST /api/face/recognize`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| image | file (File) | 是 | 待识别的人脸照片 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/face/recognize \
  -F "image=@capture.jpg"
```

**识别成功响应** `200`:

```json
{
  "success": true,
  "user": {
    "id": 1,
    "employee_id": "001",
    "name": "张三",
    "department": "技术部"
  },
  "confidence": 0.9429,
  "liveness_passed": null,
  "reason": null
}
```

**识别失败响应** `200`:

```json
{
  "success": false,
  "user": null,
  "confidence": 0.35,
  "liveness_passed": null,
  "reason": "face_not_recognized"
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| success | bool | 是否识别成功 |
| user | object \| null | 匹配到的用户信息，失败时为 null |
| user.id | int | 用户 ID |
| user.employee_id | string | 工号 |
| user.name | string | 姓名 |
| user.department | string \| null | 部门 |
| confidence | float | 置信度，范围 0.0-1.0，≥ 0.6 判定为匹配 |
| liveness_passed | bool \| null | 此接口不执行活体检测，始终为 null |
| reason | string \| null | 失败原因，见下表 |

**失败原因 `reason` 枚举值**:

| 值 | 含义 | 建议提示 |
|---|---|---|
| `no_face_detected` | 未检测到人脸 | "未检测到人脸，请对准摄像头" |
| `multiple_faces` | 检测到多张人脸 | "检测到多张人脸，请确保只有一人" |
| `poor_quality` | 人脸质量不达标 | "请调整光线或位置" |
| `face_not_recognized` | 人脸特征不匹配任何已注册用户 | "未识别到注册用户" |

---

### 4.2 完整验证（含活体检测）

**接口**: `POST /api/face/verify`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| images | file[] (File) | 是 | 连续帧图像，至少 1 张，建议 3-5 张 |
| check_liveness | bool (Form) | 否 | 是否进行活体检测，默认 `true` |

> **注意**：活体检测需要 ≥ 3 张连续帧图像。如果传入帧数不足 3 张，`liveness_passed` 将为 `null`（跳过活体检测）。

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/face/verify \
  -F "images=@frame1.jpg" \
  -F "images=@frame2.jpg" \
  -F "images=@frame3.jpg" \
  -F "check_liveness=true"
```

**成功响应** `200`:

```json
{
  "success": true,
  "user": {
    "id": 1,
    "employee_id": "001",
    "name": "张三",
    "department": "技术部"
  },
  "confidence": 0.9429,
  "liveness_passed": true,
  "reason": null
}
```

**活体检测失败响应** `200`:

```json
{
  "success": false,
  "user": null,
  "confidence": 0,
  "liveness_passed": false,
  "reason": "liveness_failed"
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| liveness_passed | bool \| null | `true`=通过，`false`=未通过，`null`=跳过（帧数不足或模型未加载） |
| reason | string \| null | 同 4.1，额外增加 `liveness_failed` 表示活体检测未通过 |

> **注意**：如果活体检测模型文件（`shape_predictor_68_face_landmarks.dat`）未部署，`liveness_passed` 始终为 `null`，不影响识别流程。

---

### 4.3 刷脸打卡（识别 + 记录考勤）

#### 上班打卡

**接口**: `POST /api/attendance/check-in`

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| image | file (File) | 是 | 人脸照片 |
| employee_id | string (Form) | 否 | 手动指定工号（识别失败时仍记录考勤） |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/attendance/check-in \
  -F "image=@capture.jpg"
```

**识别成功响应** `200`:

```json
{
  "success": true,
  "action_type": "CHECK_IN",
  "user": {
    "id": 1,
    "employee_id": "001",
    "name": "张三",
    "department": "技术部"
  },
  "confidence": 0.9429,
  "message": "张三 上班打卡成功",
  "record_id": 1
}
```

**识别失败响应** `200`:

```json
{
  "success": false,
  "action_type": "CHECK_IN",
  "user": null,
  "confidence": 0.35,
  "message": "打卡失败: face_not_recognized",
  "record_id": 2
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| success | bool | 人脸是否识别成功 |
| action_type | string | 固定为 `"CHECK_IN"` 或 `"CHECK_OUT"` |
| user | object \| null | 识别到的用户 |
| confidence | float | 识别置信度 |
| message | string | 结果描述 |
| record_id | int | 考勤记录 ID，无论成功失败都会创建记录 |

**关键行为**:

- 即使人脸识别失败（`success: false`），系统仍会创建一条考勤记录（`result: FAILED`）
- 如果传了 `employee_id` 且识别失败，系统会尝试用该工号查找用户并记录
- 系统会自动保存抓拍截图到 `data/faces/images/snapshots/`

#### 下班打卡

**接口**: `POST /api/attendance/check-out`

参数、响应格式与上班打卡完全一致，`action_type` 固定为 `"CHECK_OUT"`。

---

### 4.4 实时识别（WebSocket）

**连接地址**: `ws://<host>:8000/ws/face-stream`

适用于实时刷脸场景，客户端持续发送视频帧，服务端逐帧处理并返回识别结果。

#### 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/face-stream')
```

#### 客户端发送消息格式

```json
{
  "type": "frame",
  "data": "<base64编码的JPEG图像数据>"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| type | string | 固定 `"frame"` |
| data | string | JPEG 图片的 Base64 编码（不含 `data:image/jpeg;base64,` 前缀） |

**心跳**:

```json
{
  "type": "ping"
}
```

服务端回复 `{"type": "pong"}`。

#### 服务端推送消息格式

**状态消息**（处理中）:

```json
{
  "type": "status",
  "data": {
    "stage": "detecting",
    "message": "未检测到人脸，请对准摄像头"
  }
}
```

| stage | 说明 |
|---|---|
| `detecting` | 人脸检测阶段 |
| `quality_check` | 质量检测阶段 |
| `liveness_check` | 活体检测阶段（含帧计数进度） |

**识别结果消息**:

成功：

```json
{
  "type": "result",
  "data": {
    "success": true,
    "user": {
      "id": 1,
      "employee_id": "001",
      "name": "张三",
      "department": "技术部"
    },
    "confidence": 0.9429,
    "action": "door_open",
    "action_type": "CHECK_IN",
    "message": "张三 上班打卡成功"
  }
}
```

失败：

```json
{
  "type": "result",
  "data": {
    "success": false,
    "reason": "face_not_recognized",
    "confidence": 0.35,
    "message": "未识别到注册用户"
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| data.action | string | 固定 `"door_open"`（成功时表示开门指令） |
| data.action_type | string | 自动判断：当日首次识别为 `CHECK_IN`，再次为 `CHECK_OUT` |
| data.reason | string | 失败原因，同 4.1 节 |

**错误消息**:

```json
{
  "type": "error",
  "data": {
    "message": "具体错误信息"
  }
}
```

#### WebSocket 处理流程

```
客户端连接 WebSocket
    │
    ▼
持续发送帧（建议 200ms 间隔）
    │
    ▼
服务端逐帧处理：
    ├── 未检测到人脸 → 推送 status(detecting)
    ├── 多张人脸     → 推送 status(detecting)
    ├── 质量差       → 推送 status(quality_check)
    │
    ├── 帧缓冲未满   → 推送 status(liveness_check, n/5)
    │
    ├── 活体检测失败 → 推送 status(liveness_check)，清空缓冲
    │
    ├── 人脸未匹配   → 推送 result(success=false)，清空缓冲
    │
    └── 识别成功     → 推送 result(success=true)
                          ├── 自动记录考勤
                          ├── 保存抓拍截图
                          └── 触发 3 秒冷却（期间忽略新帧）
```

---

## 5. 人脸比对（1:1）

**接口**: `POST /api/face/compare`

用于比较两张图片中的人脸是否为同一人。

**Content-Type**: `multipart/form-data`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| image1 | file (File) | 是 | 第一张人脸图片 |
| image2 | file (File) | 是 | 第二张人脸图片 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/face/compare \
  -F "image1=@photo_a.jpg" \
  -F "image2=@photo_b.jpg"
```

**成功响应** `200`:

```json
{
  "match": true,
  "distance": 0.0571,
  "confidence": 0.9429,
  "message": "匹配成功"
}
```

**不匹配响应** `200`:

```json
{
  "match": false,
  "distance": 0.6500,
  "confidence": 0.3500,
  "message": "不匹配"
}
```

**无人脸响应** `200`:

```json
{
  "match": false,
  "distance": 1.0,
  "confidence": 0.0,
  "message": "未检测到人脸"
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| match | bool | 是否为同一人（confidence ≥ 0.6） |
| distance | float | 人脸特征向量欧氏距离，越小越相似 |
| confidence | float | 置信度 = 1 - distance |

---

## 6. 错误处理

所有接口在异常情况下返回统一格式：

```json
{
  "detail": "错误描述信息"
}
```

| HTTP 状态码 | 含义 | 常见场景 |
|---|---|---|
| 400 | 请求参数错误 | 缺少必填字段、格式不正确 |
| 401 | 未授权 | Token 缺失或已过期（仅管理员接口） |
| 404 | 资源不存在 | 用户 ID 无效、考勤记录不存在 |
| 422 | 数据验证失败 | 字段类型错误、超出长度限制 |
| 500 | 服务器内部错误 | 人脸处理异常、数据库错误 |

**注意**：人脸检测/识别相关接口的"失败"（如未检测到人脸、识别不匹配）返回 HTTP 200，通过响应体中的 `success` 字段区分，不使用 HTTP 错误码。

---

## 7. 附录

### 7.1 图片采集建议

| 项目 | 建议值 |
|---|---|
| 分辨率 | ≥ 640×480 |
| 人脸占比 | 占画面 30%-60% |
| 人脸大小 | ≥ 120×120 像素 |
| 光照 | 均匀正面光，避免逆光/侧光 |
| 背景 | 简单纯色背景 |
| 角度 | 正面，偏转 ≤ 15° |
| 表情 | 自然表情，嘴部闭合 |
| 遮挡 | 无口罩、墨镜、帽子 |

### 7.2 识别阈值说明

默认识别阈值 `FACE_THRESHOLD = 0.6`，含义：

| 置信度范围 | 判定 |
|---|---|
| ≥ 0.6 | 匹配成功 |
| < 0.6 | 匹配失败 |

可在 `backend/.env` 中通过 `FACE_THRESHOLD=0.7` 调整（值越高越严格）。

### 7.3 完整接口清单

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 否 | 管理员登录 |
| POST | `/api/auth/logout` | 否 | 退出登录 |
| GET | `/api/auth/check` | 否 | 检查登录状态 |
| POST | `/api/face/detect` | 否 | 人脸检测 |
| POST | `/api/face/recognize` | 否 | 人脸识别（无活体） |
| POST | `/api/face/verify` | 否 | 完整验证（含活体） |
| POST | `/api/face/register/{user_id}` | 否 | 人脸注册/更新 |
| POST | `/api/face/compare` | 否 | 1:1 人脸比对 |
| POST | `/api/users` | 否 | 注册新用户（含人脸） |
| GET | `/api/users` | 是 | 用户列表 |
| GET | `/api/users/{user_id}` | 是 | 用户详情 |
| PUT | `/api/users/{user_id}` | 是 | 更新用户信息 |
| DELETE | `/api/users/{user_id}` | 是 | 删除用户 |
| POST | `/api/attendance/check-in` | 否 | 上班打卡 |
| POST | `/api/attendance/check-out` | 否 | 下班打卡 |
| GET | `/api/attendance` | 是 | 考勤记录列表 |
| GET | `/api/attendance/stats` | 是 | 考勤统计 |
| GET | `/api/attendance/export` | 是 | 导出 Excel |
| WS | `/ws/face-stream` | 否 | 实时人脸识别 |
