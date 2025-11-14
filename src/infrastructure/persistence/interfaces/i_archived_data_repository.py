"""存档数据仓储接口

Version: v3.0.0 (模块化架构)

存档数据仓储提供数据源存档数据的持久化操作，包括：
- 创建存档记录（confirm时自动触发）
- 查询存档数据（按数据源、原始数据ID）
- 统计存档数量和内容大小
- 删除存档数据（级联删除）
- MongoDB事务支持（用于事务一致性）
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorClientSession

from src.core.domain.entities.archived_data import ArchivedData
from .i_repository import IBasicRepository


class IArchivedDataRepository(IBasicRepository[ArchivedData]):
    """存档数据仓储接口

    职责：
    - 存档记录的CRUD操作
    - 按数据源查询和分页
    - 防重复存档（原始数据ID查询）
    - 统计信息（按类型分组、内容大小）
    - 级联删除（删除数据源时清理存档）
    - 事务支持（跨集合同步）

    注意：
    - 支持MongoDB事务会话参数
    - create() 返回 ArchivedData 实体（与基础接口不同）
    - 提供分页查询和统计分析能力
    """

    @abstractmethod
    async def create(
        self,
        entity: ArchivedData,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> ArchivedData:
        """创建存档记录

        Args:
            entity: 存档数据实体
            session: MongoDB事务会话（通常必须提供以保证事务一致性）

        Returns:
            创建的存档数据实体

        注意：
        - 返回完整实体而非ID（历史原因）
        - 支持事务会话
        - 通常在数据源confirm操作时由Service层事务调用
        """
        pass

    @abstractmethod
    async def find_by_id(
        self,
        archived_data_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> Optional[ArchivedData]:
        """根据ID查询存档数据

        Args:
            archived_data_id: 存档数据ID
            session: MongoDB事务会话（可选）

        Returns:
            存档数据实体或None
        """
        pass

    @abstractmethod
    async def find_by_data_source(
        self,
        data_source_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[ArchivedData]:
        """按数据源查询存档数据（分页）

        Args:
            data_source_id: 数据源ID
            limit: 每页数量
            skip: 跳过数量

        Returns:
            存档数据实体列表

        排序：
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def count_by_data_source(
        self,
        data_source_id: str
    ) -> int:
        """统计数据源的存档数量

        Args:
            data_source_id: 数据源ID

        Returns:
            存档记录数量
        """
        pass

    @abstractmethod
    async def find_by_original_data_id(
        self,
        original_data_id: str,
        data_type: str
    ) -> Optional[ArchivedData]:
        """根据原始数据ID查询存档（防重复存档）

        Args:
            original_data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）

        Returns:
            存档数据实体或None

        业务逻辑：
        - 用于防止重复存档同一条数据
        - 通过 original_data_id + data_type 唯一标识
        """
        pass

    @abstractmethod
    async def delete_by_data_source(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> int:
        """删除数据源的所有存档记录（级联删除）

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            删除的记录数量

        业务逻辑：
        - 通常在删除数据源时由Service层事务调用
        - 支持事务以保证级联删除的原子性
        """
        pass

    @abstractmethod
    async def get_statistics(
        self,
        data_source_id: str
    ) -> Dict[str, Any]:
        """获取数据源存档统计信息

        Args:
            data_source_id: 数据源ID

        Returns:
            统计信息字典，包含：
            - data_source_id: 数据源ID
            - total_count: 总记录数
            - scheduled_count: scheduled类型数量
            - instant_count: instant类型数量
            - total_content_size: 总内容大小（字符数）
            - by_type: 按类型分组统计

        业务逻辑：
        - 使用MongoDB聚合管道统计
        - 计算内容大小（字符数）
        - 按数据类型分组
        """
        pass

    @abstractmethod
    async def find_with_pagination(
        self,
        data_source_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ArchivedData], int]:
        """分页查询存档数据（含总数）

        Args:
            data_source_id: 数据源ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            (存档数据列表, 总记录数) 元组

        业务逻辑：
        - 并行执行查询和计数
        - 按创建时间倒序排列
        """
        pass
