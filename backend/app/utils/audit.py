"""审计日志 HMAC 签名工具"""
import hmac
import hashlib
import json
from typing import Optional
from app.config import settings

def compute_hmac(event_type: str, user_id: Optional[int], timestamp: str, raw_data: str) -> str:
    """计算审计记录的 HMAC-SHA256 签名"""
    message = f"{event_type}|{user_id}|{timestamp}|{raw_data}"
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_hmac(signature: str, event_type: str, user_id: Optional[int], timestamp: str, raw_data: str) -> bool:
    """验证审计记录签名是否匹配"""
    expected = compute_hmac(event_type, user_id, timestamp, raw_data)
    return hmac.compare_digest(signature, expected)
