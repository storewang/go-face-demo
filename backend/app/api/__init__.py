from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

from app.api.users import router as users_router
from app.api.face import router as face_router
from app.api.attendance import router as attendance_router
from app.api.auth import router as auth_router
from app.utils.auth import get_current_user


def verify_admin():
    """FastAPI依赖项：验证管理员JWT token"""
    async def dependency(authorization: Optional[str] = Header(None)):
        payload = await get_current_user(authorization)
        return payload
    return dependency


api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(face_router)
api_router.include_router(users_router, dependencies=[Depends(verify_admin())])
api_router.include_router(attendance_router, dependencies=[Depends(verify_admin())])
