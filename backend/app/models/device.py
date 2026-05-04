from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    status = Column(Integer, default=1)
    secret_hash = Column(String(255), nullable=True, comment="设备密钥 bcrypt 哈希")
    last_heartbeat = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Device(id={self.id}, device_code='{self.device_code}', name='{self.name}')>"
