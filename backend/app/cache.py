"""
Redis 缓存模块
提供缓存、Token 黑名单、发布订阅功能
Phase 3 性能优化：识别结果缓存、用户信息缓存
"""
import json
import threading
import redis
import structlog
from app.config import settings
from typing import Optional, Any

_redis_client: Optional["RedisClient"] = None
_singleton_lock = threading.Lock()

log = structlog.get_logger(__name__)


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
        except Exception as e:
            self._available = False
            log.warning("redis_unavailable", error=str(e))

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[str]:
        if not self._available:
            return None
        try:
            return self.client.get(key)
        except Exception as e:
            log.warning("redis_get_failed", key=key, error=str(e))
            return None

    def set(self, key: str, value: str, ttl: int = None):
        if not self._available:
            return
        try:
            if ttl:
                self.client.setex(key, ttl, value)
            else:
                self.client.set(key, value)
        except Exception as e:
            log.warning("redis_set_failed", key=key, error=str(e))

    def delete(self, key: str):
        if not self._available:
            return
        try:
            self.client.delete(key)
        except Exception as e:
            log.warning("redis_delete_failed", key=key, error=str(e))

    def exists(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            log.warning("redis_exists_failed", key=key, error=str(e))
            return False

    def publish(self, channel: str, message: str):
        if not self._available:
            return
        try:
            self.client.publish(channel, message)
        except Exception as e:
            log.warning("redis_publish_failed", channel=channel, error=str(e))

    def get_json(self, key: str) -> Optional[dict]:
        val = self.get(key)
        return json.loads(val) if val else None

    def set_json(self, key: str, value: dict, ttl: int = None):
        self.set(key, json.dumps(value, ensure_ascii=False), ttl)


def get_redis_client() -> RedisClient:
    with _singleton_lock:
        global _redis_client
        if _redis_client is None:
            _redis_client = RedisClient()
        return _redis_client


redis_client = get_redis_client()
