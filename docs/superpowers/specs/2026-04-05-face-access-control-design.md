# 人脸识别门禁系统设计文档

> 创建日期: 2026-04-05

## 一、项目概述

### 1.1 目标
构建一个小型人脸识别门禁演示系统，支持用户注册、实时刷脸识别、活体检测和考勤记录导出。

### 1.2 需求范围

| 项目 | 选择 |
|------|------|
| 规模 | <50人，单门禁点 |
| 硬件 | PC + USB摄像头 |
| 后端 | Python FastAPI |
| 前端 | Vue 3 + Element Plus |
| 数据库 | SQLite |
| 人脸识别 | face_recognition |
| 活体检测 | 眨眼/点头动作检测 |
| 开门控制 | 界面模拟显示 |
| 考勤 | 完整记录 + Excel导出 |

### 1.3 技术栈

**后端:**
- Python 3.10+
- FastAPI + Uvicorn
- SQLite + SQLAlchemy
- face_recognition (dlib)
- OpenCV
- pandas + openpyxl (Excel导出)

**前端:**
- Vue 3 + Vite
- Element Plus
- Pinia (状态管理)
- Vue Router

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      用户界面层                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  用户注册    │  │  实时刷脸    │  │   考勤记录      │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│                   Vue 3 + Element Plus                   │
│                   端口: 5173                             │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP/WebSocket
┌───────────────────────▼─────────────────────────────────┐
│                     API 服务层                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ 用户管理  │ │ 人脸识别  │ │ 活体检测  │ │ 考勤管理   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│                   FastAPI + Uvicorn                      │
│                   端口: 8000                             │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                     数据存储层                           │
│  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │   SQLite     │  │   文件存储 (人脸图片/特征)      │  │
│  │   用户/考勤   │  │   data/faces/                  │  │
│  └──────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 三、项目目录结构

```
face_scan/
├── backend/                    # 后端 FastAPI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # SQLite 连接
│   │   ├── models/            # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   └── attendance.py
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   └── attendance.py
│   │   ├── api/               # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── users.py       # 用户管理
│   │   │   ├── face.py        # 人脸识别
│   │   │   └── attendance.py  # 考勤记录
│   │   ├── services/          # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── face_service.py      # 人脸检测/识别
│   │   │   ├── liveness_service.py  # 活体检测
│   │   │   └── export_service.py    # Excel 导出
│   │   └── utils/             # 工具函数
│   │       ├── __init__.py
│   │       └── face_utils.py
│   ├── data/                  # 数据存储
│   │   ├── face_scan.db       # SQLite 数据库
│   │   └── faces/             # 人脸图片存储
│   │       ├── images/        # 原图
│   │       └── encodings/     # 特征向量 .npy
│   ├── requirements.txt
│   └── run.py                 # 启动脚本
│
├── frontend/                  # 前端 Vue 3
│   ├── src/
│   │   ├── views/
│   │   │   ├── Register.vue   # 用户注册
│   │   │   ├── Scan.vue       # 实时刷脸
│   │   │   └── Records.vue    # 考勤记录
│   │   ├── components/
│   │   │   ├── Camera.vue     # 摄像头组件
│   │   │   └── FaceCapture.vue
│   │   ├── api/               # API 调用
│   │   │   └── index.ts
│   │   ├── stores/            # Pinia 状态管理
│   │   │   └── user.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docs/                      # 文档
│   └── superpowers/
│       └── specs/
├── CLAUDE.md
└── README.md
```

---

## 四、数据库设计

### 4.1 用户表 (users)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| employee_id | VARCHAR(50) | 工号，唯一 |
| name | VARCHAR(100) | 姓名 |
| department | VARCHAR(100) | 部门 |
| face_encoding_path | VARCHAR(255) | 人脸特征文件路径 |
| face_image_path | VARCHAR(255) | 人脸原图路径 |
| status | INTEGER | 状态: 1=启用, 0=禁用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 4.2 考勤记录表 (attendance_logs)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| user_id | INTEGER | 用户ID，外键 |
| employee_id | VARCHAR(50) | 工号（冗余存储） |
| name | VARCHAR(100) | 姓名（冗余存储） |
| action_type | VARCHAR(20) | 类型: CHECK_IN/CHECK_OUT |
| confidence | REAL | 识别置信度 (0-1) |
| snapshot_path | VARCHAR(255) | 抓拍图路径 |
| result | VARCHAR(20) | 结果: SUCCESS/FAILED |
| created_at | DATETIME | 创建时间 |

### 4.3 系统配置表 (system_config)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| config_key | VARCHAR(100) | 配置键，唯一 |
| config_value | TEXT | 配置值 |
| description | VARCHAR(255) | 描述 |

**预置配置:**
- `face_threshold`: 识别阈值，默认 0.6
- `liveness_frames`: 活体检测帧数，默认 5
- `auto_check_out_hours`: 自动下班打卡时间（小时）

---

## 五、API 接口设计

### 5.1 用户管理

**GET /api/users** - 获取用户列表
```json
// Response
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "employee_id": "10001",
        "name": "张三",
        "department": "技术部",
        "status": 1,
        "created_at": "2024-01-15T10:00:00"
      }
    ],
    "total": 1
  }
}
```

**POST /api/users** - 注册新用户
```json
// Request (multipart/form-data)
{
  "employee_id": "10001",
  "name": "张三",
  "department": "技术部",
  "face_image": <file>
}

// Response
{
  "code": 200,
  "data": {
    "id": 1,
    "employee_id": "10001",
    "name": "张三",
    "face_detected": true,
    "face_quality": "good"
  }
}
```

**DELETE /api/users/{id}** - 删除用户

### 5.2 人脸识别

**POST /api/face/detect** - 检测人脸
```json
// Request (multipart/form-data)
{
  "image": <file>
}

// Response
{
  "code": 200,
  "data": {
    "faces_detected": 1,
    "faces": [
      {
        "box": [top, right, bottom, left],
        "quality": "good"
      }
    ]
  }
}
```

**POST /api/face/verify** - 完整验证流程
```json
// Request (multipart/form-data)
{
  "image": <file>,
  "check_liveness": true
}

// Response (成功)
{
  "code": 200,
  "data": {
    "success": true,
    "user": {
      "id": 1,
      "employee_id": "10001",
      "name": "张三",
      "department": "技术部"
    },
    "confidence": 0.85,
    "liveness_passed": true
  }
}

// Response (失败)
{
  "code": 200,
  "data": {
    "success": false,
    "reason": "face_not_recognized",  // 或 liveness_failed
    "confidence": 0.45
  }
}
```

### 5.3 考勤管理

**GET /api/attendance** - 获取考勤记录
```
Query params:
- start_date: 开始日期 (YYYY-MM-DD)
- end_date: 结束日期 (YYYY-MM-DD)
- employee_id: 工号 (可选)
- page: 页码
- page_size: 每页数量
```

**POST /api/attendance/check-in** - 上班打卡
```json
// Request (multipart/form-data)
{
  "image": <file>,
  "employee_id": "10001"  // 可选，手动指定
}
```

**GET /api/attendance/export** - 导出 Excel
```
Query params:
- start_date: 开始日期
- end_date: 结束日期
- format: excel

Response: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

### 5.4 WebSocket

**WS /ws/face-stream** - 实时视频流识别
```json
// Client -> Server (发送帧)
{
  "type": "frame",
  "data": "<base64_encoded_image>"
}

// Server -> Client (识别结果)
{
  "type": "result",
  "data": {
    "success": true,
    "user": {...},
    "confidence": 0.85,
    "action": "door_open"
  }
}

// Server -> Client (状态更新)
{
  "type": "status",
  "data": {
    "stage": "liveness_check",
    "message": "请眨眼确认..."
  }
}
```

---

## 六、核心模块设计

### 6.1 人脸服务 (FaceService)

```python
class FaceService:
    """人脸检测与识别服务"""

    def __init__(self):
        self.known_encodings: List[np.ndarray] = []
        self.known_users: List[dict] = []
        self._load_known_faces()

    def detect_faces(self, image: np.ndarray) -> List[dict]:
        """
        检测图像中的人脸
        Returns: [{"box": (t,r,b,l), "encoding": np.ndarray}]
        """

    def get_face_quality(self, image: np.ndarray, location: tuple) -> str:
        """
        评估人脸质量
        Returns: "good" | "medium" | "poor"
        """

    def register_face(self, user_id: int, image: np.ndarray) -> dict:
        """
        注册用户人脸
        - 检测人脸
        - 检查质量
        - 提取特征
        - 保存 .npy 文件
        """

    def recognize_face(self, encoding: np.ndarray) -> Tuple[dict, float]:
        """
        1:N 人脸比对
        Returns: (user_info, confidence)
        """

    def _load_known_faces(self):
        """启动时加载所有已知人脸特征"""
```

### 6.2 活体检测服务 (LivenessService)

```python
class LivenessService:
    """眨眼/点头活体检测"""

    def __init__(self, required_frames: int = 5):
        self.required_frames = required_frames
        self.eye_aspect_ratio_threshold = 0.2
        self.nod_angle_threshold = 15

    def check_liveness(self, frames: List[np.ndarray]) -> dict:
        """
        检测连续帧中的活体特征
        Returns: {
            "passed": bool,
            "blink_detected": bool,
            "nod_detected": bool
        }
        """

    def calculate_ear(self, eye_landmarks: np.ndarray) -> float:
        """计算眼睛纵横比 (Eye Aspect Ratio)"""

    def detect_head_pose(self, landmarks: np.ndarray) -> dict:
        """估计头部姿态角度"""
```

### 6.3 识别流程

```
摄像头帧输入
      │
      ▼
┌─────────────┐
│  人脸检测    │ ──未检测到──▶ 返回等待状态
└─────┬───────┘
      │ 检测到
      ▼
┌─────────────┐
│  质量检查    │ ──质量差──▶ 返回"请调整位置"
└─────┬───────┘
      │ 质量OK
      ▼
┌─────────────┐
│  活体检测    │ ──未通过──▶ 返回"请眨眼/点头"
│ (3-5帧)     │
└─────┬───────┘
      │ 通过
      ▼
┌─────────────┐
│  特征提取    │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   1:N比对   │ ──置信度<0.6──▶ 返回"未识别"
└─────┬───────┘
      │ 匹配成功
      ▼
┌─────────────┐
│  记录考勤    │
└─────┬───────┘
      │
      ▼
  返回用户信息 + "门已开启"
```

---

## 七、前端页面设计

### 7.1 用户注册页 (Register.vue)

**功能:**
- 表单输入：工号、姓名、部门
- 摄像头实时预览
- 人脸质量实时反馈
- 拍照/重拍功能
- 提交注册

**交互流程:**
1. 填写用户信息
2. 开启摄像头
3. 系统检测人脸并显示质量状态
4. 点击拍照，预览确认
5. 提交注册

### 7.2 实时刷脸页 (Scan.vue)

**功能:**
- 全屏摄像头画面
- 实时人脸框标注
- 活体检测提示（"请眨眼"、"请点头"）
- 识别结果展示
- 开门状态动画

**交互流程:**
1. 页面加载，开启摄像头
2. WebSocket 连接后端
3. 实时发送帧数据
4. 接收识别结果
5. 显示用户信息 + 开门动画（3秒）
6. 重置状态，等待下一次

### 7.3 考勤记录页 (Records.vue)

**功能:**
- 日期范围筛选
- 工号/姓名搜索
- 数据表格展示
- 分页
- 导出 Excel

---

## 八、开发阶段

| 阶段 | 任务 | 产出 |
|------|------|------|
| **阶段1: 后端基础** | | |
| | 项目初始化、依赖安装 | backend/ 目录 |
| | SQLite 数据库 + 模型定义 | models/ |
| | 用户 CRUD API | api/users.py |
| **阶段2: 人脸识别核心** | | |
| | face_recognition 集成 | services/face_service.py |
| | 人脸检测 + 特征提取 | |
| | 1:N 比对逻辑 | |
| **阶段3: 活体检测** | | |
| | 眨眼检测 (EAR 算法) | services/liveness_service.py |
| | 点头检测 (头部姿态) | |
| **阶段4: 前端开发** | | |
| | Vue 项目初始化 | frontend/ 目录 |
| | 注册页 + 刷脸页 + 记录页 | views/ |
| | 摄像头组件 | components/Camera.vue |
| | WebSocket 实时视频流 | |
| **阶段5: 考勤与导出** | | |
| | 考勤记录 API | api/attendance.py |
| | Excel 导出功能 | services/export_service.py |
| **阶段6: 联调优化** | | |
| | 前后端联调 | |
| | 识别速度优化 | |
| | 异常处理完善 | |

---

## 九、依赖清单

### 后端 (requirements.txt)
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
python-multipart>=0.0.6
face-recognition>=1.14.0
opencv-python>=4.8.0
numpy>=1.24.0
pandas>=2.1.0
openpyxl>=3.1.0
websockets>=12.0
pydantic>=2.5.0
```

### 前端 (package.json dependencies)
```json
{
  "vue": "^3.4.0",
  "vue-router": "^4.2.0",
  "pinia": "^2.1.0",
  "element-plus": "^2.4.0",
  "axios": "^1.6.0"
}
```

---

## 十、启动方式

### 后端
```bash
cd backend
pip install -r requirements.txt
python run.py
# 访问 http://localhost:8000
# API 文档 http://localhost:8000/docs
```

### 前端
```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```
