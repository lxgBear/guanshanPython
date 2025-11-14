"""
搜索任务 Repository 接口

定义搜索任务数据访问的抽象接口。

Version: v3.0.0 (模块化架构)
"""

from abc import abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from src.core.domain.entities.search_task import SearchTask, TaskStatus
from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IPaginatableRepository
)


class ITaskRepository(
    IBasicRepository[SearchTask],
    IQueryableRepository[SearchTask],
    IPaginatableRepository[SearchTask]
):
    """
    搜索任务 Repository 接口

    继承基础接口并添加任务特定的查询方法。

    Inherits:
        IBasicRepository[SearchTask]: 基础 CRUD 操作
        IQueryableRepository[SearchTask]: 条件查询功能
        IPaginatableRepository[SearchTask]: 分页查询功能
    """

    @abstractmethod
    async def find_active_tasks(self) -> List[SearchTask]:
        """
        获取所有活跃的任务

        Returns:
            List[SearchTask]: 活跃任务列表（is_active=True）

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_schedule(self, schedule_interval: str) -> List[SearchTask]:
        """
        根据调度间隔查询任务

        Args:
            schedule_interval: 调度间隔值（如 "HOURLY_1", "DAILY"）

        Returns:
            List[SearchTask]: 符合条件的任务列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_status(self, status: TaskStatus) -> List[SearchTask]:
        """
        根据状态查询任务

        Args:
            status: 任务状态枚举

        Returns:
            List[SearchTask]: 符合条件的任务列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_creator(self, created_by: str) -> List[SearchTask]:
        """
        根据创建者查询任务

        Args:
            created_by: 创建者ID或用户名

        Returns:
            List[SearchTask]: 该用户创建的任务列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_tasks_due_for_execution(
        self,
        current_time: datetime
    ) -> List[SearchTask]:
        """
        查询到期需要执行的任务

        Args:
            current_time: 当前时间

        Returns:
            List[SearchTask]: 到期任务列表（next_run_time <= current_time）

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def update_execution_stats(
        self,
        task_id: str,
        success: bool,
        result_count: int,
        credits_used: int,
        next_run_time: Optional[datetime] = None
    ) -> bool:
        """
        更新任务执行统计信息

        Args:
            task_id: 任务ID
            success: 是否执行成功
            result_count: 本次执行返回的结果数
            credits_used: 本次执行消耗的积分
            next_run_time: 下次运行时间（可选）

        Returns:
            bool: 更新是否成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        pass

    @abstractmethod
    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None
    ) -> Tuple[List[SearchTask], int]:
        """
        分页查询任务列表（带过滤）

        Args:
            page: 页码（从 1 开始）
            page_size: 每页大小
            status: 可选的状态过滤
            is_active: 可选的启用状态过滤
            query: 可选的关键词模糊查询（匹配name或description）

        Returns:
            Tuple[List[SearchTask], int]: (任务列表, 总数量)

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass
