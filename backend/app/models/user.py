from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    face_encoding_path = Column(String(255), nullable=True)
    face_image_path = Column(String(255), nullable=True)
    status = Column(Integer, default=1)  # 1=active, 0=inactive
    role = Column(String(20), default="employee", nullable=False)  # super_admin/dept_admin/employee
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    attendance_logs = relationship("AttendanceLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, employee_id='{self.employee_id}', name='{self.name}')>"
