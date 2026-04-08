"""
Redis 缓存模块
提供缓存、Token 黑名单、发布订阅功能
Phase 3 性能优化：识别结果缓存、用户信息缓存
"""
import json
import redis
from app.config import settings
from typing import Optional, Any

# 全局 Redis 客户端实例
_redis_client: Optional["RedisClient"] = None


class RedisClient:
    """Redis 客户端封装，支持降级模式（Redis 不可用时自动降级为无缓存）"""

    def __init__(self):
        self.client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=int(getattr(settings, 'REDIS_PORT', 6379)),
            db=int(getattr(settings, 'REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        self._available = False
        try:
            self.client.ping()
            self._available = True
        except Exception:
            # Redis 不可用时降级为无缓存模式
            self._available = False

    @property
    def available(self) -> bool:
        """检查 Redis 是否可用"""
        return self._available

    def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        if not self._available:
            return None
        try:
            return self.client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ttl: int = None):
        """设置缓存值（可选 TTL）"""
        if not self._available:
            return
        try:
            if ttl:
                self.client.setex(key, ttl, value)
            else:
                self.client.set(key, value)
        except Exception:
            pass

    def delete(self, key: str):
        """删除缓存"""
        if not self._available:
            return
        try:
            self.client.delete(key)
        except Exception:
            pass

    def exists(self, key: str) -> bool:
        """检查 key 是否存在"""
        if not self._available:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False

    def publish(self, channel: str, message: str):
        """发布消息到频道"""
        if not self._available:
            return
        try:
            self.client.publish(channel, message)
        except Exception:
            pass

    def get_json(self, key: str) -> Optional[dict]:
        """获取 JSON 格式的缓存值"""
        val = self.get(key)
        return json.loads(val) if val else None

    def set_json(self, key: str, value: dict, ttl: int = None):
        """设置 JSON 格式的缓存值"""
        self.set(key, json.dumps(value, ensure_ascii=False), ttl)


def get_redis_client() -> RedisClient:
    """获取 Redis 客户端单例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


# 导出全局实例供外部使用（兼容旧代码）
redis_client = get_redis_client()
