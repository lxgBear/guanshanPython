"""用户仓储实现"""

from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.utils.logger import get_logger
from .models import UserModel, UserRoleModel, RoleModel, RolePermissionModel, PermissionModel

logger = get_logger(__name__)


class UserRepository:
    """用户仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        username: str,
        email: Optional[str],
        password_hash: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        department: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> UserModel:
        """创建用户"""
        user = UserModel(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            phone=phone,
            department=department,
            created_by=created_by
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: int) -> Optional[UserModel]:
        """根据ID获取用户"""
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(selectinload(UserModel.user_roles).selectinload(UserRoleModel.role))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[UserModel]:
        """根据用户名获取用户"""
        stmt = (
            select(UserModel)
            .where(UserModel.username == username)
            .options(selectinload(UserModel.user_roles).selectinload(UserRoleModel.role))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        """根据邮箱获取用户"""
        stmt = (
            select(UserModel)
            .where(UserModel.email == email)
            .options(selectinload(UserModel.user_roles).selectinload(UserRoleModel.role))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_with_permissions(self, user_id: int) -> Optional[Tuple[UserModel, List[str], List[str]]]:
        """
        获取用户及其角色和权限

        Returns:
            Tuple[UserModel, List[str], List[str]]: (用户, 角色代码列表, 权限代码列表)
        """
        # 获取用户
        user = await self.get_by_id(user_id)
        if not user:
            return None

        # 获取角色代码列表
        role_codes = [ur.role.code for ur in user.user_roles if ur.role.is_active]

        # 获取权限代码列表
        role_ids = [ur.role_id for ur in user.user_roles]
        if role_ids:
            stmt = (
                select(PermissionModel.code)
                .join(RolePermissionModel)
                .where(
                    RolePermissionModel.role_id.in_(role_ids),
                    PermissionModel.is_active == True
                )
                .distinct()
            )
            result = await self.session.execute(stmt)
            permission_codes = [row[0] for row in result.fetchall()]
        else:
            permission_codes = []

        return user, role_codes, permission_codes

    async def list_users(
        self,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        role_code: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[UserModel], int]:
        """
        获取用户列表

        Returns:
            Tuple[List[UserModel], int]: (用户列表, 总数)
        """
        # 基础查询
        stmt = select(UserModel).options(
            selectinload(UserModel.user_roles).selectinload(UserRoleModel.role)
        )

        # 筛选条件
        conditions = []

        if keyword:
            conditions.append(
                or_(
                    UserModel.username.ilike(f"%{keyword}%"),
                    UserModel.display_name.ilike(f"%{keyword}%"),
                    UserModel.email.ilike(f"%{keyword}%")
                )
            )

        if is_active is not None:
            conditions.append(UserModel.is_active == is_active)

        if role_code:
            # 子查询：查找具有指定角色的用户ID
            role_subquery = (
                select(UserRoleModel.user_id)
                .join(RoleModel)
                .where(RoleModel.code == role_code)
            )
            conditions.append(UserModel.id.in_(role_subquery))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 计算总数
        count_stmt = select(func.count()).select_from(UserModel)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页
        stmt = stmt.order_by(UserModel.created_at.desc())
        stmt = stmt.offset((page - 1) * size).limit(size)

        result = await self.session.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def update(
        self,
        user_id: int,
        **kwargs
    ) -> Optional[UserModel]:
        """更新用户"""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        await self.session.flush()
        return user

    async def delete(self, user_id: int) -> bool:
        """删除用户"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        await self.session.delete(user)
        await self.session.flush()
        return True

    async def lock_user(self, user_id: int, reason: str) -> Optional[UserModel]:
        """锁定用户"""
        return await self.update(user_id, is_locked=True, lock_reason=reason)

    async def unlock_user(self, user_id: int) -> Optional[UserModel]:
        """解锁用户"""
        return await self.update(user_id, is_locked=False, lock_reason=None, login_attempts=0)

    async def increment_login_attempts(self, user_id: int) -> int:
        """增加登录尝试次数"""
        user = await self.get_by_id(user_id)
        if user:
            user.login_attempts += 1
            await self.session.flush()
            return user.login_attempts
        return 0

    async def reset_login_attempts(self, user_id: int) -> None:
        """重置登录尝试次数"""
        await self.update(user_id, login_attempts=0)

    async def update_last_login(self, user_id: int) -> None:
        """更新最后登录时间"""
        await self.update(user_id, last_login=datetime.utcnow())

    async def assign_roles(
        self,
        user_id: int,
        role_ids: List[int],
        assigned_by: Optional[int] = None
    ) -> None:
        """
        分配角色给用户（支持多角色）

        Args:
            user_id: 用户ID
            role_ids: 角色ID列表
            assigned_by: 操作人ID
        """
        # 删除现有角色关联
        stmt = delete(UserRoleModel).where(UserRoleModel.user_id == user_id)
        await self.session.execute(stmt)

        # 添加新角色关联
        for role_id in role_ids:
            user_role = UserRoleModel(
                user_id=user_id,
                role_id=role_id,
                assigned_by=assigned_by
            )
            self.session.add(user_role)

        await self.session.flush()

    async def add_role(
        self,
        user_id: int,
        role_id: int,
        assigned_by: Optional[int] = None
    ) -> bool:
        """给用户添加一个角色"""
        # 检查是否已存在
        stmt = select(UserRoleModel).where(
            UserRoleModel.user_id == user_id,
            UserRoleModel.role_id == role_id
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            return False  # 已存在

        user_role = UserRoleModel(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by
        )
        self.session.add(user_role)
        await self.session.flush()
        return True

    async def remove_role(self, user_id: int, role_id: int) -> bool:
        """移除用户的一个角色"""
        stmt = delete(UserRoleModel).where(
            UserRoleModel.user_id == user_id,
            UserRoleModel.role_id == role_id
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_user_roles(self, user_id: int) -> List[RoleModel]:
        """获取用户的所有角色"""
        stmt = (
            select(RoleModel)
            .join(UserRoleModel)
            .where(UserRoleModel.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_username_exists(self, username: str, exclude_id: Optional[int] = None) -> bool:
        """检查用户名是否存在"""
        stmt = select(func.count()).select_from(UserModel).where(UserModel.username == username)
        if exclude_id:
            stmt = stmt.where(UserModel.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def check_email_exists(self, email: str, exclude_id: Optional[int] = None) -> bool:
        """检查邮箱是否存在"""
        stmt = select(func.count()).select_from(UserModel).where(UserModel.email == email)
        if exclude_id:
            stmt = stmt.where(UserModel.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0
