from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.permissions import require_role, RoleType
from app.models import Device
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse


# 心跳请求 Schema
class HeartbeatRequest(BaseModel):
    device_code: str
    password: Optional[str] = None  # 预留字段，暂不使用


# 带在线状态的设备响应
class DeviceWithOnlineResponse(DeviceResponse):
    is_online: bool = False
# 设备列表响应
class DeviceListResponse(BaseModel):
    items: List[DeviceWithOnlineResponse]
    total: int


router = APIRouter(prefix="/api/devices", tags=["设备管理"])
heartbeat_router = APIRouter(prefix="/api/devices", tags=["设备管理"])


@router.post("", response_model=DeviceResponse, summary="添加设备")
async def create_device(
    data: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(RoleType.SUPER_ADMIN, RoleType.DEPT_ADMIN))
):
    existing = db.query(Device).filter(Device.device_code == data.device_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备编号已存在")
    
    device = Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=DeviceListResponse, summary="设备列表")
async def list_devices(
    status: Optional[int] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = db.query(Device)
    if status is not None:
        query = query.filter(Device.status == status)
    devices = query.order_by(Device.id).all()
    
    # 动态计算在线状态
    now = datetime.now()
    result = []
    for device in devices:
        device_dict = {
            "id": device.id,
            "device_code": device.device_code,
            "name": device.name,
            "location": device.location,
            "status": device.status,
            "last_heartbeat": device.last_heartbeat,
            "description": device.description,
            "created_at": device.created_at,
            "updated_at": device.updated_at,
            "is_online": False
        }
        # 如果 last_heartbeat 在 60 秒内，视为在线
        if device.last_heartbeat:
            seconds_diff = (now - device.last_heartbeat).total_seconds()
            device_dict["is_online"] = seconds_diff <= 60
        result.append(DeviceWithOnlineResponse(**device_dict))
    
    return {"items": result, "total": len(result)}


@router.get("/{device_id}", response_model=DeviceResponse, summary="设备详情")
async def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.put("/{device_id}", response_model=DeviceResponse, summary="更新设备")
async def update_device(
    device_id: int,
    data: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(RoleType.SUPER_ADMIN, RoleType.DEPT_ADMIN))
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)
    
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", summary="删除设备")
async def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(RoleType.SUPER_ADMIN))
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    db.delete(device)
    db.commit()
    return {"message": "设备已删除"}


@heartbeat_router.post("/heartbeat", summary="设备心跳")
async def device_heartbeat(
    data: HeartbeatRequest,
    db: Session = Depends(get_db)
):
    """
    设备心跳接口，设备定期调用此接口报告在线状态
    - 根据 device_code 查找设备
    - 如果设备不存在，返回 404
    - 如果设备 status=2（禁用/维护中），返回 403
    - 更新 last_heartbeat 为当前时间，status 设为 1（在线）
    """
    device = db.query(Device).filter(Device.device_code == data.device_code).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.status == 2:
        raise HTTPException(status_code=403, detail="设备已禁用")
    
    # 更新心跳时间和状态
    device.last_heartbeat = datetime.now()
    device.status = 1  # 设置为在线
    db.commit()
    db.refresh(device)
    
    return {
        "success": True,
        "device": {
            "id": device.id,
            "device_code": device.device_code,
            "name": device.name,
            "location": device.location,
            "status": device.status
        }
    }
