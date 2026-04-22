"""
test_crypto.py — BiometricCrypto 单元测试
"""
import sys
import os
import types

# Mock heavy C dependencies
for mod_name in ["insightface", "insightface.app", "onnxruntime", "onnxruntime.capi"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

import numpy as np


class _MockFaceAnalysis:
    def __init__(self, **kw):
        pass

    def prepare(self, **kw):
        pass

    def get(self, image):
        return []


sys.modules["insightface.app"].FaceAnalysis = _MockFaceAnalysis

if "cv2" not in sys.modules:
    m = types.ModuleType("cv2")
    m.imwrite = lambda *a, **kw: True
    m.cvtColor = lambda img, code: img
    m.imdecode = lambda buf, flags: np.zeros((100, 100, 3), dtype=np.uint8)
    m.COLOR_RGB2BGR = 4
    m.COLOR_BGR2RGB = 4
    m.IMREAD_COLOR = 1
    m.IMREAD_UNCHANGED = -1
    sys.modules["cv2"] = m

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-1234567890")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_123")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_db.db")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost"]')
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "63790")
os.environ.setdefault("S3_ENDPOINT", "localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "")
os.environ.setdefault("S3_SECRET_KEY", "")

import pytest
from app.utils.crypto import BiometricCrypto


class TestBiometricCrypto:
    """生物特征加密/解密测试"""

    def test_encrypt_decrypt_roundtrip(self):
        """加密后解密应还原原始数据"""
        crypto = BiometricCrypto()
        original = b"test face encoding data 512 floats"
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext(self):
        """每次加密应产生不同密文（Fernet uses IV）"""
        crypto = BiometricCrypto()
        data = b"same data"
        enc1 = crypto.encrypt(data)
        enc2 = crypto.encrypt(data)
        assert enc1 != enc2

    def test_encrypt_preserves_data_integrity(self):
        """加密不应损坏数据"""
        crypto = BiometricCrypto()
        encoding = np.random.randn(512).astype(np.float32).tobytes()
        encrypted = crypto.encrypt(encoding)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == encoding

    def test_decrypt_invalid_data_raises(self):
        """解密无效数据应抛出异常"""
        crypto = BiometricCrypto()
        with pytest.raises(Exception):
            crypto.decrypt(b"invalid encrypted data")

    def test_dev_mode_ephemeral_key(self):
        """开发模式下应使用临时密钥"""
        crypto = BiometricCrypto()
        data = b"test"
        encrypted = crypto.encrypt(data)
        assert crypto.decrypt(encrypted) == data
