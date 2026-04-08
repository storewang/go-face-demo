from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DeviceCreate(BaseModel):
    device_code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    status: Optional[int] = Field(None, ge=0, le=2)
    description: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    device_code: str
    name: str
    location: Optional[str]
    status: int
    last_heartbeat: Optional[datetime]
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
