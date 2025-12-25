"""API 依赖注入模块"""

from .auth import (
    get_db_session,
    get_current_user,
    get_current_active_user,
    require_permissions,
    require_roles,
)

__all__ = [
    "get_db_session",
    "get_current_user",
    "get_current_active_user",
    "require_permissions",
    "require_roles",
]
