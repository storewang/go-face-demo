# 05 - 人脸识别 API

> 模块: 人脸识别 REST API + 完整验证流程
> 优先级: P0
> 依赖: 03-人脸识别核心, 04-活体检测
> 预计时间: 0.5天

## 一、目标

实现人脸识别相关的 REST API，整合人脸检测、活体检测、特征识别。

## 二、API 接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/face/detect | 检测人脸 |
| POST | /api/face/verify | 完整验证（含活体检测） |
| POST | /api/face/recognize | 仅人脸识别（无活体检测） |
| POST | /api/face/register | 注册人脸（更新已有用户） |

## 三、代码实现

### 3.1 Pydantic Schemas (app/schemas/face.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class FaceBox(BaseModel):
    """人脸框"""
    top: int
    right: int
    bottom: int
    left: int

class FaceDetectResponse(BaseModel):
    """人脸检测响应"""
    faces_detected: int
    faces: List[dict]  # [{"box": FaceBox, "quality": str}]

class UserInfo(BaseModel):
    """用户信息"""
    id: int
    employee_id: str
    name: str
    department: Optional[str] = None

class FaceVerifyResponse(BaseModel):
    """人脸验证响应"""
    success: bool
    user: Optional[UserInfo] = None
    confidence: float = Field(..., ge=0, le=1)
    liveness_passed: Optional[bool] = None
    reason: Optional[str] = None  # 失败原因

class FaceRegisterResponse(BaseModel):
    """人脸注册响应"""
    success: bool
    user_id: int
    face_detected: bool
    face_quality: Optional[str] = None
    message: str
```

### 3.2 人脸识别 API (app/api/face.py)

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import User
from app.schemas.face import (
    FaceDetectResponse, FaceVerifyResponse, 
    FaceRegisterResponse, UserInfo
)
from app.services.face_service import face_service
from app.services.liveness_service import get_liveness_service
from app.utils.face_utils import FaceUtils

router = APIRouter(prefix="/api/face", tags=["人脸识别"])

@router.post("/detect", response_model=FaceDetectResponse, summary="检测人脸")
def detect_face(
    image: UploadFile = File(..., description="图像文件")
):
    """
    检测图像中的人脸
    
    - 返回人脸位置和质量评估
    - 不进行识别
    """
    # 读取图像
    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)
    
    # 检测人脸
    faces = face_service.detect_faces(img)
    
    # 构建响应
    face_list = []
    for face in faces:
        face_list.append({
            "box": {
                "top": face["box"][0],
                "right": face["box"][1],
                "bottom": face["box"][2],
                "left": face["box"][3]
            },
            "quality": face["quality"]
        })
    
    return FaceDetectResponse(
        faces_detected=len(faces),
        faces=face_list
    )

@router.post("/recognize", response_model=FaceVerifyResponse, summary="人脸识别（无活体检测）")
def recognize_face(
    image: UploadFile = File(..., description="图像文件")
):
    """
    人脸识别（仅识别，不进行活体检测）
    
    - 适用于已登录用户二次验证等场景
    """
    # 读取图像
    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)
    
    # 验证
    result = face_service.verify_user(img)
    
    if result["success"]:
        return FaceVerifyResponse(
            success=True,
            user=UserInfo(**result["user"]),
            confidence=result["confidence"],
            liveness_passed=None,
            reason=None
        )
    else:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=result["confidence"],
            liveness_passed=None,
            reason=result["reason"]
        )

@router.post("/verify", response_model=FaceVerifyResponse, summary="完整验证（含活体检测）")
def verify_face(
    images: List[UploadFile] = File(..., description="连续帧图像（3-5张）"),
    check_liveness: bool = Form(True, description="是否进行活体检测")
):
    """
    完整人脸验证流程
    
    1. 人脸检测
    2. 活体检测（可选）
    3. 特征识别
    4. 返回用户信息
    """
    if len(images) < 1:
        raise HTTPException(status_code=400, detail="至少需要1张图像")
    
    # 读取第一张图像进行检测
    first_image_bytes = images[0].file.read()
    first_img = FaceUtils.load_image_from_bytes(first_image_bytes)
    
    # 检测人脸
    faces = face_service.detect_faces(first_img)
    
    if len(faces) == 0:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="no_face_detected"
        )
    
    if len(faces) > 1:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="multiple_faces"
        )
    
    face = faces[0]
    
    # 质量检查
    if face["quality"] == "poor":
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="poor_quality"
        )
    
    # 活体检测
    liveness_passed = None
    if check_liveness and len(images) >= 3:
        liveness = get_liveness_service()
        
        # 读取所有帧
        frames = [first_img]
        face_locations = [face["box"]]
        
        for img_file in images[1:]:
            img_bytes = img_file.file.read()
            img = FaceUtils.load_image_from_bytes(img_bytes)
            frames.append(img)
            
            # 检测该帧的人脸位置
            frame_faces = face_service.detect_faces(img)
            if frame_faces:
                face_locations.append(frame_faces[0]["box"])
            else:
                # 使用上一帧的位置
                face_locations.append(face_locations[-1])
        
        # 活体检测
        liveness_result = liveness.check_liveness(frames, face_locations)
        liveness_passed = liveness_result["passed"]
        
        if not liveness_passed:
            return FaceVerifyResponse(
                success=False,
                user=None,
                confidence=0,
                liveness_passed=False,
                reason="liveness_failed"
            )
    
    # 人脸识别
    user, confidence = face_service.recognize_face(face["encoding"])
    
    if user is None:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=confidence,
            liveness_passed=liveness_passed,
            reason="face_not_recognized"
        )
    
    return FaceVerifyResponse(
        success=True,
        user=UserInfo(**user),
        confidence=confidence,
        liveness_passed=liveness_passed,
        reason=None
    )

@router.post("/register/{user_id}", response_model=FaceRegisterResponse, summary="注册人脸")
def register_face(
    user_id: int,
    image: UploadFile = File(..., description="人脸照片"),
    db: Session = Depends(get_db)
):
    """
    为已有用户注册/更新人脸
    
    - 检测人脸
    - 评估质量
    - 提取特征
    - 保存文件
    """
    # 检查用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 读取图像
    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)
    
    # 注册人脸
    result = face_service.register_face(user_id, img, db)
    
    return FaceRegisterResponse(
        success=result["success"],
        user_id=user_id,
        face_detected=result["success"],
        face_quality=result.get("quality"),
        message=result["message"]
    )

@router.post("/compare", summary="人脸比对（1:1）")
def compare_faces(
    image1: UploadFile = File(..., description="第一张人脸"),
    image2: UploadFile = File(..., description="第二张人脸")
):
    """
    比对两张人脸是否为同一人
    
    - 返回相似度分数 (0-1)
    - 阈值建议: 0.6
    """
    import face_recognition
    
    # 读取图像
    img1_bytes = image1.file.read()
    img1 = FaceUtils.load_image_from_bytes(img1_bytes)
    
    img2_bytes = image2.file.read()
    img2 = FaceUtils.load_image_from_bytes(img2_bytes)
    
    # 检测人脸
    faces1 = face_service.detect_faces(img1)
    faces2 = face_service.detect_faces(img2)
    
    if len(faces1) == 0 or len(faces2) == 0:
        return {"match": False, "distance": 1.0, "message": "未检测到人脸"}
    
    # 计算距离
    encoding1 = faces1[0]["encoding"]
    encoding2 = faces2[0]["encoding"]
    
    distance = face_recognition.face_distance([encoding1], encoding2)[0]
    confidence = 1 - distance
    
    match = confidence >= face_service.threshold
    
    return {
        "match": bool(match),
        "distance": float(distance),
        "confidence": float(confidence),
        "message": "匹配成功" if match else "不匹配"
    }
```

### 3.3 注册路由 (app/api/__init__.py)

```python
from fastapi import APIRouter
from app.api.users import router as users_router
from app.api.face import router as face_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(face_router)
```

## 四、API 测试

### 4.1 人脸检测

```bash
curl -X POST "http://localhost:8000/api/face/detect" \
  -F "image=@/path/to/face.jpg"
```

响应:
```json
{
  "faces_detected": 1,
  "faces": [
    {
      "box": {"top": 100, "right": 200, "bottom": 200, "left": 100},
      "quality": "good"
    }
  ]
}
```

### 4.2 完整验证

```bash
curl -X POST "http://localhost:8000/api/face/verify" \
  -F "images=@/path/to/frame1.jpg" \
  -F "images=@/path/to/frame2.jpg" \
  -F "images=@/path/to/frame3.jpg" \
  -F "check_liveness=true"
```

响应（成功）:
```json
{
  "success": true,
  "user": {
    "id": 1,
    "employee_id": "10001",
    "name": "张三",
    "department": "技术部"
  },
  "confidence": 0.85,
  "liveness_passed": true,
  "reason": null
}
```

响应（失败）:
```json
{
  "success": false,
  "user": null,
  "confidence": 0.45,
  "liveness_passed": false,
  "reason": "liveness_failed"
}
```

### 4.3 人脸注册

```bash
curl -X POST "http://localhost:8000/api/face/register/1" \
  -F "image=@/path/to/face.jpg"
```

### 4.4 人脸比对

```bash
curl -X POST "http://localhost:8000/api/face/compare" \
  -F "image1=@/path/to/face1.jpg" \
  -F "image2=@/path/to/face2.jpg"
```

## 五、实现步骤

```bash
# Step 1: 创建文件
touch app/schemas/face.py
touch app/api/face.py

# Step 2: 编写代码

# Step 3: 重启服务
python run.py

# Step 4: 测试 API
# 访问 http://localhost:8000/docs
```

## 六、验收标准

- [ ] POST /api/face/detect 可检测人脸并返回位置
- [ ] POST /api/face/recognize 可识别用户（无活体检测）
- [ ] POST /api/face/verify 可完成完整验证流程
- [ ] POST /api/face/register/{user_id} 可为用户注册人脸
- [ ] POST /api/face/compare 可比对两张人脸
- [ ] 未检测到人脸时返回正确错误信息
- [ ] 活体检测失败时返回 liveness_failed
- [ ] 人脸未识别时返回 face_not_recognized
- [ ] 所有接口在 Swagger 文档中可见

## 七、错误码说明

| reason | 说明 |
|--------|------|
| no_face_detected | 未检测到人脸 |
| multiple_faces | 检测到多张人脸 |
| poor_quality | 人脸质量较差 |
| liveness_failed | 活体检测未通过 |
| face_not_recognized | 人脸未匹配到用户 |

## 八、注意事项

1. **多文件上传**: verify 接口需要上传多张图像（3-5帧）
2. **内存管理**: 大图像可能占用较多内存，建议限制文件大小
3. **并发处理**: 高并发场景需考虑服务单例的线程安全
4. **日志记录**: 记录识别结果用于后续分析
