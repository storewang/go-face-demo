"""
考勤统计 API
提供每日考勤统计、个人考勤统计和考勤趋势分析功能
Phase 4 功能扩展（第二批）
"""
import structlog
from datetime import datetime, timedelta, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.permissions import require_role, RoleType
from app.models.attendance import AttendanceLog
from app.models.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/statistics", tags=["考勤统计"])


@router.get("/daily", summary="每日考勤统计")
async def daily_stats(
    date_str: Optional[str] = Query(None, description="日期 YYYY-MM-DD，默认今天"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取指定日期的考勤汇总"""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)

    # 统计非超级管理员用户总数
    total_employees = db.query(func.count(User.id)).filter(User.role != RoleType.SUPER_ADMIN).scalar() or 0

    # 按操作类型分组统计
    stats = db.query(
        AttendanceLog.action_type,
        func.count(AttendanceLog.id),
    ).filter(
        AttendanceLog.created_at >= start,
        AttendanceLog.created_at < end,
    ).group_by(AttendanceLog.action_type).all()

    action_map = {str(a): c for a, c in stats}

    # 查询当天有打卡记录的唯一用户数
    present_count = db.query(func.count(func.distinct(AttendanceLog.user_id))).filter(
        AttendanceLog.created_at >= start,
        AttendanceLog.created_at < end,
    ).scalar() or 0

    return {
        "date": target_date.isoformat(),
        "total_employees": total_employees,
        "present_count": present_count,
        "absent_count": total_employees - present_count,
        "action_breakdown": action_map,
        "attendance_rate": round(present_count / total_employees * 100, 1) if total_employees > 0 else 0,
    }


@router.get("/user/{user_id}", summary="个人考勤统计")
async def user_stats(
    user_id: int,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取指定用户的考勤详情"""
    # 默认查询本月
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

    # 获取指定时间段的考勤记录
    records = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user_id,
        AttendanceLog.created_at >= start,
        AttendanceLog.created_at <= end,
    ).order_by(AttendanceLog.created_at).all()

    # 统计每日首次/末次打卡
    from collections import defaultdict
    daily = defaultdict(lambda: {"first": None, "last": None})
    for r in records:
        day = r.created_at.strftime("%Y-%m-%d")
        t = r.created_at.strftime("%H:%M:%S")
        if daily[day]["first"] is None:
            daily[day]["first"] = t
        daily[day]["last"] = t

    return {
        "user_id": user_id,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_records": len(records),
        "work_days": len(daily),
        "daily_summary": dict(daily),
    }


@router.get("/trend", summary="考勤趋势")
async def attendance_trend(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取最近 N 天的考勤趋势"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # 每天打卡人数
    daily_counts = db.query(
        func.date(AttendanceLog.created_at),
        func.count(func.distinct(AttendanceLog.user_id)),
    ).filter(
        AttendanceLog.created_at >= datetime.combine(start_date, datetime.min.time()),
        AttendanceLog.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
    ).group_by(func.date(AttendanceLog.created_at)).all()

    # 统计总员工数（排除 super_admin）
    total = db.query(func.count(User.id)).filter(User.role != RoleType.SUPER_ADMIN).scalar() or 0

    trend = []
    for d, count in daily_counts:
        trend.append({
            "date": str(d),
            "present": count,
            "absent": total - count,
            "rate": round(count / total * 100, 1) if total > 0 else 0,
        })

    return {"days": days, "total_employees": total, "trend": trend}