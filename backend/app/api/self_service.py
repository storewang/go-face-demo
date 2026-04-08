"""
用户自助服务 API
提供个人信息、考勤查询、人脸注销等功能
Phase 4 功能扩展（第二批）
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.attendance import AttendanceLog
from app.models.user import User
from app.cache import redis_client

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/self", tags=["自助服务"])


@router.get("/profile", summary="个人信息")
async def get_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户的完整信息"""
    user_id = current_user.get("user_id") or current_user.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "name": user.name,
        "department": user.department,
        "role": user.role,
        "face_registered": bool(user.face_image_path),
    }


@router.get("/attendance", summary="我的考勤记录")
async def my_attendance(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取最近 N 天的个人考勤记录"""
    user_id = current_user.get("user_id") or current_user.get("sub")
    start = datetime.now() - timedelta(days=days)
    records = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user_id,
        AttendanceLog.created_at >= start,
    ).order_by(AttendanceLog.created_at.desc()).all()

    return {
        "user_id": user_id,
        "period_days": days,
        "total_records": len(records),
        "records": [
            {
                "id": r.id,
                "action_type": r.action_type,
                "result_type": r.result,
                "confidence": r.confidence,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


@router.get("/attendance/today", summary="今日考勤状态")
async def today_attendance(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取今日签到/签退状态"""
    user_id = current_user.get("user_id") or current_user.get("sub")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user_id,
        AttendanceLog.created_at >= today,
    ).order_by(AttendanceLog.created_at).all()

    check_in = None
    check_out = None
    for r in records:
        if r.action_type == "CHECK_IN" and not check_in:
            check_in = r.created_at.strftime("%H:%M:%S") if r.created_at else None
        elif r.action_type == "CHECK_OUT":
            check_out = r.created_at.strftime("%H:%M:%S") if r.created_at else None

    return {
        "date": today.strftime("%Y-%m-%d"),
        "check_in": check_in,
        "check_out": check_out,
        "status": "completed" if check_in and check_out else "checked_in" if check_in else "not_started",
    }


@router.delete("/face", summary="注销人脸")
async def unregister_face(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户注销自己的人脸数据"""
    user_id = current_user.get("user_id") or current_user.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.face_encoding_path = None
    user.face_image_path = None
    db.commit()
    redis_client.delete(f"user:{user_id}")
    log.info("face_unregistered", user_id=user_id)
    return {"message": "人脸数据已注销"}