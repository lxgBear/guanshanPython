"""认证API模块"""

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .roles import router as roles_router

# 创建认证模块主路由
router = APIRouter()

# 注册子路由
router.include_router(auth_router, tags=["认证"])
router.include_router(users_router, prefix="/users", tags=["用户管理"])
router.include_router(roles_router, prefix="/roles", tags=["角色管理"])
