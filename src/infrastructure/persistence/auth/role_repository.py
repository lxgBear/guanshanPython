"""角色仓储实现"""

from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.utils.logger import get_logger
from .models import RoleModel, RolePermissionModel, PermissionModel

logger = get_logger(__name__)


class RoleRepository:
    """角色仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        code: str,
        name: str,
        level: int = 0,
        description: Optional[str] = None,
        parent_role_id: Optional[int] = None,
        is_system: bool = False
    ) -> RoleModel:
        """创建角色"""
        role = RoleModel(
            code=code,
            name=name,
            level=level,
            description=description,
            parent_role_id=parent_role_id,
            is_system=is_system
        )
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_by_id(self, role_id: int) -> Optional[RoleModel]:
        """根据ID获取角色"""
        stmt = (
            select(RoleModel)
            .where(RoleModel.id == role_id)
            .options(selectinload(RoleModel.role_permissions).selectinload(RolePermissionModel.permission))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[RoleModel]:
        """根据代码获取角色"""
        stmt = (
            select(RoleModel)
            .where(RoleModel.code == code)
            .options(selectinload(RoleModel.role_permissions).selectinload(RolePermissionModel.permission))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_codes(self, codes: List[str]) -> List[RoleModel]:
        """根据代码列表获取角色"""
        stmt = select(RoleModel).where(RoleModel.code.in_(codes))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_roles(
        self,
        is_active: Optional[bool] = None,
        include_system: bool = True
    ) -> List[RoleModel]:
        """获取角色列表"""
        stmt = (
            select(RoleModel)
            .options(selectinload(RoleModel.role_permissions).selectinload(RolePermissionModel.permission))
            .order_by(RoleModel.level.desc())
        )

        if is_active is not None:
            stmt = stmt.where(RoleModel.is_active == is_active)

        if not include_system:
            stmt = stmt.where(RoleModel.is_system == False)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        role_id: int,
        **kwargs
    ) -> Optional[RoleModel]:
        """更新角色"""
        role = await self.get_by_id(role_id)
        if not role:
            return None

        # 系统角色不允许修改代码
        if role.is_system and 'code' in kwargs:
            del kwargs['code']

        for key, value in kwargs.items():
            if hasattr(role, key) and value is not None:
                setattr(role, key, value)

        role.updated_at = datetime.utcnow()
        await self.session.flush()
        return role

    async def delete(self, role_id: int) -> bool:
        """删除角色（系统角色不可删除）"""
        role = await self.get_by_id(role_id)
        if not role or role.is_system:
            return False

        await self.session.delete(role)
        await self.session.flush()
        return True

    async def assign_permissions(
        self,
        role_id: int,
        permission_ids: List[int],
        granted_by: Optional[int] = None
    ) -> None:
        """分配权限给角色"""
        # 删除现有权限关联
        stmt = delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        await self.session.execute(stmt)

        # 添加新权限关联
        for permission_id in permission_ids:
            role_permission = RolePermissionModel(
                role_id=role_id,
                permission_id=permission_id,
                granted_by=granted_by
            )
            self.session.add(role_permission)

        await self.session.flush()

    async def get_role_permissions(self, role_id: int) -> List[PermissionModel]:
        """获取角色的所有权限"""
        stmt = (
            select(PermissionModel)
            .join(RolePermissionModel)
            .where(RolePermissionModel.role_id == role_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_code_exists(self, code: str, exclude_id: Optional[int] = None) -> bool:
        """检查角色代码是否存在"""
        stmt = select(func.count()).select_from(RoleModel).where(RoleModel.code == code)
        if exclude_id:
            stmt = stmt.where(RoleModel.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0


class PermissionRepository:
    """权限仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        code: str,
        name: str,
        module: str,
        description: Optional[str] = None
    ) -> PermissionModel:
        """创建权限"""
        permission = PermissionModel(
            code=code,
            name=name,
            module=module,
            description=description
        )
        self.session.add(permission)
        await self.session.flush()
        return permission

    async def get_by_id(self, permission_id: int) -> Optional[PermissionModel]:
        """根据ID获取权限"""
        stmt = select(PermissionModel).where(PermissionModel.id == permission_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[PermissionModel]:
        """根据代码获取权限"""
        stmt = select(PermissionModel).where(PermissionModel.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_codes(self, codes: List[str]) -> List[PermissionModel]:
        """根据代码列表获取权限"""
        stmt = select(PermissionModel).where(PermissionModel.code.in_(codes))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_permissions(
        self,
        module: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[PermissionModel], List[str]]:
        """
        获取权限列表

        Returns:
            Tuple[List[PermissionModel], List[str]]: (权限列表, 模块列表)
        """
        stmt = select(PermissionModel).order_by(PermissionModel.module, PermissionModel.code)

        if module:
            stmt = stmt.where(PermissionModel.module == module)

        if is_active is not None:
            stmt = stmt.where(PermissionModel.is_active == is_active)

        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())

        # 获取模块列表
        module_stmt = select(PermissionModel.module).distinct().order_by(PermissionModel.module)
        module_result = await self.session.execute(module_stmt)
        modules = [row[0] for row in module_result.fetchall()]

        return permissions, modules

    async def check_code_exists(self, code: str) -> bool:
        """检查权限代码是否存在"""
        stmt = select(func.count()).select_from(PermissionModel).where(PermissionModel.code == code)
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0
