"""数据源仓储接口

Version: v3.0.0 (模块化架构)

数据源仓储提供数据源的持久化操作，包括：
- 基础CRUD操作
- 多维度过滤查询（状态、类型、分类、时间范围）
- 原始数据引用管理
- 统计信息维护
- MongoDB事务支持（用于状态同步）
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClientSession

from src.core.domain.entities.data_source import DataSource, RawDataReference
from .i_repository import IBasicRepository


class IDataSourceRepository(IBasicRepository[DataSource]):
    """数据源仓储接口

    职责：
    - 数据源的CRUD操作
    - 多维度过滤查询（状态、类型、分类、创建者、时间范围）
    - 原始数据引用管理（添加、移除）
    - 统计信息维护
    - 事务支持（跨集合同步）

    注意：
    - 支持MongoDB事务会话参数
    - create() 返回 DataSource 实体（与基础接口不同）
    - 提供丰富的过滤和分类查询能力
    """

    @abstractmethod
    async def create(
        self,
        entity: DataSource,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> DataSource:
        """创建数据源

        Args:
            entity: 数据源实体
            session: MongoDB事务会话（可选）

        Returns:
            创建的数据源实体

        注意：
        - 返回完整实体而非ID（历史原因）
        - 支持事务会话
        """
        pass

    @abstractmethod
    async def find_by_id(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> Optional[DataSource]:
        """根据ID查询数据源

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            数据源实体或None
        """
        pass

    @abstractmethod
    async def find_all(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[DataSource]:
        """查询所有数据源（支持多维度过滤和分页）

        Args:
            created_by: 创建者过滤
            status: 状态过滤（draft或confirmed）
            source_type: 数据源类型过滤（scheduled, instant, mixed）
            start_date: 开始日期过滤（创建时间）
            end_date: 结束日期过滤（创建时间）
            primary_category: 第一级分类过滤
            secondary_category: 第二级分类过滤
            tertiary_category: 第三级分类过滤
            limit: 每页数量
            skip: 跳过数量

        Returns:
            数据源实体列表

        排序：
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def count(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None
    ) -> int:
        """统计数据源数量（支持多维度过滤）

        Args:
            created_by: 创建者过滤
            status: 状态过滤
            source_type: 数据源类型过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            primary_category: 第一级分类过滤
            secondary_category: 第二级分类过滤
            tertiary_category: 第三级分类过滤

        Returns:
            数据源数量
        """
        pass

    @abstractmethod
    async def update(
        self,
        data_source_id: str,
        update_data: Dict[str, Any],
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新数据源

        Args:
            data_source_id: 数据源ID
            update_data: 更新数据字典
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功

        注意：
        - 自动更新 updated_at 字段
        """
        pass

    @abstractmethod
    async def delete(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """删除数据源

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    async def add_raw_data_ref(
        self,
        data_source_id: str,
        raw_data_ref: RawDataReference,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """添加原始数据引用

        Args:
            data_source_id: 数据源ID
            raw_data_ref: 原始数据引用
            session: MongoDB事务会话（可选）

        Returns:
            是否添加成功

        业务逻辑：
        - 使用 $push 添加到数组
        - 自动更新 updated_at
        """
        pass

    @abstractmethod
    async def remove_raw_data_ref(
        self,
        data_source_id: str,
        data_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """移除原始数据引用

        Args:
            data_source_id: 数据源ID
            data_id: 原始数据ID
            session: MongoDB事务会话（可选）

        Returns:
            是否移除成功

        业务逻辑：
        - 使用 $pull 从数组中移除
        - 自动更新 updated_at
        """
        pass

    @abstractmethod
    async def update_statistics(
        self,
        data_source_id: str,
        total_count: int,
        scheduled_count: int,
        instant_count: int,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新统计信息

        Args:
            data_source_id: 数据源ID
            total_count: 总数
            scheduled_count: 定时任务数据数量
            instant_count: 即时搜索数据数量
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功
        """
        pass

    @abstractmethod
    async def find_by_raw_data_id(
        self,
        data_id: str,
        data_type: str
    ) -> List[DataSource]:
        """查找包含指定原始数据的所有数据源

        Args:
            data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）

        Returns:
            数据源实体列表

        业务逻辑：
        - 使用 $elemMatch 查询数组元素
        - 用于反向查找数据源
        """
        pass
