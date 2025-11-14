"""
搜索结果 Repository 接口

定义搜索结果（原始数据）数据访问的抽象接口。

Version: v3.0.0 (模块化架构)
"""

from abc import abstractmethod
from typing import List, Optional, Tuple

from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IBulkOperationRepository
)


class IResultRepository(
    IBasicRepository[SearchResult],
    IQueryableRepository[SearchResult],
    IBulkOperationRepository[SearchResult]
):
    """
    搜索结果 Repository 接口

    管理原始搜索结果的数据访问。
    搜索结果是不可变的原始数据，主要用于存档和溯源。

    Inherits:
        IBasicRepository[SearchResult]: 基础 CRUD 操作
        IQueryableRepository[SearchResult]: 条件查询功能
        IBulkOperationRepository[SearchResult]: 批量操作功能
    """

    @abstractmethod
    async def find_by_task_id(
        self,
        task_id: str,
        limit: Optional[int] = None
    ) -> List[SearchResult]:
        """
        根据任务ID查询搜索结果

        Args:
            task_id: 搜索任务ID
            limit: 可选的数量限制

        Returns:
            List[SearchResult]: 搜索结果列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_url(self, url: str) -> Optional[SearchResult]:
        """
        根据 URL 查询搜索结果（去重检查）

        Args:
            url: 搜索结果URL

        Returns:
            Optional[SearchResult]: 如果存在则返回结果，否则返回 None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_status(
        self,
        status: ResultStatus,
        limit: Optional[int] = None
    ) -> List[SearchResult]:
        """
        根据状态查询搜索结果

        Args:
            status: 结果状态枚举
            limit: 可选的数量限制

        Returns:
            List[SearchResult]: 搜索结果列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def save_batch(self, batch: SearchResultBatch) -> List[str]:
        """
        批量保存搜索结果批次

        Args:
            batch: 搜索结果批次对象

        Returns:
            List[str]: 保存成功的结果ID列表

        Raises:
            RepositoryException: 保存失败时抛出

        Note:
            这是一个便捷方法，内部调用 bulk_create
        """
        pass

    @abstractmethod
    async def get_task_results_count(self, task_id: str) -> int:
        """
        统计任务的搜索结果数量

        Args:
            task_id: 搜索任务ID

        Returns:
            int: 结果数量

        Raises:
            RepositoryException: 统计失败时抛出
        """
        pass

    @abstractmethod
    async def delete_by_task_id(self, task_id: str) -> int:
        """
        删除任务的所有搜索结果

        Args:
            task_id: 搜索任务ID

        Returns:
            int: 删除的数量

        Raises:
            RepositoryException: 删除失败时抛出

        Warning:
            此操作不可撤销，请谨慎使用
        """
        pass
