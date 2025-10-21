"""
数据库迁移基类

所有迁移脚本必须继承此类并实现 upgrade() 和 downgrade() 方法。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseMigration(ABC):
    """数据库迁移基类"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.executed_at: Optional[datetime] = None

    @property
    @abstractmethod
    def version(self) -> str:
        """迁移版本号（例如: "001", "002"）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """迁移描述"""
        pass

    @abstractmethod
    async def upgrade(self) -> dict:
        """
        执行迁移

        Returns:
            dict: 迁移结果统计
                - modified_count: 修改的文档数
                - created_count: 创建的文档数
                - details: 详细信息
        """
        pass

    @abstractmethod
    async def downgrade(self) -> dict:
        """
        回滚迁移

        Returns:
            dict: 回滚结果统计
        """
        pass

    async def validate(self) -> bool:
        """
        验证迁移结果

        Returns:
            bool: 迁移是否成功
        """
        return True

    def get_info(self) -> dict:
        """获取迁移信息"""
        return {
            "version": self.version,
            "description": self.description,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }
