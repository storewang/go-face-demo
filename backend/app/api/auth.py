from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
import warnings
import logging

from app.config import settings
from app.utils.auth import verify_password, hash_password, create_access_token, verify_token
from app.main import limiter

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
    
    access_token = create_access_token(data={"sub": "admin"})
    
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
