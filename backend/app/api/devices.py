from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.permissions import require_role, RoleType
from app.models import Device
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse

router = APIRouter(prefix="/api/devices", tags=["设备管理"])


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


@router.get("", response_model=List[DeviceResponse], summary="设备列表")
async def list_devices(
    status: Optional[int] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = db.query(Device)
    if status is not None:
        query = query.filter(Device.status == status)
    return query.order_by(Device.id).all()


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
