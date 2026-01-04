"""认证服务 (MongoDB 版本)"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from src.utils.logger import get_logger
from src.infrastructure.auth import JWTHandler, PasswordHandler, TokenData
from src.infrastructure.persistence.auth.mongodb import MongoUserRepository
from src.core.domain.entities.auth import User, TokenResponse

logger = get_logger(__name__)


class AuthException(Exception):
    """认证异常"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthService:
    """认证服务 (MongoDB 版本)"""

    # 最大登录尝试次数
    MAX_LOGIN_ATTEMPTS = 5
    # 锁定时间（分钟）
    LOCKOUT_MINUTES = 30

    def __init__(self):
        """初始化认证服务（无需 session 参数）"""
        self.user_repo = MongoUserRepository()
        self.jwt_handler = JWTHandler()
        self.password_handler = PasswordHandler()

    async def login(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """
        用户登录

        Args:
            username: 用户名
            password: 密码
            ip_address: IP地址
            user_agent: 用户代理

        Returns:
            TokenResponse 包含 token 和用户信息

        Raises:
            AuthException: 认证失败
        """
        # 获取用户
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self._record_login_attempt(None, ip_address, user_agent, "failed", "用户不存在")
            raise AuthException("AUTH_001", "用户名或密码错误")

        user_id = user["_id"]

        # 检查账户是否被锁定
        if user.get("is_locked"):
            await self._record_login_attempt(user_id, ip_address, user_agent, "locked", "账户已锁定")
            raise AuthException("AUTH_002", f"账户已锁定: {user.get('lock_reason', '')}")

        # 检查账户是否激活
        if not user.get("is_active"):
            await self._record_login_attempt(user_id, ip_address, user_agent, "failed", "账户已禁用")
            raise AuthException("AUTH_006", "账户已禁用")

        # 验证密码
        if not self.password_handler.verify_password(password, user.get("password_hash", "")):
            # 增加登录尝试次数
            attempts = await self.user_repo.increment_login_attempts(user_id)

            # 检查是否需要锁定
            if attempts >= self.MAX_LOGIN_ATTEMPTS:
                await self.user_repo.lock_user(
                    user_id,
                    f"密码错误超过{self.MAX_LOGIN_ATTEMPTS}次，账户已锁定"
                )
                await self._record_login_attempt(user_id, ip_address, user_agent, "locked", "密码错误次数过多")
                raise AuthException("AUTH_002", "密码错误次数过多，账户已锁定")

            await self._record_login_attempt(user_id, ip_address, user_agent, "failed", "密码错误")
            raise AuthException("AUTH_001", "用户名或密码错误")

        # 登录成功
        await self.user_repo.reset_login_attempts(user_id)
        await self.user_repo.update_last_login(user_id)
        await self._record_login_attempt(user_id, ip_address, user_agent, "success", None)

        # 获取用户角色和权限
        user_data = await self.user_repo.get_user_with_permissions(user_id)
        if not user_data:
            raise AuthException("AUTH_001", "用户数据异常")

        user_doc, role_codes, permission_codes = user_data

        # 生成 Token
        access_token = self.jwt_handler.create_access_token(
            user_id=user_id,
            username=user_doc["username"],
            roles=role_codes,
            permissions=permission_codes
        )

        refresh_token = self.jwt_handler.create_refresh_token(
            user_id=user_id,
            username=user_doc["username"]
        )

        # 构建响应
        user_response = User(
            id=user_id,
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

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.jwt_handler.get_expires_in(access_token),
            user=user_response
        )

    async def logout(self, token: str) -> None:
        """
        用户登出（将 Token 加入黑名单）

        Args:
            token: 访问令牌
        """
        # 简单实现：这里可以扩展为将 token 加入 Redis 黑名单
        token_data = self.jwt_handler.verify_token(token)
        if token_data:
            logger.info(f"用户 {token_data.username} 已登出")

    async def refresh_token(self, refresh_token: str) -> Tuple[str, int]:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            Tuple[str, int]: (新访问令牌, 过期时间秒数)

        Raises:
            AuthException: 令牌无效或已过期
        """
        token_data = self.jwt_handler.verify_token(refresh_token)

        if not token_data:
            raise AuthException("AUTH_004", "令牌无效")

        if token_data.token_type != "refresh":
            raise AuthException("AUTH_004", "令牌类型错误")

        # 获取用户最新信息
        user_data = await self.user_repo.get_user_with_permissions(token_data.user_id)
        if not user_data:
            raise AuthException("AUTH_004", "用户不存在")

        user_doc, role_codes, permission_codes = user_data

        if not user_doc.get("is_active"):
            raise AuthException("AUTH_006", "账户已禁用")

        if user_doc.get("is_locked"):
            raise AuthException("AUTH_002", "账户已锁定")

        # 生成新的访问令牌
        new_access_token = self.jwt_handler.create_access_token(
            user_id=user_doc["_id"],
            username=user_doc["username"],
            roles=role_codes,
            permissions=permission_codes
        )

        return new_access_token, self.jwt_handler.get_expires_in(new_access_token)

    async def verify_token(self, token: str) -> Optional[TokenData]:
        """
        验证访问令牌

        Args:
            token: 访问令牌

        Returns:
            TokenData 或 None
        """
        return self.jwt_handler.verify_token(token)

    async def get_current_user(self, token: str) -> Optional[User]:
        """
        获取当前用户信息

        Args:
            token: 访问令牌

        Returns:
            User 或 None
        """
        token_data = self.jwt_handler.verify_token(token)
        if not token_data:
            return None

        user_data = await self.user_repo.get_user_with_permissions(token_data.user_id)
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

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改密码

        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            AuthException: 旧密码错误
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthException("AUTH_001", "用户不存在")

        if not self.password_handler.verify_password(old_password, user.get("password_hash", "")):
            raise AuthException("AUTH_001", "旧密码错误")

        new_hash = self.password_handler.hash_password(new_password)
        await self.user_repo.update(user_id, password_hash=new_hash)

        return True

    async def reset_password(self, user_id: str, new_password: str, operator_id: str) -> bool:
        """
        重置密码（管理员操作）

        Args:
            user_id: 用户ID
            new_password: 新密码
            operator_id: 操作人ID

        Returns:
            是否成功
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthException("AUTH_001", "用户不存在")

        new_hash = self.password_handler.hash_password(new_password)
        await self.user_repo.update(user_id, password_hash=new_hash)

        logger.info(f"管理员 {operator_id} 重置了用户 {user_id} 的密码")
        return True

    async def _record_login_attempt(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        status: str,
        fail_reason: Optional[str]
    ) -> None:
        """记录登录尝试"""
        if user_id:
            await self.user_repo.record_login_history(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                fail_reason=fail_reason
            )
