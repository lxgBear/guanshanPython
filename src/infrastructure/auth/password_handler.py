"""密码处理器"""

from passlib.context import CryptContext


class PasswordHandler:
    """密码哈希和验证处理器"""

    def __init__(self):
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12,
            bcrypt__truncate_error=False  # 兼容 Python 3.13 + bcrypt 4.x
        )

    def hash_password(self, password: str) -> str:
        """
        对密码进行哈希处理

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        验证密码

        Args:
            plain_password: 明文密码
            hashed_password: 哈希后的密码

        Returns:
            验证结果
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        检查密码是否需要重新哈希（算法升级时）

        Args:
            hashed_password: 哈希后的密码

        Returns:
            是否需要重新哈希
        """
        return self.pwd_context.needs_update(hashed_password)


# 单例实例
password_handler = PasswordHandler()
