"""MongoDB 认证仓储模块"""

from .user_repository import MongoUserRepository, create_auth_indexes
from .role_repository import MongoRoleRepository, MongoPermissionRepository, create_role_indexes

__all__ = [
    "MongoUserRepository",
    "MongoRoleRepository",
    "MongoPermissionRepository",
    "create_auth_indexes",
    "create_role_indexes",
]
