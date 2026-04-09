"""
go-face-demo 后端集成测试
覆盖所有 API 端点
使用 SQLite 内存数据库 + Mock C 依赖
"""
import sys
import os
import types

# ===== Mock C 依赖 =====
for mod_name in ["dlib", "face_recognition", "face_recognition.api", "face_recognition_models"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

import numpy as np
sys.modules["face_recognition"].face_locations = lambda img, *a, **kw: []
sys.modules["face_recognition"].face_encodings = lambda img, *a, **kw: []
sys.modules["face_recognition"].face_distance = lambda ref, enc: np.array([0.0])

# Mock cv2
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

# ===== 环境变量 =====
os.environ["JWT_SECRET_KEY"] = "test-secret-key-1234567890"
os.environ["ADMIN_PASSWORD"] = "test_admin_123"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/testdb"
os.environ["CORS_ORIGINS"] = '["http://localhost"]'
os.environ["DEBUG"] = "true"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "63790"
os.environ["S3_ENDPOINT"] = "localhost:9000"
os.environ["S3_ACCESS_KEY"] = ""
os.environ["S3_SECRET_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.utils.auth import create_access_token

# ===== 测试数据库 — StaticPool 保证 SQLite 连接共享 =====
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ===== helpers =====
def make_token(role="super_admin", user_id=1, department="admin"):
    return create_access_token(data={
        "sub": str(user_id),
        "user_id": user_id,
        "role": role,
        "department": department,
    })


# ===== fixtures =====
@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def admin_token():
    return make_token(role="super_admin", user_id=0)


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def create_user():
    def _create(employee_id="EMP001", name="测试用户", department="技术部", role="employee", status=1):
        from app.models.user import User
        db = TestSessionLocal()
        user = User(employee_id=employee_id, name=name, department=department,
                    role=role, status=status, face_encoding_path=None, face_image_path=None)
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
        db.close()
        # 返回简单对象
        return type('U', (), {'id': uid, 'employee_id': employee_id, 'name': name,
                              'department': department, 'role': role, 'status': status})()
    yield _create


@pytest.fixture
def test_user(create_user):
    return create_user()


@pytest.fixture
def create_device():
    def _create(device_code="DEV001", name="测试设备", location="1楼大厅", status=1):
        from app.models.device import Device
        db = TestSessionLocal()
        d = Device(device_code=device_code, name=name, location=location, status=status)
        db.add(d)
        db.commit()
        db.refresh(d)
        did = d.id
        db.close()
        return type('D', (), {'id': did, 'device_code': device_code, 'name': name,
                              'location': location, 'status': status})()
    yield _create


@pytest.fixture
def test_device(create_device):
    return create_device()


@pytest.fixture
def create_attendance():
    def _create(user_id=1, employee_id="EMP001", name="测试用户",
                device_id=None, action_type="CHECK_IN", confidence=0.95):
        from app.models.attendance import AttendanceLog
        db = TestSessionLocal()
        r = AttendanceLog(user_id=user_id, employee_id=employee_id, name=name,
                          action_type=action_type, confidence=confidence,
                          result="SUCCESS", device_id=device_id)
        db.add(r)
        db.commit()
        db.refresh(r)
        rid = r.id
        db.close()
        return type('R', (), {'id': rid, 'user_id': user_id, 'employee_id': employee_id,
                              'action_type': action_type})()
    yield _create


client = TestClient(app)


# ============================================================
# 认证
# ============================================================
class TestAuth:
    def test_login_success(self):
        r = client.post("/api/auth/login", json={"password": "test_admin_123"})
        assert r.status_code == 200
        assert "token" in r.json()["data"]

    def test_login_wrong_password(self):
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401

    def test_logout(self):
        assert client.post("/api/auth/logout").status_code == 200

    def test_check_unauthenticated(self):
        assert client.get("/api/auth/check").json()["authenticated"] is False

    def test_check_authenticated(self, admin_token):
        r = client.get("/api/auth/check", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.json()["authenticated"] is True


# ============================================================
# 用户管理
# ============================================================
class TestUsers:
    def test_register_user(self, admin_headers):
        r = client.post("/api/users", headers=admin_headers, data={
            "employee_id": "EMP002", "name": "新用户", "department": "市场部"})
        assert r.status_code == 200
        assert r.json()["employee_id"] == "EMP002"

    def test_register_duplicate(self, admin_headers, test_user):
        r = client.post("/api/users", headers=admin_headers, data={
            "employee_id": "EMP001", "name": "重复"})
        assert r.status_code == 400

    def test_list_users(self, admin_headers, test_user):
        r = client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_pagination(self, admin_headers, create_user):
        for i in range(5):
            create_user(employee_id=f"PG{i:03d}", name=f"用户{i}")
        r = client.get("/api/users", headers=admin_headers, params={"page_size": 3})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    def test_get_user(self, admin_headers, test_user):
        r = client.get(f"/api/users/{test_user.id}", headers=admin_headers)
        assert r.status_code == 200

    def test_get_user_not_found(self, admin_headers):
        assert client.get("/api/users/99999", headers=admin_headers).status_code == 404

    def test_update_user(self, admin_headers, test_user):
        r = client.put(f"/api/users/{test_user.id}", headers=admin_headers,
                       json={"name": "改名", "department": "新部门"})
        assert r.status_code == 200
        assert r.json()["name"] == "改名"

    def test_delete_user(self, admin_headers, test_user):
        assert client.delete(f"/api/users/{test_user.id}", headers=admin_headers).status_code == 200
        assert client.get(f"/api/users/{test_user.id}", headers=admin_headers).status_code == 404

    def test_update_role(self, admin_headers, test_user):
        r = client.put(f"/api/users/{test_user.id}/role", headers=admin_headers,
                       json={"role": "dept_admin"})
        assert r.status_code == 200
        assert r.json()["role"] == "dept_admin"

    def test_update_role_invalid(self, admin_headers, test_user):
        assert client.put(f"/api/users/{test_user.id}/role", headers=admin_headers,
                          json={"role": "xxx"}).status_code == 400

    def test_unauthorized(self):
        assert client.get("/api/users").status_code in (401, 403)


# ============================================================
# 设备管理
# ============================================================
class TestDevices:
    def test_create_device(self, admin_headers):
        r = client.post("/api/devices", headers=admin_headers, json={
            "device_code": "CAM_01", "name": "摄像头", "location": "A栋"})
        assert r.status_code == 200
        assert r.json()["device_code"] == "CAM_01"

    def test_create_duplicate(self, admin_headers, test_device):
        assert client.post("/api/devices", headers=admin_headers,
                           json={"device_code": "DEV001", "name": "重复"}).status_code == 400

    def test_list_devices(self, admin_headers, test_device):
        r = client.get("/api/devices", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_filter_status(self, admin_headers, create_device):
        create_device(device_code="ON_01", status=1)
        create_device(device_code="OFF_01", status=0)
        r = client.get("/api/devices", headers=admin_headers, params={"status": 1})
        assert all(d["status"] == 1 for d in r.json())

    def test_get_device(self, admin_headers, test_device):
        r = client.get(f"/api/devices/{test_device.id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["device_code"] == "DEV001"

    def test_get_device_not_found(self, admin_headers):
        assert client.get("/api/devices/99999", headers=admin_headers).status_code == 404

    def test_update_device(self, admin_headers, test_device):
        r = client.put(f"/api/devices/{test_device.id}", headers=admin_headers,
                       json={"name": "改名"})
        assert r.status_code == 200
        assert r.json()["name"] == "改名"

    def test_delete_device(self, admin_headers, test_device):
        assert client.delete(f"/api/devices/{test_device.id}",
                            headers=admin_headers).status_code == 200

    def test_heartbeat_success(self, test_device):
        r = client.post("/api/devices/heartbeat", json={"device_code": "DEV001"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_heartbeat_not_found(self):
        assert client.post("/api/devices/heartbeat",
                           json={"device_code": "NOPE"}).status_code == 404

    def test_heartbeat_disabled(self, create_device):
        create_device(device_code="DIS_01", status=2)
        assert client.post("/api/devices/heartbeat",
                           json={"device_code": "DIS_01"}).status_code == 403

    def test_heartbeat_no_auth(self, test_device):
        """心跳免认证"""
        assert client.post("/api/devices/heartbeat",
                           json={"device_code": "DEV001"}).status_code == 200

    def test_is_online(self, admin_headers, test_device):
        # 无心跳时离线
        r = client.get("/api/devices", headers=admin_headers)
        dev = next(d for d in r.json() if d["device_code"] == "DEV001")
        assert dev["is_online"] is False
        # 有心跳后在线
        client.post("/api/devices/heartbeat", json={"device_code": "DEV001"})
        r = client.get("/api/devices", headers=admin_headers)
        dev = next(d for d in r.json() if d["device_code"] == "DEV001")
        assert dev["is_online"] is True

    def test_unauthorized(self):
        assert client.get("/api/devices").status_code == 401


# ============================================================
# 考勤管理
# ============================================================
class TestAttendance:
    def test_list_attendance(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id)
        r = client.get("/api/attendance", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_pagination(self, admin_headers, test_user, create_attendance):
        for _ in range(3):
            create_attendance(user_id=test_user.id)
        r = client.get("/api/attendance", headers=admin_headers, params={"page_size": 2})
        assert len(r.json()["items"]) == 2

    def test_filter_employee_id(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id, employee_id="EMP001")
        r = client.get("/api/attendance", headers=admin_headers, params={"employee_id": "EMP001"})
        assert all(x["employee_id"] == "EMP001" for x in r.json()["items"])

    def test_filter_action_type(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id, action_type="CHECK_IN")
        r = client.get("/api/attendance", headers=admin_headers, params={"action_type": "CHECK_IN"})
        assert all(x["action_type"] == "CHECK_IN" for x in r.json()["items"])

    def test_filter_device_id(self, admin_headers, test_user, test_device, create_attendance):
        create_attendance(user_id=test_user.id, device_id=test_device.id)
        r = client.get("/api/attendance", headers=admin_headers, params={"device_id": test_device.id})
        assert all(x.get("device_id") == test_device.id for x in r.json()["items"])

    def test_with_device_name(self, admin_headers, test_user, test_device, create_attendance):
        create_attendance(user_id=test_user.id, device_id=test_device.id)
        r = client.get("/api/attendance", headers=admin_headers)
        rec = next((x for x in r.json()["items"] if x.get("device_id")), None)
        if rec:
            assert "device_name" in rec

    def test_detail(self, admin_headers, test_user, create_attendance):
        rec = create_attendance(user_id=test_user.id)
        assert client.get(f"/api/attendance/{rec.id}", headers=admin_headers).status_code == 200

    def test_detail_not_found(self, admin_headers):
        assert client.get("/api/attendance/99999", headers=admin_headers).status_code == 404

    def test_stats(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id, action_type="CHECK_IN")
        r = client.get("/api/attendance/stats", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total_records"] >= 1

    def test_export_no_records(self, admin_headers):
        assert client.get("/api/attendance/export", headers=admin_headers, params={
            "start_date": "2099-01-01", "end_date": "2099-01-02"}).status_code == 404

    def test_unauthorized(self):
        assert client.get("/api/attendance").status_code in (401, 403)


# ============================================================
# 统计
# ============================================================
class TestStatistics:
    def test_daily_empty(self, admin_headers):
        r = client.get("/api/statistics/daily", headers=admin_headers)
        assert r.status_code == 200
        assert "total_employees" in r.json()

    def test_daily_with_data(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id)
        r = client.get("/api/statistics/daily", headers=admin_headers)
        assert r.json()["present_count"] >= 1

    def test_user_stats(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id)
        r = client.get(f"/api/statistics/user/{test_user.id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total_records"] >= 1

    def test_trend(self, admin_headers, test_user, create_attendance):
        create_attendance(user_id=test_user.id)
        r = client.get("/api/statistics/trend", headers=admin_headers, params={"days": 7})
        assert r.status_code == 200
        assert "trend" in r.json()

    def test_unauthorized(self):
        assert client.get("/api/statistics/daily").status_code == 401


# ============================================================
# 自助服务
# ============================================================
class TestSelfService:
    def test_profile_not_found(self, admin_token):
        r = client.get("/api/self/profile", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404

    def test_profile_success(self, test_user):
        token = make_token(role="employee", user_id=test_user.id, department="技术部")
        r = client.get("/api/self/profile", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["employee_id"] == "EMP001"

    def test_my_attendance(self, test_user, create_attendance):
        token = make_token(role="employee", user_id=test_user.id)
        create_attendance(user_id=test_user.id)
        r = client.get("/api/self/attendance", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["total_records"] >= 1

    def test_today_not_started(self, test_user):
        token = make_token(role="employee", user_id=test_user.id)
        r = client.get("/api/self/attendance/today", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["status"] == "not_started"

    def test_today_checked_in(self, test_user, create_attendance):
        token = make_token(role="employee", user_id=test_user.id)
        create_attendance(user_id=test_user.id, action_type="CHECK_IN")
        r = client.get("/api/self/attendance/today", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["status"] == "checked_in"

    def test_unregister_face(self, test_user):
        token = make_token(role="employee", user_id=test_user.id)
        assert client.delete("/api/self/face",
                            headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_unauthorized(self):
        assert client.get("/api/self/profile").status_code == 401


# ============================================================
# 健康检查
# ============================================================
class TestHealth:
    def test_health(self):
        r = client.get("/health")
        # 健康检查直接用 app.database.SessionLocal，在测试中连的是不可达的 PG
        # 所以 database check 会 degraded，但不应 500
        assert r.status_code == 200
        assert r.json()["status"] in ("healthy", "degraded", "unhealthy")

    def test_live(self):
        assert client.get("/health/live").json()["alive"] is True

    def test_root(self):
        assert client.get("/").status_code == 200


# ============================================================
# 人脸 API (Mock)
# ============================================================
class TestFaceAPI:
    def test_detect_no_face(self, admin_headers):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="JPEG")
        buf.seek(0)
        r = client.post("/api/face/detect", headers=admin_headers, files={"image": ("t.jpg", buf, "image/jpeg")})
        assert r.status_code == 200
        assert r.json()["faces_detected"] == 0

    def test_recognize_no_face(self, admin_headers):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="JPEG")
        buf.seek(0)
        r = client.post("/api/face/recognize", headers=admin_headers, files={"image": ("t.jpg", buf, "image/jpeg")})
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_register_not_found(self, admin_headers):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="JPEG")
        buf.seek(0)
        assert client.post("/api/face/register/99999", headers=admin_headers,
                           files={"image": ("t.jpg", buf, "image/jpeg")}).status_code == 404


# ============================================================
# 权限
# ============================================================
class TestPermissions:
    def test_employee_no_users(self, test_user):
        token = make_token(role="employee", user_id=test_user.id)
        assert client.get("/api/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403

    def test_dept_admin_devices(self, test_user):
        token = make_token(role="dept_admin", user_id=test_user.id, department="技术部")
        assert client.get("/api/devices", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_employee_no_create_device(self, test_user):
        token = make_token(role="employee", user_id=test_user.id)
        assert client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
                           json={"device_code": "X", "name": "X"}).status_code == 403

    def test_only_super_admin_role(self, test_user):
        token = make_token(role="dept_admin", user_id=test_user.id)
        assert client.put(f"/api/users/{test_user.id}/role", headers={"Authorization": f"Bearer {token}"},
                          json={"role": "super_admin"}).status_code == 403


# ============================================================
# 边界条件
# ============================================================
class TestEdgeCases:
    def test_empty_db(self, admin_headers):
        assert client.get("/api/users", headers=admin_headers).json()["total"] == 0

    def test_sql_injection_safe(self, admin_headers):
        r = client.get("/api/users", headers=admin_headers, params={"department": "'; DROP TABLE users; --"})
        assert r.status_code == 200

    def test_invalid_page(self, admin_headers):
        assert client.get("/api/users", headers=admin_headers, params={"page": -1}).status_code == 422

    def test_invalid_date(self, admin_headers):
        r = client.get("/api/attendance", headers=admin_headers, params={"start_date": "bad"})
        assert r.status_code in (400, 422)
