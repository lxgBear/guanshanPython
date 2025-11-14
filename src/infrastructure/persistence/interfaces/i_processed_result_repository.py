"""
处理结果 Repository 接口

定义 AI 处理结果数据访问的抽象接口。

Version: v3.0.0 (模块化架构)
"""

from abc import abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IPaginatableRepository,
    IBulkOperationRepository
)


class IProcessedResultRepository(
    IBasicRepository[ProcessedResult],
    IQueryableRepository[ProcessedResult],
    IPaginatableRepository[ProcessedResult],
    IBulkOperationRepository[ProcessedResult]
):
    """
    处理结果 Repository 接口

    管理 AI 增强处理后的数据访问。
    处理结果是主要的前端查询数据源，包含翻译、摘要、分类等 AI 增强信息。

    Inherits:
        IBasicRepository[ProcessedResult]: 基础 CRUD 操作
        IQueryableRepository[ProcessedResult]: 条件查询功能
        IPaginatableRepository[ProcessedResult]: 分页查询功能
        IBulkOperationRepository[ProcessedResult]: 批量操作功能
    """

    @abstractmethod
    async def find_by_task_id(
        self,
        task_id: str,
        status: Optional[ProcessedStatus] = None,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """
        根据任务ID查询处理结果

        Args:
            task_id: 搜索任务ID
            status: 可选的状态过滤
            limit: 可选的数量限制

        Returns:
            List[ProcessedResult]: 处理结果列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_raw_result_id(
        self,
        raw_result_id: str
    ) -> Optional[ProcessedResult]:
        """
        根据原始结果ID查询处理结果

        Args:
            raw_result_id: 原始搜索结果ID

        Returns:
            Optional[ProcessedResult]: 处理结果，如果不存在则返回 None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_status(
        self,
        status: ProcessedStatus,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """
        根据状态查询处理结果

        Args:
            status: 处理状态枚举
            limit: 可选的数量限制

        Returns:
            List[ProcessedResult]: 处理结果列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_pending_results(
        self,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """
        查询待处理的结果

        Args:
            limit: 可选的数量限制

        Returns:
            List[ProcessedResult]: 待处理结果列表（status=PENDING）

        Raises:
            RepositoryException: 查询失败时抛出

        Note:
            用于 AI 处理服务拉取待处理任务
        """
        pass

    @abstractmethod
    async def update_processing_status(
        self,
        result_id: str,
        status: ProcessedStatus,
        **kwargs
    ) -> bool:
        """
        更新处理状态

        Args:
            result_id: 处理结果ID
            status: 新的处理状态
            **kwargs: 其他可选字段
                - processing_error: 错误信息
                - retry_count: 重试次数
                - processed_at: 处理完成时间

        Returns:
            bool: 更新是否成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        pass

    @abstractmethod
    async def save_ai_result(
        self,
        result_id: str,
        ai_data: Dict[str, Any]
    ) -> bool:
        """
        保存 AI 处理结果

        Args:
            result_id: 处理结果ID
            ai_data: AI 处理的数据字典，包含：
                - translated_title: 翻译后标题
                - translated_content: 翻译后内容
                - summary: 摘要
                - key_points: 关键要点
                - sentiment: 情感分析
                - categories: 分类标签
                - ai_model: 使用的模型
                - ai_processing_time_ms: 处理时间
                - ai_confidence_score: 置信度分数

        Returns:
            bool: 保存是否成功

        Raises:
            RepositoryException: 保存失败时抛出
        """
        pass

    @abstractmethod
    async def update_user_action(
        self,
        result_id: str,
        status: Optional[ProcessedStatus] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """
        更新用户操作

        Args:
            result_id: 处理结果ID
            status: 可选的状态更新（如 ARCHIVED, DELETED）
            user_rating: 可选的用户评分（1-5）
            user_notes: 可选的用户备注

        Returns:
            bool: 更新是否成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        pass

    @abstractmethod
    async def get_processing_statistics(
        self,
        task_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取处理统计信息

        Args:
            task_id: 可选的任务ID过滤
            start_date: 可选的开始日期
            end_date: 可选的结束日期

        Returns:
            Dict[str, Any]: 统计信息字典，包含：
                - total: 总数
                - pending: 待处理数
                - processing: 处理中数
                - completed: 已完成数
                - failed: 失败数
                - archived: 已归档数
                - deleted: 已删除数
                - avg_processing_time_ms: 平均处理时间
                - success_rate: 成功率

        Raises:
            RepositoryException: 统计失败时抛出
        """
        pass

    @abstractmethod
    async def find_with_pagination_and_filters(
        self,
        task_id: Optional[str] = None,
        status: Optional[ProcessedStatus] = None,
        categories: Optional[List[str]] = None,
        min_rating: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[ProcessedResult], int]:
        """
        分页查询处理结果（带多维度过滤）

        Args:
            task_id: 可选的任务ID过滤
            status: 可选的状态过滤
            categories: 可选的分类过滤
            min_rating: 可选的最低评分过滤
            start_date: 可选的开始日期
            end_date: 可选的结束日期
            page: 页码（从 1 开始）
            page_size: 每页大小
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            Tuple[List[ProcessedResult], int]: (结果列表, 总数量)

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass
