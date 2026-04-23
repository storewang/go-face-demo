"""
test_audit.py — 审计日志 HMAC 签名和 AuditService 测试
"""
import sys
import os
import types

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

os.environ["JWT_SECRET_KEY"] = "test-secret-key-1234567890"
os.environ["ADMIN_PASSWORD"] = "test_admin_123"
os.environ["DATABASE_URL"] = "sqlite:///./test_db.db"
os.environ["CORS_ORIGINS"] = '["http://localhost"]'
os.environ["DEBUG"] = "true"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "63790"
os.environ["S3_ENDPOINT"] = "localhost:9000"
os.environ["S3_ACCESS_KEY"] = ""
os.environ["S3_SECRET_KEY"] = ""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.utils.audit import compute_hmac, verify_hmac
from app.services.audit_service import audit_service
from app.models.audit import AuditLog


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


class TestHMACUtils:
    """HMAC 签名工具测试"""

    def test_compute_hmac_returns_hex_string(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", "{}")
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_verify_hmac_correct_signature(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", '{"test": true}')
        assert verify_hmac(sig, "door_open", 1, "2024-01-01T00:00:00", '{"test": true}') is True

    def test_verify_hmac_tampered_event_type(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", "{}")
        assert verify_hmac(sig, "door_deny", 1, "2024-01-01T00:00:00", "{}") is False

    def test_verify_hmac_tampered_user_id(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", "{}")
        assert verify_hmac(sig, "door_open", 2, "2024-01-01T00:00:00", "{}") is False

    def test_verify_hmac_tampered_timestamp(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", "{}")
        assert verify_hmac(sig, "door_open", 1, "2024-01-01T00:01:00", "{}") is False

    def test_verify_hmac_tampered_data(self):
        sig = compute_hmac("door_open", 1, "2024-01-01T00:00:00", '{"original": true}')
        assert verify_hmac(sig, "door_open", 1, "2024-01-01T00:00:00", '{"tampered": true}') is False

    def test_compute_hmac_with_none_user_id(self):
        sig = compute_hmac("system_alert", None, "2024-01-01T00:00:00", "{}")
        assert verify_hmac(sig, "system_alert", None, "2024-01-01T00:00:00", "{}") is True


class TestAuditService:
    """审计服务测试"""

    def test_record_event_creates_audit_log(self, db_session):
        record = audit_service.record_event(
            db_session,
            event_type="door_open",
            user_id=1,
            employee_id="EMP001",
            user_name="张三",
            device_id=1,
            confidence=0.95,
            extra_data={"method": "face"},
        )
        db_session.commit()

        assert record.id is not None
        assert record.event_type == "door_open"
        assert record.user_id == 1
        assert record.employee_id == "EMP001"
        assert record.confidence == 0.95
        assert len(record.hmac_signature) == 64

    def test_record_event_hmac_verifiable(self, db_session):
        record = audit_service.record_event(
            db_session,
            event_type="pin_open",
            user_id=5,
            extra_data={"pin_attempts": 1},
        )
        db_session.commit()

        assert verify_hmac(
            record.hmac_signature,
            record.event_type,
            record.user_id,
            record.created_at.isoformat() if record.created_at else "",
            record.raw_data,
        ) is True

    def test_record_event_without_optional_fields(self, db_session):
        record = audit_service.record_event(
            db_session,
            event_type="system_alert",
        )
        db_session.commit()

        assert record.id is not None
        assert record.user_id is None
        assert record.confidence is None
        assert record.hmac_signature is not None

    def test_multiple_events_have_unique_signatures(self, db_session):
        r1 = audit_service.record_event(db_session, event_type="door_open", user_id=1)
        r2 = audit_service.record_event(db_session, event_type="door_open", user_id=2)
        db_session.commit()

        assert r1.hmac_signature != r2.hmac_signature
