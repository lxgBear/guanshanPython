"""权限领域实体"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import re


class PermissionModule(str, Enum):
    """权限模块枚举"""
    USER = "user"
    ROLE = "role"
    INFO = "info"
    REVIEW = "review"
    SEARCH = "search"
    SYSTEM = "system"


class PermissionAction(str, Enum):
    """权限操作枚举"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    ASSIGN = "assign"
    EXECUTE = "execute"
    APPROVE = "approve"
    CONFIG = "config"


class PermissionCode(str, Enum):
    """预定义权限代码"""
    # 用户管理
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"

    # 角色管理
    ROLE_CREATE = "role:create"
    ROLE_READ = "role:read"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_ASSIGN = "role:assign"

    # 信息采集
    INFO_CREATE = "info:create"
    INFO_READ = "info:read"
    INFO_UPDATE = "info:update"
    INFO_DELETE = "info:delete"

    # 校审管理
    REVIEW_ASSIGN = "review:assign"
    REVIEW_EXECUTE = "review:execute"
    REVIEW_APPROVE = "review:approve"
    REVIEW_READ = "review:read"

    # NL搜索
    SEARCH_BASIC = "search:basic"
    SEARCH_ADVANCED = "search:advanced"
    SEARCH_MULTILANG = "search:multilang"

    # 系统管理
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOG = "system:log"
    SYSTEM_API = "system:api"


class PermissionBase(BaseModel):
    """权限基础模型"""
    code: str = Field(..., min_length=3, max_length=100, description="权限代码")
    name: str = Field(..., min_length=2, max_length=100, description="权限名称")
    module: str = Field(..., max_length=50, description="所属模块")
    description: Optional[str] = Field(None, max_length=500, description="权限描述")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r'^[a-z]+:[a-z_]+$', v):
            raise ValueError('权限代码格式必须为 module:action')
        return v


class PermissionCreate(PermissionBase):
    """创建权限请求模型"""
    pass


class PermissionInDB(PermissionBase):
    """数据库中的权限模型"""
    id: int
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class Permission(PermissionInDB):
    """权限响应模型"""
    pass


class PermissionList(BaseModel):
    """权限列表响应模型"""
    items: List[Permission]
    modules: List[str] = Field(default_factory=list, description="模块列表")


# 角色权限配置（用于初始化）
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        # 所有权限
        PermissionCode.USER_CREATE, PermissionCode.USER_READ, PermissionCode.USER_UPDATE,
        PermissionCode.USER_DELETE, PermissionCode.USER_LIST,
        PermissionCode.ROLE_CREATE, PermissionCode.ROLE_READ, PermissionCode.ROLE_UPDATE,
        PermissionCode.ROLE_DELETE, PermissionCode.ROLE_ASSIGN,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        PermissionCode.SYSTEM_CONFIG, PermissionCode.SYSTEM_LOG, PermissionCode.SYSTEM_API,
    ],
    "chief_reviewer": [
        PermissionCode.USER_CREATE, PermissionCode.USER_READ, PermissionCode.USER_UPDATE,
        PermissionCode.USER_LIST, PermissionCode.ROLE_ASSIGN,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        PermissionCode.SYSTEM_LOG,
    ],
    "direction_reviewer": [
        PermissionCode.USER_READ, PermissionCode.USER_LIST,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
    ],
    "reviewer": [
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
    ],
    "collector": [
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED,
    ],
    "customer": [
        PermissionCode.SEARCH_BASIC,
    ],
}
