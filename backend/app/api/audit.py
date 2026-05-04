"""审计日志查询 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from app.database import get_db
from app.utils.auth import get_current_user
from app.models.audit import AuditLog
from app.utils.audit import verify_hmac
from pydantic import BaseModel

router = APIRouter(prefix="/api/audit", tags=["审计日志"])

class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int]
    employee_id: Optional[str]
    user_name: Optional[str]
    device_id: Optional[int]
    confidence: Optional[float]
    snapshot_path: Optional[str]
    raw_data: Optional[str]
    hmac_signature: str
    signature_valid: bool
    created_at: Optional[datetime]

    class Config:
        orm_mode = True

class AuditListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int

    class Config:
        orm_mode = True

@router.get("/logs", response_model=AuditListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询审计日志（需认证）"""
    query = db.query(AuditLog)
    
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    # 日期过滤
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            start_dt = None
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            end_dt = None
    if start_dt:
        query = query.filter(AuditLog.created_at >= start_dt)
    if end_dt:
        query = query.filter(AuditLog.created_at <= end_dt)
    
    total = query.count()
    items = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # Verify HMAC for each record
    result_items = []
    for item in items:
        sig_valid = verify_hmac(
            item.hmac_signature,
            item.event_type,
            item.user_id,
            item.created_at.isoformat() if item.created_at else "",
            item.raw_data or "",
        )
        result_items.append(AuditLogResponse(
            id=item.id,
            event_type=item.event_type,
            user_id=item.user_id,
            employee_id=item.employee_id,
            user_name=item.user_name,
            device_id=item.device_id,
            confidence=item.confidence,
            snapshot_path=item.snapshot_path,
            raw_data=item.raw_data,
            hmac_signature=item.hmac_signature,
            signature_valid=sig_valid,
            created_at=item.created_at,
        ))
    
    return AuditListResponse(items=result_items, total=total, page=page, page_size=page_size)
