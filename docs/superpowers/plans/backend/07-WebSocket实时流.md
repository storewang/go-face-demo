# 07 - WebSocket 实时流

> 模块: 实时视频流人脸识别
> 优先级: P1
> 依赖: 06-考勤管理
> 预计时间: 0.5天

## 一、目标

实现 WebSocket 实时视频流识别，支持门禁场景的实时刷脸。

## 二、技术方案

### 2.1 通信协议

**Client → Server (发送帧)**
```json
{
  "type": "frame",
  "data": "<base64_encoded_image>"
}
```

**Server → Client (识别结果)**
```json
{
  "type": "result",
  "data": {
    "success": true,
    "user": {...},
    "confidence": 0.85,
    "action": "door_open"
  }
}
```

**Server → Client (状态更新)**
```json
{
  "type": "status",
  "data": {
    "stage": "liveness_check",
    "message": "请眨眼确认..."
  }
}
```

### 2.2 流程设计

```
客户端连接 WebSocket
       │
       ▼
  开始发送视频帧 (base64)
       │
       ▼
  服务端检测人脸
       │
       ├─ 未检测到 → 返回 "no_face"
       │
       ├─ 检测到 → 累积帧数
       │       │
       │       ▼
       │   达到活体检测帧数 (3-5帧)
       │       │
       │       ▼
       │   活体检测
       │       │
       │       ├─ 失败 → 返回 "liveness_failed"
       │       │
       │       └─ 成功 → 人脸识别
       │               │
       │               ▼
       │           返回识别结果
       │
       ▼
  等待下一次（冷却时间 3秒）
```

## 三、代码实现

### 3.1 WebSocket 连接管理器 (app/websocket/manager.py)

```python
from fastapi import WebSocket
from typing import Dict, Set
import asyncio
import json

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.session_data: Dict[WebSocket, dict] = {}
    
    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.session_data[websocket] = {
            "frames": [],
            "face_locations": [],
            "last_result_time": 0
        }
    
    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self.active_connections.discard(websocket)
        self.session_data.pop(websocket, None)
    
    async def send_json(self, websocket: WebSocket, data: dict):
        """发送 JSON 消息"""
        await websocket.send_json(data)
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection in self.active_connections:
            await connection.send_json(message)
    
    def get_session(self, websocket: WebSocket) -> dict:
        """获取会话数据"""
        return self.session_data.get(websocket, {})
    
    def update_session(self, websocket: WebSocket, data: dict):
        """更新会话数据"""
        if websocket in self.session_data:
            self.session_data[websocket].update(data)

# 全局管理器
manager = ConnectionManager()
```

### 3.2 WebSocket 端点 (app/api/websocket.py)

```python
import base64
import json
import asyncio
import numpy as np
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.manager import manager
from app.services.face_service import face_service
from app.services.liveness_service import get_liveness_service
from app.database import SessionLocal
from app.models import AttendanceLog, ActionType, ResultType
from app.config import settings
from app.utils.face_utils import FaceUtils
import cv2

# 配置
FRAME_BUFFER_SIZE = 5  # 活体检测所需帧数
COOLDOWN_SECONDS = 3   # 识别成功后冷却时间

async def process_frame(websocket: WebSocket, frame_data: str, session: dict):
    """
    处理单帧图像
    
    Args:
        websocket: WebSocket 连接
        frame_data: base64 编码的图像
        session: 会话数据
    """
    try:
        # 解码图像
        image_bytes = base64.b64decode(frame_data)
        image = FaceUtils.load_image_from_bytes(image_bytes)
        
        # 检测人脸
        faces = face_service.detect_faces(image)
        
        if len(faces) == 0:
            await manager.send_json(websocket, {
                "type": "status",
                "data": {
                    "stage": "detecting",
                    "message": "未检测到人脸，请对准摄像头"
                }
            })
            return
        
        if len(faces) > 1:
            await manager.send_json(websocket, {
                "type": "status",
                "data": {
                    "stage": "detecting",
                    "message": "检测到多张人脸，请确保只有一人"
                }
            })
            return
        
        face = faces[0]
        
        # 检查质量
        if face["quality"] == "poor":
            await manager.send_json(websocket, {
                "type": "status",
                "data": {
                    "stage": "quality_check",
                    "message": "请调整光线或位置"
                }
            })
            return
        
        # 添加到帧缓冲
        session["frames"].append(image)
        session["face_locations"].append(face["box"])
        
        # 检查是否达到活体检测帧数
        if len(session["frames"]) < FRAME_BUFFER_SIZE:
            await manager.send_json(websocket, {
                "type": "status",
                "data": {
                    "stage": "liveness_check",
                    "message": f"请保持不动 ({len(session['frames'])}/{FRAME_BUFFER_SIZE})"
                }
            })
            return
        
        # 活体检测
        liveness = get_liveness_service()
        liveness_result = liveness.check_liveness(
            session["frames"],
            session["face_locations"]
        )
        
        if not liveness_result["passed"]:
            await manager.send_json(websocket, {
                "type": "status",
                "data": {
                    "stage": "liveness_check",
                    "message": liveness_result["message"]
                }
            })
            # 清空缓冲，重新开始
            session["frames"] = []
            session["face_locations"] = []
            return
        
        # 人脸识别
        user, confidence = face_service.recognize_face(face["encoding"])
        
        if user is None:
            await manager.send_json(websocket, {
                "type": "result",
                "data": {
                    "success": False,
                    "reason": "face_not_recognized",
                    "confidence": confidence,
                    "message": "未识别到注册用户"
                }
            })
            # 清空缓冲
            session["frames"] = []
            session["face_locations"] = []
            return
        
        # 识别成功
        # 保存考勤记录
        db = SessionLocal()
        try:
            # 保存快照
            snapshot_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user['employee_id']}.jpg"
            snapshot_path = str(settings.IMAGES_DIR / "snapshots" / snapshot_filename)
            (settings.IMAGES_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
            cv2.imwrite(snapshot_path, cv2.cvtColor(session["frames"][-1], cv2.COLOR_RGB2BGR))
            
            # 判断打卡类型
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_records = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user["id"],
                AttendanceLog.created_at >= today_start
            ).count()
            
            action_type = ActionType.CHECK_OUT if today_records > 0 else ActionType.CHECK_IN
            
            # 创建记录
            record = AttendanceLog(
                user_id=user["id"],
                employee_id=user["employee_id"],
                name=user["name"],
                action_type=action_type,
                confidence=confidence,
                snapshot_path=snapshot_path,
                result=ResultType.SUCCESS
            )
            db.add(record)
            db.commit()
        finally:
            db.close()
        
        # 返回结果
        action_message = "下班打卡成功" if action_type == ActionType.CHECK_OUT else "上班打卡成功"
        
        await manager.send_json(websocket, {
            "type": "result",
            "data": {
                "success": True,
                "user": user,
                "confidence": confidence,
                "action": "door_open",
                "action_type": action_type.value,
                "message": f"{user['name']} {action_message}"
            }
        })
        
        # 清空缓冲
        session["frames"] = []
        session["face_locations"] = []
        
        # 记录最后识别时间（用于冷却）
        session["last_result_time"] = datetime.now().timestamp()
        
    except Exception as e:
        print(f"Error processing frame: {e}")
        await manager.send_json(websocket, {
            "type": "error",
            "data": {"message": str(e)}
        })

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点"""
    await manager.connect(websocket)
    session = manager.get_session(websocket)
    
    try:
        while True:
            # 检查冷却时间
            last_result = session.get("last_result_time", 0)
            if datetime.now().timestamp() - last_result < COOLDOWN_SECONDS:
                await asyncio.sleep(0.5)
                continue
            
            # 接收消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "frame":
                frame_data = message.get("data", "")
                await process_frame(websocket, frame_data, session)
            
            elif message.get("type") == "ping":
                await manager.send_json(websocket, {"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
```

### 3.3 注册路由 (app/main.py)

```python
from fastapi import WebSocket
from app.api.websocket import websocket_endpoint

# 添加 WebSocket 路由
@app.websocket("/ws/face-stream")
async def ws_face_stream(websocket: WebSocket):
    await websocket_endpoint(websocket)
```

## 四、前端示例 (Vue 3)

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/face-stream')

ws.onopen = () => {
  console.log('WebSocket connected')
  startCamera()
}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'status') {
    // 显示状态提示
    statusMessage.value = data.data.message
  }
  else if (data.type === 'result') {
    if (data.data.success) {
      // 显示识别成功
      showSuccess(data.data.user, data.data.message)
      playDoorOpenAnimation()
    } else {
      // 显示识别失败
      showFailed(data.data.message)
    }
  }
}

// 发送视频帧
function sendFrame(imageData) {
  // 将 canvas 转为 base64
  const base64 = imageData.split(',')[1]
  
  ws.send(JSON.stringify({
    type: 'frame',
    data: base64
  }))
}

// 摄像头捕获
function startCamera() {
  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      videoElement.srcObject = stream
      
      setInterval(() => {
        // 捕获帧并发送
        canvas.getContext('2d').drawImage(videoElement, 0, 0)
        const imageData = canvas.toDataURL('image/jpeg', 0.8)
        sendFrame(imageData)
      }, 200)  // 每200ms发送一帧
    })
}
```

## 五、实现步骤

```bash
# Step 1: 创建目录
mkdir -p app/websocket

# Step 2: 创建文件
touch app/websocket/__init__.py
touch app/websocket/manager.py
touch app/api/websocket.py

# Step 3: 更新 main.py 添加 WebSocket 路由

# Step 4: 测试
# 使用前端页面或 WebSocket 客户端工具测试
```

## 六、测试工具

### 6.1 Python 测试客户端

```python
import asyncio
import websockets
import base64
import json
from pathlib import Path

async def test_websocket():
    uri = "ws://localhost:8000/ws/face-stream"
    
    async with websockets.connect(uri) as ws:
        # 读取测试图像
        with open("test_face.jpg", "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        # 发送帧
        for i in range(5):
            await ws.send(json.dumps({
                "type": "frame",
                "data": image_data
            }))
            
            # 接收响应
            response = await ws.recv()
            print(json.loads(response))
            
            await asyncio.sleep(0.5)

asyncio.run(test_websocket())
```

## 七、验收标准

- [ ] WebSocket 可正常连接
- [ ] 发送帧后收到状态消息
- [ ] 活体检测流程正常
- [ ] 识别成功返回用户信息
- [ ] 识别失败返回正确错误
- [ ] 考勤记录正确创建
- [ ] 冷却时间生效
- [ ] 连接断开正确清理

## 八、性能优化

1. **帧率控制**: 客户端限制发送频率 (5-10 fps)
2. **图像压缩**: 使用 JPEG 压缩减少数据量
3. **分辨率**: 降低到 640x480 足够
4. **异步处理**: 使用 asyncio 并发处理多连接
5. **连接限制**: 设置最大连接数

## 九、注意事项

1. **资源释放**: 确保连接断开时清理资源
2. **异常处理**: 捕获所有可能的异常
3. **并发安全**: 注意共享资源的并发访问
4. **内存管理**: 及时清空帧缓冲
