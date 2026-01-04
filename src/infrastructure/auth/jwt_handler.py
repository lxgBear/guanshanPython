"""JWT Token 处理器"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid

from jose import jwt, JWTError
from pydantic import BaseModel

from src.config import get_settings


class TokenData(BaseModel):
    """Token 数据模型"""
    user_id: str  # MongoDB 使用字符串 ID
    username: str
    roles: List[str] = []
    permissions: List[str] = []
    token_type: str = "access"  # access or refresh
    jti: str  # JWT ID (用于撤销)
    exp: datetime
    iat: datetime


class JWTHandler:
    """JWT Token 处理器"""

    def __init__(self):
        settings = get_settings()
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_hours = settings.JWT_EXPIRATION_HOURS
        self.refresh_token_expire_days = 7

    def create_access_token(
        self,
        user_id: str,
        username: str,
        roles: List[str],
        permissions: List[str],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建访问令牌

        Args:
            user_id: 用户ID
            username: 用户名
            roles: 角色列表
            permissions: 权限列表
            expires_delta: 过期时间增量

        Returns:
            JWT token 字符串
        """
        now = datetime.now(timezone.utc)

        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(hours=self.access_token_expire_hours)

        payload = {
            "sub": str(user_id),
            "username": username,
            "roles": roles,
            "permissions": permissions,
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expire,
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        username: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建刷新令牌

        Args:
            user_id: 用户ID
            username: 用户名
            expires_delta: 过期时间增量

        Returns:
            JWT refresh token 字符串
        """
        now = datetime.now(timezone.utc)

        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "sub": str(user_id),
            "username": username,
            "token_type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expire,
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[TokenData]:
        """
        验证并解析 Token

        Args:
            token: JWT token 字符串

        Returns:
            TokenData 对象，验证失败返回 None
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            user_id = payload.get("sub")  # 保持字符串类型
            username = payload.get("username")
            token_type = payload.get("token_type", "access")
            jti = payload.get("jti", "")

            if not user_id or not username:
                return None

            return TokenData(
                user_id=user_id,
                username=username,
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                token_type=token_type,
                jti=jti,
                exp=datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc),
                iat=datetime.fromtimestamp(payload.get("iat"), tz=timezone.utc),
            )

        except JWTError:
            return None
        except (ValueError, TypeError):
            return None

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        解码 Token (不验证)

        Args:
            token: JWT token 字符串

        Returns:
            解码后的 payload 字典
        """
        try:
            return jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}
            )
        except JWTError:
            return None

    def get_token_jti(self, token: str) -> Optional[str]:
        """
        获取 Token 的 JTI (用于撤销)

        Args:
            token: JWT token 字符串

        Returns:
            JTI 字符串
        """
        payload = self.decode_token(token)
        return payload.get("jti") if payload else None

    def get_expires_in(self, token: str) -> int:
        """
        获取 Token 剩余有效时间（秒）

        Args:
            token: JWT token 字符串

        Returns:
            剩余秒数
        """
        payload = self.decode_token(token)
        if not payload:
            return 0

        exp = payload.get("exp")
        if not exp:
            return 0

        now = datetime.now(timezone.utc).timestamp()
        return max(0, int(exp - now))


# 单例实例
jwt_handler = JWTHandler()
