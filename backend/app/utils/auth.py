from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Header

from jose import JWTError, jwt
from passlib.hash import bcrypt
import structlog

from app.config import settings
from app.cache import redis_client

log = structlog.get_logger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "role": data.get("role", "employee"),
        "department": data.get("department", ""),
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def _is_token_blacklisted(token: str) -> bool:
    return redis_client.exists(f"token_blacklist:{token}")


def _revoke_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        expire = payload.get("exp", 0)
        ttl = max(expire - int(datetime.now(timezone.utc).timestamp()), 0)
        if ttl > 0:
            redis_client.set(f"token_blacklist:{token}", "1", ttl)
            log.info("token_revoked", user_id=payload.get("sub"))
    except Exception as e:
        log.warning("token_revoke_failed", error=str(e))


def verify_token(token: str) -> Optional[dict]:
    if _is_token_blacklisted(token):
        return None
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
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证令牌格式错误")
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
    
    return payload
