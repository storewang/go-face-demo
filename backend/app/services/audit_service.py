"""审计日志写入服务"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.utils.audit import compute_hmac
import structlog

log = structlog.get_logger(__name__)

class AuditService:
    """审计日志服务"""
    
    def record_event(
        self,
        db: Session,
        event_type: str,
        user_id: Optional[int] = None,
        employee_id: Optional[str] = None,
        user_name: Optional[str] = None,
        device_id: Optional[int] = None,
        confidence: Optional[float] = None,
        snapshot_path: Optional[str] = None,
        extra_data: Optional[dict] = None,
    ) -> AuditLog:
        """记录审计事件"""
        raw_data = json.dumps(extra_data or {}, ensure_ascii=False)
        timestamp = datetime.now().isoformat()
        
        record = AuditLog(
            event_type=event_type,
            user_id=user_id,
            employee_id=employee_id,
            user_name=user_name,
            device_id=device_id,
            confidence=confidence,
            snapshot_path=snapshot_path,
            raw_data=raw_data,
            hmac_signature=compute_hmac(event_type, user_id, timestamp, raw_data),
        )
        db.add(record)
        db.flush()
        
        # 如果数据库生成了 created_at，用其重新计算 HMAC 以保证可验证
        if record.created_at:
            db_ts = record.created_at.isoformat()
            if db_ts != timestamp:
                record.hmac_signature = compute_hmac(event_type, user_id, db_ts, raw_data)
        return record

audit_service = AuditService()
