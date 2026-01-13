"""用户领域实体"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, field_validator
import re


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    department: Optional[str] = Field(None, max_length=100, description="部门")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v


class UserCreate(UserBase):
    """创建用户请求模型"""
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    role_codes: List[str] = Field(default_factory=list, description="角色代码列表")


class UserUpdate(BaseModel):
    """更新用户请求模型"""
    email: Optional[EmailStr] = None
    display_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    role_codes: Optional[List[str]] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v


class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: str  # MongoDB 使用字符串 ID (Snowflake)
    is_active: bool = True
    is_locked: bool = False
    lock_reason: Optional[str] = None
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None  # MongoDB 使用字符串 ID

    class Config:
        from_attributes = True


class User(UserInDB):
    """用户响应模型（包含角色信息）"""
    roles: List[str] = Field(default_factory=list, description="角色代码列表")
    permissions: List[str] = Field(default_factory=list, description="权限代码列表")


class UserLogin(BaseModel):
    """用户登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    remember_me: bool = Field(default=False, description="记住我")


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class TokenRefresh(BaseModel):
    """刷新Token请求模型"""
    refresh_token: str


class PasswordChange(BaseModel):
    """修改密码请求模型"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class PasswordReset(BaseModel):
    """重置密码请求模型（管理员用）"""
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


