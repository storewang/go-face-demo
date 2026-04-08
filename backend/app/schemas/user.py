from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=50, description="工号")
    name: str = Field(..., min_length=1, max_length=100, description="姓名")
    department: Optional[str] = Field(None, max_length=100, description="部门")


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    status: Optional[int] = Field(None, ge=0, le=1)
    role: Optional[str] = Field(None, max_length=20)


class UserResponse(UserBase):
    id: int
    status: int
    role: str = "employee"
    face_encoding_path: Optional[str] = None
    face_image_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserRegisterResponse(UserResponse):
    face_detected: bool = False
    face_quality: Optional[str] = None
