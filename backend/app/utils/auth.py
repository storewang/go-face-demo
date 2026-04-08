from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Header

from jose import JWTError, jwt
from passlib.hash import bcrypt

from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return bcrypt.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """对密码进行bcrypt哈希"""
    return bcrypt.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌
    
    Args:
        data: 包含sub(用户标识)等信息的字典
        expires_delta: 可选的过期时间增量
        
    Returns:
        JWT token字符串
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证JWT令牌
    
    Args:
        token: JWT token字符串
        
    Returns:
        payload字典，验证失败返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "access":
            return None
            
        return payload
    except JWTError:
        return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI依赖项：获取当前认证用户
    
    从Authorization Header中提取并验证JWT token
    
    Raises:
        HTTPException: 未提供令牌或令牌无效/过期
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证令牌格式错误")
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
    
    return payload
