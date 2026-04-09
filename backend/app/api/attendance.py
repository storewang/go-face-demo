from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, AttendanceLog, ActionType, ResultType, Device
from app.schemas.attendance import (
    AttendanceResponse,
    AttendanceListResponse,
    CheckInResponse,
    AttendanceStats,
)
from app.services.face_service import face_service
from app.services.export_service import export_service
from app.utils.face_utils import FaceUtils
from app.config import settings

router = APIRouter(prefix="/api/attendance", tags=["考勤管理"])


@router.get("", response_model=AttendanceListResponse, summary="获取考勤记录")
def list_attendance(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    employee_id: Optional[str] = Query(None, description="工号筛选"),
    action_type: Optional[str] = Query(None, description="类型: CHECK_IN/CHECK_OUT"),
    result: Optional[str] = Query(None, description="结果: SUCCESS/FAILED"),
    device_id: Optional[int] = Query(None, description="设备ID筛选"),
    db: Session = Depends(get_db),
):
    # 使用 left join 关联 Device 表获取设备名称
    query = db.query(AttendanceLog).outerjoin(
        Device, AttendanceLog.device_id == Device.id
    )

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误，请使用 YYYY-MM-DD")
        query = query.filter(AttendanceLog.created_at >= start)

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误，请使用 YYYY-MM-DD")
        query = query.filter(AttendanceLog.created_at < end)

    if employee_id:
        query = query.filter(AttendanceLog.employee_id == employee_id)

    if action_type:
        query = query.filter(AttendanceLog.action_type == action_type)

    if result:
        query = query.filter(AttendanceLog.result == result)

    if device_id:
        query = query.filter(AttendanceLog.device_id == device_id)

    query = query.order_by(AttendanceLog.created_at.desc())

    total = query.count()
    offset = (page - 1) * page_size
    records = query.offset(offset).limit(page_size).all()

    # 构建 AttendanceResponse 列表，添加 device_name
    items = []
    for record in records:
        # 查询设备名称
        device_name = None
        if record.device_id:
            device = db.query(Device).filter(Device.id == record.device_id).first()
            if device:
                device_name = device.name
        
        record_dict = {
            "id": record.id,
            "user_id": record.user_id,
            "employee_id": record.employee_id,
            "name": record.name,
            "action_type": record.action_type,
            "confidence": record.confidence,
            "result": record.result,
            "device_id": record.device_id,
            "device_name": device_name,
            "snapshot_path": record.snapshot_path,
            "created_at": record.created_at,
        }
        items.append(AttendanceResponse(**record_dict))

    return AttendanceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=AttendanceStats, summary="考勤统计")
def get_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceLog)

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(AttendanceLog.created_at >= start)

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(AttendanceLog.created_at < end)

    records = query.all()

    if not records:
        return AttendanceStats(
            total_records=0,
            success_count=0,
            failed_count=0,
            unique_users=0,
            avg_confidence=0,
        )

    total = len(records)
    success = sum(1 for r in records if r.result == ResultType.SUCCESS)
    failed = total - success
    unique_users = len(set(r.employee_id for r in records if r.employee_id))

    confidences = [r.confidence for r in records if r.confidence is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    return AttendanceStats(
        total_records=total,
        success_count=success,
        failed_count=failed,
        unique_users=unique_users,
        avg_confidence=round(avg_conf, 3),
    )


@router.get("/export", summary="导出考勤 Excel")
def export_attendance(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    employee_id: Optional[str] = Query(None, description="工号筛选"),
    format: str = Query("detail", description="格式: detail/summary"),
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceLog)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    query = query.filter(
        AttendanceLog.created_at >= start, AttendanceLog.created_at < end
    )

    if employee_id:
        query = query.filter(AttendanceLog.employee_id == employee_id)

    records = query.order_by(AttendanceLog.created_at).all()

    if not records:
        raise HTTPException(status_code=404, detail="无符合条件的记录")

    if format == "summary":
        excel_file = export_service.export_attendance_summary(
            records, start_date, end_date
        )
        filename = f"attendance_summary_{start_date}_{end_date}.xlsx"
    else:
        excel_file = export_service.export_attendance_to_excel(
            records, start_date, end_date
        )
        filename = f"attendance_{start_date}_{end_date}.xlsx"

    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{record_id}", response_model=AttendanceResponse, summary="获取记录详情")
def get_attendance(record_id: int, db: Session = Depends(get_db)):
    record = db.query(AttendanceLog).filter(AttendanceLog.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return AttendanceResponse.model_validate(record)


def _create_check_record(
    action_type_value: str, image: UploadFile, employee_id: Optional[str], db: Session
) -> CheckInResponse:
    import cv2

    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)

    result = face_service.verify_user(img)

    user_id = None
    name = None
    final_employee_id = employee_id
    confidence = result.get("confidence", 0)

    if result["success"]:
        user_id = result["user"]["id"]
        name = result["user"]["name"]
        final_employee_id = result["user"]["employee_id"]
    elif employee_id:
        user = db.query(User).filter(User.employee_id == employee_id).first()
        if user:
            user_id = user.id
            name = user.name

    snapshot_path = None
    if result["success"] or employee_id:
        snapshot_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{final_employee_id or 'unknown'}.jpg"
        snapshot_path = str(settings.IMAGES_DIR / "snapshots" / snapshot_filename)

        (settings.IMAGES_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
        cv2.imwrite(snapshot_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    action_type = (
        ActionType.CHECK_IN if action_type_value == "CHECK_IN" else ActionType.CHECK_OUT
    )
    result_type = ResultType.SUCCESS if result["success"] else ResultType.FAILED

    record = AttendanceLog(
        user_id=user_id,
        employee_id=final_employee_id,
        name=name,
        action_type=action_type,
        confidence=confidence,
        snapshot_path=snapshot_path,
        result=result_type,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    action_label = "上班" if action_type == ActionType.CHECK_IN else "下班"

    if result["success"]:
        return CheckInResponse(
            success=True,
            action_type=action_type_value,
            user=result["user"],
            confidence=confidence,
            message=f"{name} {action_label}打卡成功",
            record_id=record.id,
        )
    else:
        return CheckInResponse(
            success=False,
            action_type=action_type_value,
            user=None,
            confidence=confidence,
            message=f"打卡失败: {result['reason']}",
            record_id=record.id,
        )


@router.post("/check-in", response_model=CheckInResponse, summary="上班打卡")
def check_in(
    image: UploadFile = File(..., description="人脸照片"),
    employee_id: Optional[str] = Form(None, description="工号（可选，手动指定）"),
    db: Session = Depends(get_db),
):
    return _create_check_record("CHECK_IN", image, employee_id, db)


@router.post("/check-out", response_model=CheckInResponse, summary="下班打卡")
def check_out(
    image: UploadFile = File(..., description="人脸照片"),
    employee_id: Optional[str] = Form(None, description="工号（可选）"),
    db: Session = Depends(get_db),
):
    return _create_check_record("CHECK_OUT", image, employee_id, db)
