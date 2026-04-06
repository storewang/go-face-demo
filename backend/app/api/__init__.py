from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

from app.api.users import router as users_router
from app.api.face import router as face_router
from app.api.attendance import router as attendance_router
from app.api.auth import router as auth_router
from app.utils.auth import validate_token


def verify_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录管理员账号")

    token = authorization.replace("Bearer ", "")
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(face_router)
api_router.include_router(users_router, dependencies=[Depends(verify_admin)])
api_router.include_router(attendance_router, dependencies=[Depends(verify_admin)])
