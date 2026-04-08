from fastapi import HTTPException, Depends
from typing import Callable
from app.utils.auth import get_current_user


class RoleType:
    SUPER_ADMIN = "super_admin"
    DEPT_ADMIN = "dept_admin"
    EMPLOYEE = "employee"


ROLE_PERMISSIONS = {
    RoleType.SUPER_ADMIN: {"manage_all_users", "view_all_attendance", "export_data", "manage_devices", "system_config"},
    RoleType.DEPT_ADMIN: {"manage_dept_users", "view_dept_attendance", "export_data", "manage_devices"},
    RoleType.EMPLOYEE: {"view_own_attendance", "register_face"},
}


def require_role(*roles: str):
    """角色权限依赖 - 限制只有指定角色可访问"""
    async def dependency(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="未认证")
        user_role = current_user.get("role", RoleType.EMPLOYEE)
        if user_role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return dependency


def require_permission(*permissions: str):
    """细粒度权限依赖"""
    async def dependency(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="未认证")
        user_role = current_user.get("role", RoleType.EMPLOYEE)
        user_perms = ROLE_PERMISSIONS.get(user_role, set())
        required = permissions[0]
        if required not in user_perms:
            raise HTTPException(status_code=403, detail=f"权限不足，需要 {required} 权限")
        return current_user
    return dependency
