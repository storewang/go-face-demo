"""生物特征数据加密/解密模块
使用 Fernet 对称加密保护人脸特征向量
"""
from cryptography.fernet import Fernet
from app.config import settings
import structlog

log = structlog.get_logger(__name__)

class BiometricCrypto:
    """生物特征数据加密/解密"""
    
    def __init__(self):
        raw_key = getattr(settings, "BIOMETRIC_ENCRYPTION_KEY", "")
        if not raw_key:
            # Development mode: generate ephemeral key at runtime
            self._fernet = Fernet(Fernet.generate_key())
            log.warning(
                "BIOMETRIC_ENCRYPTION_KEY is empty; using ephemeral key for this runtime. "
                "Data will not survive restarts in dev mode."
            )
        else:
            key = raw_key.encode()
            self._fernet = Fernet(key)
        
    def encrypt(self, data: bytes) -> bytes:
        """加密二进制数据"""
        return self._fernet.encrypt(data)
    
    def decrypt(self, data: bytes) -> bytes:
        """解密二进制数据"""
        return self._fernet.decrypt(data)


biometric_crypto = BiometricCrypto()
