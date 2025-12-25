"""认证依赖注入"""

from typing import Optional, List, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.connection import get_mariadb_session
from src.infrastructure.auth import JWTHandler, TokenData
from src.services.auth import AuthService
from src.core.domain.entities.auth import User

# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)

# JWT 处理器
jwt_handler = JWTHandler()


async def get_db_session() -> AsyncSession:
    """获取数据库会话"""
    session = await get_mariadb_session()
    try:
        yield session
    finally:
        await session.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """
    获取当前用户（可选认证）

    Returns:
        User 或 None（未认证）
    """
    if not credentials:
        return None

    token = credentials.credentials
    token_data = jwt_handler.verify_token(token)

    if not token_data:
        return None

    if token_data.token_type != "access":
        return None

    # 获取完整用户信息
    auth_service = AuthService(session)
    user = await auth_service.get_current_user(token)

    return user


async def get_current_active_user(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户（必须认证）

    Raises:
        HTTPException: 未认证或用户不可用
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_003", "message": "未认证或令牌已过期"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_006", "message": "账户已禁用"},
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_002", "message": f"账户已锁定: {user.lock_reason}"},
        )

    return user


def require_permissions(*required_permissions: str) -> Callable:
    """
    权限检查依赖

    Args:
        required_permissions: 所需权限代码（任一满足即可）

    Usage:
        @router.get("/admin", dependencies=[Depends(require_permissions("user:create", "user:delete"))])
        async def admin_only():
            pass
    """
    async def permission_checker(
        user: User = Depends(get_current_active_user)
    ) -> User:
        # admin 角色拥有所有权限
        if "admin" in user.roles:
            return user

        # 检查是否有任一所需权限
        user_permissions = set(user.permissions)
        required = set(required_permissions)

        if not user_permissions.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "AUTH_005",
                    "message": f"权限不足，需要以下权限之一: {', '.join(required_permissions)}"
                },
            )

        return user

    return permission_checker


def require_roles(*required_roles: str) -> Callable:
    """
    角色检查依赖

    Args:
        required_roles: 所需角色代码（任一满足即可）

    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles("admin", "chief_reviewer"))])
        async def admin_only():
            pass
    """
    async def role_checker(
        user: User = Depends(get_current_active_user)
    ) -> User:
        user_roles = set(user.roles)
        required = set(required_roles)

        if not user_roles.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "AUTH_005",
                    "message": f"角色不足，需要以下角色之一: {', '.join(required_roles)}"
                },
            )

        return user

    return role_checker


class PermissionChecker:
    """
    权限检查器类（支持更复杂的权限逻辑）

    Usage:
        checker = PermissionChecker(["user:create"], require_all=True)
        @router.get("/", dependencies=[Depends(checker)])
        async def endpoint():
            pass
    """

    def __init__(
        self,
        permissions: List[str],
        require_all: bool = False
    ):
        self.permissions = permissions
        self.require_all = require_all

    async def __call__(
        self,
        user: User = Depends(get_current_active_user)
    ) -> User:
        # admin 角色拥有所有权限
        if "admin" in user.roles:
            return user

        user_permissions = set(user.permissions)
        required = set(self.permissions)

        if self.require_all:
            # 需要所有权限
            if not required.issubset(user_permissions):
                missing = required - user_permissions
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "AUTH_005",
                        "message": f"权限不足，缺少: {', '.join(missing)}"
                    },
                )
        else:
            # 任一权限即可
            if not user_permissions.intersection(required):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "AUTH_005",
                        "message": f"权限不足，需要以下权限之一: {', '.join(self.permissions)}"
                    },
                )

        return user
