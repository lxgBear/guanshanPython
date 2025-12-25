"""角色领域实体"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class RoleBase(BaseModel):
    """角色基础模型"""
    code: str = Field(..., min_length=2, max_length=50, description="角色代码")
    name: str = Field(..., min_length=2, max_length=100, description="角色名称")
    level: int = Field(default=0, ge=0, le=100, description="权限级别 (0-100)")
    description: Optional[str] = Field(None, max_length=500, description="角色描述")
    parent_role_code: Optional[str] = Field(None, description="父级角色代码")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError('角色代码必须以小写字母开头，只能包含小写字母、数字和下划线')
        return v


class RoleCreate(RoleBase):
    """创建角色请求模型"""
    permission_codes: List[str] = Field(default_factory=list, description="权限代码列表")


class RoleUpdate(BaseModel):
    """更新角色请求模型"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    level: Optional[int] = Field(None, ge=0, le=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_role_code: Optional[str] = None
    is_active: Optional[bool] = None
    permission_codes: Optional[List[str]] = None


class RoleInDB(RoleBase):
    """数据库中的角色模型"""
    id: int
    parent_role_id: Optional[int] = None
    is_system: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Role(RoleInDB):
    """角色响应模型（包含权限信息）"""
    permissions: List[str] = Field(default_factory=list, description="权限代码列表")
    permissions_count: int = Field(default=0, description="权限数量")


class RoleAssign(BaseModel):
    """分配角色请求模型"""
    role_codes: List[str] = Field(..., min_length=1, description="角色代码列表")


class RolePermissionUpdate(BaseModel):
    """更新角色权限请求模型"""
    permission_codes: List[str] = Field(..., description="权限代码列表")
