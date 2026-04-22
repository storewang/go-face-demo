"""
test_cleanup.py — CleanupService 数据生命周期管理测试
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
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.cleanup_service import CleanupService
from app.models import User, AttendanceLog
from app.models.audit import AuditLog
from app.models.attendance import ActionType, ResultType


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


@pytest.fixture
def cleanup():
    return CleanupService()


class TestCleanupOldAttendanceLogs:
    """考勤记录清理测试"""

    def test_deletes_old_records(self, cleanup, db_session):
        old_date = datetime.now() - timedelta(days=100)
        old_record = AttendanceLog(
            user_id=1, employee_id="E001", name="Old",
            action_type=ActionType.CHECK_IN, result=ResultType.SUCCESS,
            confidence=0.9, created_at=old_date,
        )
        db_session.add(old_record)
        db_session.commit()

        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.DATA_RETENTION_DAYS = 90
            deleted = cleanup.cleanup_old_attendance_logs(db_session)

        assert deleted == 1

    def test_keeps_recent_records(self, cleanup, db_session):
        recent = AttendanceLog(
            user_id=1, employee_id="E001", name="Recent",
            action_type=ActionType.CHECK_IN, result=ResultType.SUCCESS,
            confidence=0.9,
        )
        db_session.add(recent)
        db_session.commit()

        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.DATA_RETENTION_DAYS = 90
            deleted = cleanup.cleanup_old_attendance_logs(db_session)

        assert deleted == 0
        assert db_session.query(AttendanceLog).count() == 1

    def test_zero_retention_disables_cleanup(self, cleanup, db_session):
        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.DATA_RETENTION_DAYS = 0
            deleted = cleanup.cleanup_old_attendance_logs(db_session)

        assert deleted == 0


class TestCleanupOldAuditLogs:
    """审计日志清理测试"""

    def test_deletes_old_audit_logs(self, cleanup, db_session):
        from app.utils.audit import compute_hmac

        old_ts = (datetime.now() - timedelta(days=400)).isoformat()
        sig = compute_hmac("test", None, old_ts, "{}")
        old_log = AuditLog(
            event_type="test", hmac_signature=sig,
            created_at=datetime.now() - timedelta(days=400),
        )
        db_session.add(old_log)
        db_session.commit()

        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.AUDIT_RETENTION_DAYS = 365
            deleted = cleanup.cleanup_old_audit_logs(db_session)

        assert deleted == 1


class TestCleanupResignedUserFaceData:
    """离职员工人脸数据清理测试"""

    def test_cleans_resigned_users(self, cleanup, db_session):
        with patch("app.services.cleanup_service.storage_service"), \
             patch("app.services.cleanup_service.settings") as mock_settings, \
             patch("pathlib.Path.exists", return_value=False):
            mock_settings.FACE_DATA_DELETE_ON_RESIGN = True
            mock_settings.S3_ENCODING_BUCKET = "encodings"

            user = User(
                employee_id="E001", name="已离职", department="IT",
                status=0, face_encoding_path="/tmp/test_encoding.npy",
            )
            db_session.add(user)
            db_session.commit()

            cleaned = cleanup.cleanup_resigned_user_face_data(db_session)

        assert cleaned == 1
        assert user.face_encoding_path is None

    def test_skips_active_users(self, cleanup, db_session):
        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.FACE_DATA_DELETE_ON_RESIGN = True

            user = User(
                employee_id="E002", name="在职", department="IT",
                status=1, face_encoding_path="/tmp/active.npy",
            )
            db_session.add(user)
            db_session.commit()

            cleaned = cleanup.cleanup_resigned_user_face_data(db_session)

        assert cleaned == 0
        assert user.face_encoding_path == "/tmp/active.npy"

    def test_disabled_when_config_off(self, cleanup, db_session):
        with patch("app.services.cleanup_service.settings") as mock_settings:
            mock_settings.FACE_DATA_DELETE_ON_RESIGN = False
            cleaned = cleanup.cleanup_resigned_user_face_data(db_session)

        assert cleaned == 0
