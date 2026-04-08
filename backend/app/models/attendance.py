from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ActionType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class ResultType(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    device_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(String(50), nullable=True, index=True)
    name = Column(String(100), nullable=True)
    action_type = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=True)
    snapshot_path = Column(String(255), nullable=True)
    result = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="attendance_logs")

    def __repr__(self):
        return f"<AttendanceLog(id={self.id}, employee_id='{self.employee_id}', action='{self.action_type}')>"
