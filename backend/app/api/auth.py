from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
import warnings
import logging

from app.config import settings
from app.utils.auth import verify_password, hash_password, create_access_token, verify_token
from app.rate_limit import limiter
from datetime import datetime
from app.schemas.user import PinVerifyRequest
from app.models import User, AttendanceLog, ActionType, ResultType
from app.database import SessionLocal
from app.utils.auth import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])

# 内存存储首次启动时自动生成的密码哈希(仅用于过渡期)
_auto_generated_hash: Optional[str] = None


class LoginRequest(BaseModel):
    password: str


def _get_admin_hash() -> Optional[str]:
    """
    获取管理员密码哈希
    
    优先级:
    1. 环境变量配置的管理员密码哈希
    2. 首次启动时自动生成的哈希(过渡期)
    """
    if settings.ADMIN_PASSWORD_HASH:
        return settings.ADMIN_PASSWORD_HASH
    
    global _auto_generated_hash
    return _auto_generated_hash


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    admin_hash = _get_admin_hash()
    
    if not admin_hash:
        if settings.ADMIN_PASSWORD:
            global _auto_generated_hash
            _auto_generated_hash = hash_password(settings.ADMIN_PASSWORD)
            logger.warning("首次启动: 已自动将ADMIN_PASSWORD哈希存储在内存中，请尽快配置ADMIN_PASSWORD_HASH")
            warnings.warn("已使用明文密码生成哈希，请配置ADMIN_PASSWORD_HASH环境变量", UserWarning)
            admin_hash = _auto_generated_hash
        else:
            raise HTTPException(
                status_code=500,
                detail="管理员密码未配置，请设置ADMIN_PASSWORD或ADMIN_PASSWORD_HASH环境变量"
            )
    
    if not verify_password(body.password, admin_hash):
        raise HTTPException(status_code=401, detail="密码错误")
    
    access_token = create_access_token(data={
        "sub": "admin",
        "role": "super_admin",
        "department": "admin"
    })
    
    return {
        "code": 200,
        "data": {"token": access_token},
        "message": "登录成功"
    }


@router.post("/logout")
async def logout():
    """JWT无状态，客户端删除token即可"""
    return {"code": 200, "message": "已退出登录"}


@router.get("/check")
async def check_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"authenticated": False}
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    
    return {"authenticated": payload is not None}


@router.post("/pin-verify")
@limiter.limit("3/minute")  # Strict rate limit for security
async def pin_verify(request: Request, body: PinVerifyRequest):
    """PIN码验证开门（摄像头故障时后备通道）"""
    db = SessionLocal()
    try:
        # 查询所有设置了PIN且状态为启用的用户
        candidates = db.query(User).filter(User.pin_code.isnot(None), User.status == 1).all()
        from app.schemas.user import UserResponse
        for u in candidates:
            if verify_password(body.pin_code, u.pin_code):
                user_resp = UserResponse.model_validate(u)
                # 记录考勤（和 websocket 逻辑保持一致）
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_count = (
                    db.query(AttendanceLog)
                    .filter(AttendanceLog.user_id == u.id, AttendanceLog.created_at >= today_start)
                    .count()
                )
                action_type = ActionType.CHECK_OUT if today_count > 0 else ActionType.CHECK_IN
                record = AttendanceLog(
                    user_id=u.id,
                    employee_id=u.employee_id,
                    name=u.name,
                    action_type=action_type.value,
                    result=ResultType.SUCCESS.value,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return {
                    "code": 200,
                    "data": {
                        "user": user_resp.model_dump(),
                        "action": "door_open",
                        "action_type": action_type.value,
                    },
                    "message": "PIN验证成功",
                }
        # 未匹配到任何用户
        return {"code": 200, "data": {"authenticated": False}, "message": "PIN验证失败"}
    finally:
        db.close()
