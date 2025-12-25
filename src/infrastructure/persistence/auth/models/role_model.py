"""角色数据库模型"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user_model import UserRoleModel
    from .permission_model import PermissionModel


class RoleModel(Base):
    """角色表模型"""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=True
    )

    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系：用户角色关联
    user_roles: Mapped[List["UserRoleModel"]] = relationship(
        "UserRoleModel",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    # 关系：角色权限关联
    role_permissions: Mapped[List["RolePermissionModel"]] = relationship(
        "RolePermissionModel",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    # 自引用：父级角色
    parent_role: Mapped[Optional["RoleModel"]] = relationship(
        "RoleModel",
        remote_side=[id],
        backref="child_roles"
    )


class RolePermissionModel(Base):
    """角色-权限关联表模型"""
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    role: Mapped["RoleModel"] = relationship("RoleModel", back_populates="role_permissions")
    permission: Mapped["PermissionModel"] = relationship(
        "PermissionModel", back_populates="role_permissions"
    )

    __table_args__ = (
        Index("idx_role_permission", "role_id", "permission_id", unique=True),
    )
