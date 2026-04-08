from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserRegisterResponse,
)
from app.cache import redis_client
from app.config import settings

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", response_model=UserListResponse, summary="获取用户列表")
def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    department: Optional[str] = Query(None, description="部门筛选"),
    status: Optional[int] = Query(None, ge=0, le=1, description="状态筛选"),
    db: Session = Depends(get_db),
):
    query = db.query(User)

    if department:
        query = query.filter(User.department == department)
    if status is not None:
        query = query.filter(User.status == status)

    total = query.count()
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserResponse, summary="获取用户详情")
def get_user(user_id: int, db: Session = Depends(get_db)):
    # Phase 3 性能优化：用户信息缓存（TTL 10分钟）
    cache_key = f"user:{user_id}"
    cached = redis_client.get_json(cache_key)
    if cached:
        return UserResponse.model_validate(cached)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user_data = UserResponse.model_validate(user).model_dump()
    redis_client.set_json(cache_key, user_data, settings.CACHE_USER_TTL)
    
    return UserResponse.model_validate(user)


@router.post("", response_model=UserRegisterResponse, summary="注册新用户")
def register_user(
    employee_id: str = Form(..., description="工号"),
    name: str = Form(..., description="姓名"),
    department: Optional[str] = Form(None, description="部门"),
    face_image: Optional[UploadFile] = File(None, description="人脸照片"),
    db: Session = Depends(get_db),
):
    exists = db.query(User).filter(User.employee_id == employee_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="工号已存在")

    user = User(employee_id=employee_id, name=name, department=department, status=1)
    db.add(user)
    db.commit()
    db.refresh(user)

    face_detected = False
    face_quality = None

    if face_image:
        try:
            from app.services.face_service import face_service
            from app.utils.face_utils import FaceUtils

            image_bytes = face_image.file.read()
            image = FaceUtils.load_image_from_bytes(image_bytes)

            result = face_service.register_face(user.id, image, db)
            face_detected = result["success"]
            face_quality = result.get("quality")
        except Exception as e:
            import traceback

            traceback.print_exc()
            face_detected = False
            face_quality = None

    db.refresh(user)
    response = UserRegisterResponse.model_validate(user)
    response.face_detected = face_detected
    response.face_quality = face_quality

    return response


@router.put("/{user_id}", response_model=UserResponse, summary="更新用户信息")
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    # 清除用户缓存
    redis_client.delete(f"user:{user_id}")

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", summary="删除用户")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.face_encoding_path:
        import os

        if os.path.exists(user.face_encoding_path):
            os.remove(user.face_encoding_path)
    if user.face_image_path:
        import os

        if os.path.exists(user.face_image_path):
            os.remove(user.face_image_path)

    db.delete(user)
    db.commit()

    # 清除用户缓存
    redis_client.delete(f"user:{user_id}")

    return {"code": 200, "message": "删除成功"}
