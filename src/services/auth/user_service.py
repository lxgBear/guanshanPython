"""用户管理服务 (MongoDB 版本)"""

from typing import Optional, List, Tuple

from src.utils.logger import get_logger
from src.infrastructure.auth import PasswordHandler
from src.infrastructure.persistence.auth.mongodb import MongoUserRepository, MongoRoleRepository
from src.core.domain.entities.auth import User, UserCreate, UserUpdate

logger = get_logger(__name__)


class UserServiceException(Exception):
    """用户服务异常"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class UserService:
    """用户管理服务 (MongoDB 版本)"""

    def __init__(self):
        """初始化用户服务（无需 session 参数）"""
        self.user_repo = MongoUserRepository()
        self.role_repo = MongoRoleRepository()
        self.password_handler = PasswordHandler()

    async def create_user(
        self,
        data: UserCreate,
        created_by: Optional[str] = None
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
        user_doc = await self.user_repo.create(
            username=data.username,
            email=data.email,
            password_hash=password_hash,
            display_name=data.display_name,
            phone=data.phone,
            department=data.department,
            roles=data.role_codes or [],  # 直接存储角色代码
            created_by=created_by
        )

        # 获取完整用户信息
        return await self.get_user(user_doc["_id"])

    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户详情"""
        user_data = await self.user_repo.get_user_with_permissions(user_id)
        if not user_data:
            return None

        user_doc, role_codes, permission_codes = user_data

        return User(
            id=user_doc["_id"],
            username=user_doc["username"],
            email=user_doc.get("email"),
            display_name=user_doc.get("display_name"),
            phone=user_doc.get("phone"),
            department=user_doc.get("department"),
            is_active=user_doc.get("is_active", True),
            is_locked=user_doc.get("is_locked", False),
            lock_reason=user_doc.get("lock_reason"),
            last_login=user_doc.get("last_login"),
            login_attempts=user_doc.get("login_attempts", 0),
            created_at=user_doc.get("created_at"),
            updated_at=user_doc.get("updated_at"),
            created_by=user_doc.get("created_by"),
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
            role_codes = u.get("roles", [])
            result.append(User(
                id=u["_id"],
                username=u["username"],
                email=u.get("email"),
                display_name=u.get("display_name"),
                phone=u.get("phone"),
                department=u.get("department"),
                is_active=u.get("is_active", True),
                is_locked=u.get("is_locked", False),
                lock_reason=u.get("lock_reason"),
                last_login=u.get("last_login"),
                login_attempts=u.get("login_attempts", 0),
                created_at=u.get("created_at"),
                updated_at=u.get("updated_at"),
                created_by=u.get("created_by"),
                roles=role_codes,
                permissions=[]  # 列表不需要返回权限
            ))

        return result, total

    async def update_user(
        self,
        user_id: str,
        data: UserUpdate,
        operator_id: Optional[str] = None
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
            await self.user_repo.assign_roles(user_id, data.role_codes, operator_id)

        return await self.get_user(user_id)

    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        return await self.user_repo.delete(user_id)

    async def lock_user(self, user_id: str, reason: str) -> Optional[User]:
        """锁定用户"""
        await self.user_repo.lock_user(user_id, reason)
        return await self.get_user(user_id)

    async def unlock_user(self, user_id: str) -> Optional[User]:
        """解锁用户"""
        await self.user_repo.unlock_user(user_id)
        return await self.get_user(user_id)

    async def assign_roles(
        self,
        user_id: str,
        role_codes: List[str],
        operator_id: Optional[str] = None
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

        # 验证角色是否存在
        roles = await self.role_repo.get_by_codes(role_codes)
        if len(roles) != len(role_codes):
            raise UserServiceException("ROLE_001", "部分角色不存在")

        await self.user_repo.assign_roles(user_id, role_codes, operator_id)

        return await self.get_user(user_id)

    async def add_role(
        self,
        user_id: str,
        role_code: str,
        operator_id: Optional[str] = None
    ) -> Optional[User]:
        """给用户添加一个角色"""
        role = await self.role_repo.get_by_code(role_code)
        if not role:
            raise UserServiceException("ROLE_001", f"角色 {role_code} 不存在")

        await self.user_repo.add_role(user_id, role_code, operator_id)

        return await self.get_user(user_id)

    async def remove_role(self, user_id: str, role_code: str) -> Optional[User]:
        """移除用户的一个角色"""
        role = await self.role_repo.get_by_code(role_code)
        if not role:
            raise UserServiceException("ROLE_001", f"角色 {role_code} 不存在")

        await self.user_repo.remove_role(user_id, role_code)

        return await self.get_user(user_id)

    async def list_users_by_permission(
        self,
        permission_code: str,
        keyword: Optional[str] = None,
        exclude_user_id: Optional[str] = None
    ) -> Tuple[List[User], int]:
        """
        获取拥有指定权限的用户列表

        v2.8.0: 用于获取可选审核员列表

        Args:
            permission_code: 权限代码
            keyword: 搜索关键词
            exclude_user_id: 排除的用户ID

        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        users, total = await self.user_repo.list_users_by_permission(
            permission_code=permission_code,
            keyword=keyword,
            exclude_user_id=exclude_user_id
        )

        result = []
        for u in users:
            role_codes = u.get("roles", [])
            result.append(User(
                id=u["_id"],
                username=u["username"],
                email=u.get("email"),
                display_name=u.get("display_name"),
                phone=u.get("phone"),
                department=u.get("department"),
                is_active=u.get("is_active", True),
                is_locked=u.get("is_locked", False),
                lock_reason=u.get("lock_reason"),
                last_login=u.get("last_login"),
                login_attempts=u.get("login_attempts", 0),
                created_at=u.get("created_at"),
                updated_at=u.get("updated_at"),
                created_by=u.get("created_by"),
                roles=role_codes,
                permissions=[]  # 列表不需要返回权限详情
            ))

        return result, total
