"""审计日志写入服务"""
import json
from datetime import datetime
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
        user_id: int | None = None,
        employee_id: str | None = None,
        user_name: str | None = None,
        device_id: int | None = None,
        confidence: float | None = None,
        snapshot_path: str | None = None,
        extra_data: dict | None = None,
    ) -> AuditLog:
        """记录审计事件"""
        raw_data = json.dumps(extra_data or {}, ensure_ascii=False)
        timestamp = datetime.now().isoformat()
        hmac_sig = compute_hmac(event_type, user_id, timestamp, raw_data)
        
        record = AuditLog(
            event_type=event_type,
            user_id=user_id,
            employee_id=employee_id,
            user_name=user_name,
            device_id=device_id,
            confidence=confidence,
            snapshot_path=snapshot_path,
            raw_data=raw_data,
            hmac_signature=hmac_sig,
        )
        db.add(record)
        db.flush()  # Flush to get ID but don't commit (caller controls transaction)
        return record

audit_service = AuditService()
