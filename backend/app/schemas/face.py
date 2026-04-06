from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FaceBox(BaseModel):
    top: int
    right: int
    bottom: int
    left: int


class FaceDetectResponse(BaseModel):
    faces_detected: int
    faces: List[dict]


class UserInfo(BaseModel):
    id: int
    employee_id: str
    name: str
    department: Optional[str] = None


class FaceVerifyResponse(BaseModel):
    success: bool
    user: Optional[UserInfo] = None
    confidence: float = Field(..., ge=0, le=1)
    liveness_passed: Optional[bool] = None
    reason: Optional[str] = None


class FaceRegisterResponse(BaseModel):
    success: bool
    user_id: int
    face_detected: bool
    face_quality: Optional[str] = None
    message: str
