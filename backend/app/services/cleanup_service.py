"""数据生命周期管理服务
定期清理过期数据和已离职员工的人脸数据
"""
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings
from app.models import User, AttendanceLog
from app.models.audit import AuditLog
from app.services.storage_service import storage_service
import structlog

log = structlog.get_logger(__name__)

class CleanupService:
    """数据生命周期管理"""
    
    def cleanup_expired_snapshots(self, db: Session) -> int:
        """清理过期的抓拍图文件
        Returns: 删除的文件数量
        """
        if settings.SNAPSHOT_RETENTION_DAYS <= 0:
            return 0
        
        cutoff = datetime.now() - timedelta(days=settings.SNAPSHOT_RETENTION_DAYS)
        snapshot_dir = settings.IMAGES_DIR / "snapshots"
        if not snapshot_dir.exists():
            return 0
        
        deleted = 0
        for f in snapshot_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff.timestamp():
                try:
                    f.unlink()
                    deleted += 1
                except Exception as e:
                    log.warning("snapshot_delete_failed", file=str(f), error=str(e))
        
        log.info("snapshots_cleaned", deleted=deleted, retention_days=settings.SNAPSHOT_RETENTION_DAYS)
        return deleted
    
    def cleanup_old_attendance_logs(self, db: Session) -> int:
        """清理过期的考勤记录
        Returns: 删除的记录数量
        """
        if settings.DATA_RETENTION_DAYS <= 0:
            return 0
        
        cutoff = datetime.now() - timedelta(days=settings.DATA_RETENTION_DAYS)
        count = db.query(AttendanceLog).filter(AttendanceLog.created_at < cutoff).delete()
        db.commit()
        log.info("attendance_logs_cleaned", deleted=count, retention_days=settings.DATA_RETENTION_DAYS)
        return count
    
    def cleanup_old_audit_logs(self, db: Session) -> int:
        """清理过期的审计日志
        Returns: 删除的记录数量
        """
        if settings.AUDIT_RETENTION_DAYS <= 0:
            return 0
        
        cutoff = datetime.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        count = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
        db.commit()
        log.info("audit_logs_cleaned", deleted=count, retention_days=settings.AUDIT_RETENTION_DAYS)
        return count
    
    def cleanup_resigned_user_face_data(self, db: Session) -> int:
        """清理已离职员工的人脸数据（保留用户记录）
        Returns: 清理的用户数量
        """
        if not settings.FACE_DATA_DELETE_ON_RESIGN:
            return 0
        
        resigned_users = db.query(User).filter(User.status == 0, User.face_encoding_path.isnot(None)).all()
        cleaned = 0
        for user in resigned_users:
            # 删除存储中的特征向量
            storage_service.delete(settings.S3_ENCODING_BUCKET, f"{user.employee_id}.npy")
            
            # 删除本地文件
            encoding_path = Path(user.face_encoding_path) if user.face_encoding_path else None
            if encoding_path and encoding_path.exists():
                encoding_path.unlink()
            
            # 清除数据库中的路径引用
            user.face_encoding_path = None
            user.face_image_path = None
            cleaned += 1
            log.info("face_data_cleaned", employee_id=user.employee_id, name=user.name)
        
        if cleaned > 0:
            db.commit()
        log.info("resigned_users_face_data_cleaned", count=cleaned)
        return cleaned
    
    def run_all(self, db: Session) -> dict:
        """执行所有清理任务"""
        results = {
            "snapshots_deleted": self.cleanup_expired_snapshots(db),
            "attendance_logs_deleted": self.cleanup_old_attendance_logs(db),
            "audit_logs_deleted": self.cleanup_old_audit_logs(db),
            "face_data_cleaned": self.cleanup_resigned_user_face_data(db),
        }
        log.info("cleanup_completed", **results)
        return results

cleanup_service = CleanupService()
