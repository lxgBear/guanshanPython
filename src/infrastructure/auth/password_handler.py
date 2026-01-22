"""密码处理器

v4.9.1: 修复 bcrypt 5.0 + Python 3.13 兼容性问题
直接使用 bcrypt 库替代 passlib，避免 wrap bug 检测导致的错误
"""

import bcrypt


class PasswordHandler:
    """密码哈希和验证处理器"""

    def __init__(self):
        self.rounds = 12

    def hash_password(self, password: str) -> str:
        """
        对密码进行哈希处理

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        # bcrypt 要求密码为 bytes 类型
        password_bytes = password.encode('utf-8')
        # 生成 salt 并哈希
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        验证密码

        Args:
            plain_password: 明文密码
            hashed_password: 哈希后的密码

        Returns:
            验证结果
        """
        try:
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception:
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        检查密码是否需要重新哈希（算法升级时）

        Args:
            hashed_password: 哈希后的密码

        Returns:
            是否需要重新哈希
        """
        # bcrypt 哈希格式: $2b$rounds$salt+hash
        # 检查 rounds 是否与当前配置一致
        try:
            parts = hashed_password.split('$')
            if len(parts) >= 3:
                current_rounds = int(parts[2])
                return current_rounds != self.rounds
        except Exception:
            pass
        return True


# 单例实例
password_handler = PasswordHandler()
