from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class ResultType(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AttendanceBase(BaseModel):
    user_id: Optional[int] = None
    employee_id: Optional[str] = None
    name: Optional[str] = None
    action_type: ActionType
    confidence: Optional[float] = None
    result: ResultType


class AttendanceCreate(AttendanceBase):
    snapshot_path: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: int
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    snapshot_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceListResponse(BaseModel):
    items: List[AttendanceResponse]
    total: int
    page: int
    page_size: int


class CheckInResponse(BaseModel):
    success: bool
    action_type: str
    user: Optional[dict] = None
    confidence: Optional[float] = None
    message: str
    record_id: Optional[int] = None


class AttendanceStats(BaseModel):
    total_records: int
    success_count: int
    failed_count: int
    unique_users: int
    avg_confidence: float
