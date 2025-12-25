"""用户管理服务"""

from typing import Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import get_logger
from src.infrastructure.auth import PasswordHandler
from src.infrastructure.persistence.auth import UserRepository, RoleRepository
from src.infrastructure.persistence.auth.role_repository import PermissionRepository
from src.core.domain.entities.auth import User, UserCreate, UserUpdate

logger = get_logger(__name__)


class UserServiceException(Exception):
    """用户服务异常"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class UserService:
    """用户管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.password_handler = PasswordHandler()

    async def create_user(
        self,
        data: UserCreate,
        created_by: Optional[int] = None
    ) -> User:
        """
        创建用户

        Args:
            data: 用户创建数据
            created_by: 创建人ID

        Returns:
            创建的用户

        Raises:
            UserServiceException: 创建失败
        """
        # 检查用户名是否存在
        if await self.user_repo.check_username_exists(data.username):
            raise UserServiceException("USER_001", f"用户名 {data.username} 已存在")

        # 检查邮箱是否存在
        if data.email and await self.user_repo.check_email_exists(data.email):
            raise UserServiceException("USER_002", f"邮箱 {data.email} 已被使用")

        # 加密密码
        password_hash = self.password_handler.hash_password(data.password)

        # 创建用户
        user = await self.user_repo.create(
            username=data.username,
            email=data.email,
            password_hash=password_hash,
            display_name=data.display_name,
            phone=data.phone,
            department=data.department,
            created_by=created_by
        )

        # 分配角色
        if data.role_codes:
            roles = await self.role_repo.get_by_codes(data.role_codes)
            if roles:
                role_ids = [r.id for r in roles]
                await self.user_repo.assign_roles(user.id, role_ids, created_by)

        await self.session.commit()

        # 获取完整用户信息
        return await self.get_user(user.id)

    async def get_user(self, user_id: int) -> Optional[User]:
        """获取用户详情"""
        user_data = await self.user_repo.get_user_with_permissions(user_id)
        if not user_data:
            return None

        user, role_codes, permission_codes = user_data

        return User(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            phone=user.phone,
            department=user.department,
            is_active=user.is_active,
            is_locked=user.is_locked,
            lock_reason=user.lock_reason,
            last_login=user.last_login,
            login_attempts=user.login_attempts,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            roles=role_codes,
            permissions=permission_codes
        )

    async def list_users(
        self,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        role_code: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[User], int]:
        """
        获取用户列表

        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        users, total = await self.user_repo.list_users(
            page=page,
            size=size,
            keyword=keyword,
            role_code=role_code,
            is_active=is_active
        )

        result = []
        for u in users:
            role_codes = [ur.role.code for ur in u.user_roles if ur.role.is_active]
            result.append(User(
                id=u.id,
                username=u.username,
                email=u.email,
                display_name=u.display_name,
                phone=u.phone,
                department=u.department,
                is_active=u.is_active,
                is_locked=u.is_locked,
                lock_reason=u.lock_reason,
                last_login=u.last_login,
                login_attempts=u.login_attempts,
                created_at=u.created_at,
                updated_at=u.updated_at,
                created_by=u.created_by,
                roles=role_codes,
                permissions=[]  # 列表不需要返回权限
            ))

        return result, total

    async def update_user(
        self,
        user_id: int,
        data: UserUpdate,
        operator_id: Optional[int] = None
    ) -> Optional[User]:
        """
        更新用户

        Args:
            user_id: 用户ID
            data: 更新数据
            operator_id: 操作人ID

        Returns:
            更新后的用户
        """
        # 检查用户是否存在
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserServiceException("USER_003", "用户不存在")

        # 检查邮箱是否冲突
        if data.email and await self.user_repo.check_email_exists(data.email, exclude_id=user_id):
            raise UserServiceException("USER_002", f"邮箱 {data.email} 已被使用")

        # 更新基本信息
        update_data = data.model_dump(exclude_unset=True, exclude={'role_codes'})
        if update_data:
            await self.user_repo.update(user_id, **update_data)

        # 更新角色
        if data.role_codes is not None:
            roles = await self.role_repo.get_by_codes(data.role_codes)
            role_ids = [r.id for r in roles] if roles else []
            await self.user_repo.assign_roles(user_id, role_ids, operator_id)

        await self.session.commit()

        return await self.get_user(user_id)

    async def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        result = await self.user_repo.delete(user_id)
        if result:
            await self.session.commit()
        return result

    async def lock_user(self, user_id: int, reason: str) -> Optional[User]:
        """锁定用户"""
        await self.user_repo.lock_user(user_id, reason)
        await self.session.commit()
        return await self.get_user(user_id)

    async def unlock_user(self, user_id: int) -> Optional[User]:
        """解锁用户"""
        await self.user_repo.unlock_user(user_id)
        await self.session.commit()
        return await self.get_user(user_id)

    async def assign_roles(
        self,
        user_id: int,
        role_codes: List[str],
        operator_id: Optional[int] = None
    ) -> Optional[User]:
        """
        分配角色给用户

        Args:
            user_id: 用户ID
            role_codes: 角色代码列表
            operator_id: 操作人ID

        Returns:
            更新后的用户
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserServiceException("USER_003", "用户不存在")

        roles = await self.role_repo.get_by_codes(role_codes)
        if not roles:
            raise UserServiceException("ROLE_001", "角色不存在")

        role_ids = [r.id for r in roles]
        await self.user_repo.assign_roles(user_id, role_ids, operator_id)
        await self.session.commit()

        return await self.get_user(user_id)

    async def add_role(
        self,
        user_id: int,
        role_code: str,
        operator_id: Optional[int] = None
    ) -> Optional[User]:
        """给用户添加一个角色"""
        role = await self.role_repo.get_by_code(role_code)
        if not role:
            raise UserServiceException("ROLE_001", f"角色 {role_code} 不存在")

        await self.user_repo.add_role(user_id, role.id, operator_id)
        await self.session.commit()

        return await self.get_user(user_id)

    async def remove_role(self, user_id: int, role_code: str) -> Optional[User]:
        """移除用户的一个角色"""
        role = await self.role_repo.get_by_code(role_code)
        if not role:
            raise UserServiceException("ROLE_001", f"角色 {role_code} 不存在")

        await self.user_repo.remove_role(user_id, role.id)
        await self.session.commit()

        return await self.get_user(user_id)
