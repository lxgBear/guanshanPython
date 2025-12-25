"""认证领域实体模块"""

from .user import (
    User, UserCreate, UserUpdate, UserInDB, UserLogin,
    TokenResponse, TokenRefresh, PasswordChange, PasswordReset
)
from .role import Role, RoleCreate, RoleUpdate, RoleAssign, RolePermissionUpdate
from .permission import Permission, PermissionCreate, PermissionCode, DEFAULT_ROLE_PERMISSIONS

__all__ = [
    # User entities
    "User", "UserCreate", "UserUpdate", "UserInDB", "UserLogin",
    "TokenResponse", "TokenRefresh", "PasswordChange", "PasswordReset",
    # Role entities
    "Role", "RoleCreate", "RoleUpdate", "RoleAssign", "RolePermissionUpdate",
    # Permission entities
    "Permission", "PermissionCreate", "PermissionCode", "DEFAULT_ROLE_PERMISSIONS",
]
