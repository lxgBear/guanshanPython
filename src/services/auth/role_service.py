"""角色管理服务 (MongoDB 版本)"""

from typing import Optional, List, Tuple

from src.utils.logger import get_logger
from src.infrastructure.persistence.auth.mongodb import (
    MongoRoleRepository,
    MongoPermissionRepository
)
from src.core.domain.entities.auth import Role, RoleCreate, RoleUpdate, Permission

logger = get_logger(__name__)


class RoleServiceException(Exception):
    """角色服务异常"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class RoleService:
    """角色管理服务 (MongoDB)"""

    def __init__(self):
        self.role_repo = MongoRoleRepository()
        self.permission_repo = MongoPermissionRepository()

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
                parent_role_id = parent_role["_id"]

        # 创建角色（权限直接存储为代码列表）
        role = await self.role_repo.create(
            code=data.code,
            name=data.name,
            level=data.level,
            description=data.description,
            parent_role_id=parent_role_id,
            permissions=data.permission_codes or []
        )

        return await self.get_role(role["_id"])

    async def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色详情"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return None

        permission_codes = role.get("permissions", [])
        parent_role_code = None
        if role.get("parent_role_id"):
            parent = await self.role_repo.get_by_id(role["parent_role_id"])
            if parent:
                parent_role_code = parent.get("code")

        return Role(
            id=role["_id"],
            code=role["code"],
            name=role["name"],
            level=role.get("level", 0),
            description=role.get("description"),
            parent_role_code=parent_role_code,
            parent_role_id=role.get("parent_role_id"),
            is_system=role.get("is_system", False),
            is_active=role.get("is_active", True),
            created_at=role.get("created_at"),
            updated_at=role.get("updated_at"),
            permissions=permission_codes,
            permissions_count=len(permission_codes)
        )

    async def get_role_by_code(self, code: str) -> Optional[Role]:
        """根据代码获取角色"""
        role = await self.role_repo.get_by_code(code)
        if not role:
            return None

        permission_codes = role.get("permissions", [])
        parent_role_code = None
        if role.get("parent_role_id"):
            parent = await self.role_repo.get_by_id(role["parent_role_id"])
            if parent:
                parent_role_code = parent.get("code")

        return Role(
            id=role["_id"],
            code=role["code"],
            name=role["name"],
            level=role.get("level", 0),
            description=role.get("description"),
            parent_role_code=parent_role_code,
            parent_role_id=role.get("parent_role_id"),
            is_system=role.get("is_system", False),
            is_active=role.get("is_active", True),
            created_at=role.get("created_at"),
            updated_at=role.get("updated_at"),
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
            permission_codes = r.get("permissions", [])
            parent_role_code = None
            if r.get("parent_role_id"):
                parent = await self.role_repo.get_by_id(r["parent_role_id"])
                if parent:
                    parent_role_code = parent.get("code")

            result.append(Role(
                id=r["_id"],
                code=r["code"],
                name=r["name"],
                level=r.get("level", 0),
                description=r.get("description"),
                parent_role_code=parent_role_code,
                parent_role_id=r.get("parent_role_id"),
                is_system=r.get("is_system", False),
                is_active=r.get("is_active", True),
                created_at=r.get("created_at"),
                updated_at=r.get("updated_at"),
                permissions=permission_codes,
                permissions_count=len(permission_codes)
            ))

        return result

    async def update_role(self, role_id: str, data: RoleUpdate) -> Optional[Role]:
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

        # 注意：系统管理员作为总管理员，可以修改所有角色的所有属性
        # 仅保留删除保护，防止误删系统角色

        # 更新基本信息
        update_data = data.model_dump(exclude_unset=True, exclude={'permission_codes', 'parent_role_code'})
        if update_data:
            await self.role_repo.update(role_id, **update_data)

        # 更新权限
        if data.permission_codes is not None:
            await self.role_repo.assign_permissions(role_id, data.permission_codes)

        return await self.get_role(role_id)

    async def delete_role(self, role_id: str) -> bool:
        """删除角色（系统角色不可删除）"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise RoleServiceException("ROLE_001", "角色不存在")

        if role.get("is_system"):
            raise RoleServiceException("ROLE_003", "系统角色不可删除")

        return await self.role_repo.delete(role_id)

    async def update_role_permissions(
        self,
        role_id: str,
        permission_codes: List[str]
    ) -> Optional[Role]:
        """更新角色权限"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise RoleServiceException("ROLE_001", "角色不存在")

        await self.role_repo.assign_permissions(role_id, permission_codes)

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
                id=p["_id"],
                code=p["code"],
                name=p["name"],
                module=p["module"],
                description=p.get("description"),
                is_active=p.get("is_active", True),
                created_at=p.get("created_at")
            )
            for p in permissions
        ]

        return result, modules
