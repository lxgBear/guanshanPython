"""用户数据库模型"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UserModel(Base):
    """用户表模型"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    login_attempts: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系：一个用户可以有多个角色
    user_roles: Mapped[List["UserRoleModel"]] = relationship(
        "UserRoleModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # 关系：登录历史
    login_history: Mapped[List["LoginHistoryModel"]] = relationship(
        "LoginHistoryModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # 关系：Token
    tokens: Mapped[List["UserTokenModel"]] = relationship(
        "UserTokenModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class UserRoleModel(Base):
    """用户-角色关联表模型（支持多角色）"""
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="user_roles")
    role: Mapped["RoleModel"] = relationship("RoleModel", back_populates="user_roles")

    __table_args__ = (
        Index("idx_user_role", "user_id", "role_id", unique=True),
    )


class UserTokenModel(Base):
    """用户Token表模型（用于Token管理和撤销）"""
    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 关系
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="tokens")


class LoginHistoryModel(Base):
    """登录历史表模型"""
    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    login_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed, locked
    fail_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 关系
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="login_history")


# 导入延迟引用
from .role_model import RoleModel  # noqa: E402
