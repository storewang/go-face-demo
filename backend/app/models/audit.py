"""审计日志模型 — 防篡改门禁事件记录"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True)  # door_open/door_deny/pin_open/face_register/face_auth_fail
    user_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(String(50), nullable=True)
    user_name = Column(String(100), nullable=True)
    device_id = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    snapshot_path = Column(String(255), nullable=True)
    raw_data = Column(Text, nullable=True)  # 原始事件 JSON
    hmac_signature = Column(String(128), nullable=False)  # HMAC-SHA256 hex
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, event={self.event_type}, user_id={self.user_id})>"
