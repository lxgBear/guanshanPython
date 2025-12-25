"""角色管理服务"""

from typing import Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import get_logger
from src.infrastructure.persistence.auth import RoleRepository
from src.infrastructure.persistence.auth.role_repository import PermissionRepository
from src.core.domain.entities.auth import Role, RoleCreate, RoleUpdate, Permission

logger = get_logger(__name__)


class RoleServiceException(Exception):
    """角色服务异常"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class RoleService:
    """角色管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.role_repo = RoleRepository(session)
        self.permission_repo = PermissionRepository(session)

    async def create_role(self, data: RoleCreate) -> Role:
        """
        创建角色

        Args:
            data: 角色创建数据

        Returns:
            创建的角色

        Raises:
            RoleServiceException: 创建失败
        """
        # 检查角色代码是否存在
        if await self.role_repo.check_code_exists(data.code):
            raise RoleServiceException("ROLE_002", f"角色代码 {data.code} 已存在")

        # 获取父级角色ID
        parent_role_id = None
        if data.parent_role_code:
            parent_role = await self.role_repo.get_by_code(data.parent_role_code)
            if parent_role:
                parent_role_id = parent_role.id

        # 创建角色
        role = await self.role_repo.create(
            code=data.code,
            name=data.name,
            level=data.level,
            description=data.description,
            parent_role_id=parent_role_id
        )

        # 分配权限
        if data.permission_codes:
            permissions = await self.permission_repo.get_by_codes(data.permission_codes)
            if permissions:
                permission_ids = [p.id for p in permissions]
                await self.role_repo.assign_permissions(role.id, permission_ids)

        await self.session.commit()

        return await self.get_role(role.id)

    async def get_role(self, role_id: int) -> Optional[Role]:
        """获取角色详情"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return None

        permission_codes = [rp.permission.code for rp in role.role_permissions]

        return Role(
            id=role.id,
            code=role.code,
            name=role.name,
            level=role.level,
            description=role.description,
            parent_role_code=role.parent_role.code if role.parent_role else None,
            parent_role_id=role.parent_role_id,
            is_system=role.is_system,
            is_active=role.is_active,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=permission_codes,
            permissions_count=len(permission_codes)
        )

    async def get_role_by_code(self, code: str) -> Optional[Role]:
        """根据代码获取角色"""
        role = await self.role_repo.get_by_code(code)
        if not role:
            return None

        permission_codes = [rp.permission.code for rp in role.role_permissions]

        return Role(
            id=role.id,
            code=role.code,
            name=role.name,
            level=role.level,
            description=role.description,
            parent_role_code=role.parent_role.code if role.parent_role else None,
            parent_role_id=role.parent_role_id,
            is_system=role.is_system,
            is_active=role.is_active,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=permission_codes,
            permissions_count=len(permission_codes)
        )

    async def list_roles(
        self,
        is_active: Optional[bool] = None,
        include_system: bool = True
    ) -> List[Role]:
        """获取角色列表"""
        roles = await self.role_repo.list_roles(is_active=is_active, include_system=include_system)

        result = []
        for r in roles:
            permission_codes = [rp.permission.code for rp in r.role_permissions]
            result.append(Role(
                id=r.id,
                code=r.code,
                name=r.name,
                level=r.level,
                description=r.description,
                parent_role_code=r.parent_role.code if r.parent_role else None,
                parent_role_id=r.parent_role_id,
                is_system=r.is_system,
                is_active=r.is_active,
                created_at=r.created_at,
                updated_at=r.updated_at,
                permissions=permission_codes,
                permissions_count=len(permission_codes)
            ))

        return result

    async def update_role(self, role_id: int, data: RoleUpdate) -> Optional[Role]:
        """
        更新角色

        Args:
            role_id: 角色ID
            data: 更新数据

        Returns:
            更新后的角色
        """
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise RoleServiceException("ROLE_001", "角色不存在")

        # 系统角色不允许修改某些字段
        if role.is_system:
            if data.level is not None or data.parent_role_code is not None:
                raise RoleServiceException("ROLE_003", "系统角色不允许修改权限级别和父级角色")

        # 更新基本信息
        update_data = data.model_dump(exclude_unset=True, exclude={'permission_codes', 'parent_role_code'})
        if update_data:
            await self.role_repo.update(role_id, **update_data)

        # 更新权限
        if data.permission_codes is not None:
            permissions = await self.permission_repo.get_by_codes(data.permission_codes)
            permission_ids = [p.id for p in permissions] if permissions else []
            await self.role_repo.assign_permissions(role_id, permission_ids)

        await self.session.commit()

        return await self.get_role(role_id)

    async def delete_role(self, role_id: int) -> bool:
        """删除角色（系统角色不可删除）"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise RoleServiceException("ROLE_001", "角色不存在")

        if role.is_system:
            raise RoleServiceException("ROLE_003", "系统角色不可删除")

        result = await self.role_repo.delete(role_id)
        if result:
            await self.session.commit()
        return result

    async def update_role_permissions(
        self,
        role_id: int,
        permission_codes: List[str]
    ) -> Optional[Role]:
        """更新角色权限"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise RoleServiceException("ROLE_001", "角色不存在")

        permissions = await self.permission_repo.get_by_codes(permission_codes)
        permission_ids = [p.id for p in permissions] if permissions else []
        await self.role_repo.assign_permissions(role_id, permission_ids)
        await self.session.commit()

        return await self.get_role(role_id)

    async def list_permissions(
        self,
        module: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Permission], List[str]]:
        """
        获取权限列表

        Returns:
            Tuple[List[Permission], List[str]]: (权限列表, 模块列表)
        """
        permissions, modules = await self.permission_repo.list_permissions(
            module=module,
            is_active=is_active
        )

        result = [
            Permission(
                id=p.id,
                code=p.code,
                name=p.name,
                module=p.module,
                description=p.description,
                is_active=p.is_active,
                created_at=p.created_at
            )
            for p in permissions
        ]

        return result, modules
