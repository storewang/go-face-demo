import secrets
import time
from typing import Optional, Set


# In-memory token store (single-server, sufficient for <50 users)
_active_tokens: Set[str] = set()
TOKEN_EXPIRE_SECONDS = 8 * 3600  # 8 hours


def create_token() -> str:
    """生成认证令牌"""
    token = secrets.token_hex(32)
    _active_tokens.add(token)
    return token


def validate_token(token: str) -> bool:
    """验证令牌是否有效"""
    return token in _active_tokens


def revoke_token(token: str) -> None:
    """撤销令牌"""
    _active_tokens.discard(token)
