"""即时搜索AI处理结果仓储接口

Version: v3.0.0 (模块化架构)

v2.1.0 即时+智能搜索统一架构：
- 管理 instant_processed_results 集合的所有数据访问操作
- 支持 search_type 字段区分即时搜索和智能搜索
- 支持状态管理和用户操作
- 提供AI服务所需的查询和更新接口

AI处理结果仓储提供即时搜索AI处理结果的持久化操作，包括：
- 创建待处理结果和批量创建
- AI结果保存和状态更新
- 按任务、状态、类型查询
- 用户操作（留存、删除、评分、备注）
- 统计分析和失败重试
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.instant_processed_result import (
    InstantProcessedResult,
    InstantProcessedStatus
)
from .i_repository import IBasicRepository


class IInstantProcessedResultRepository(IBasicRepository[InstantProcessedResult]):
    """即时搜索AI处理结果仓储接口

    职责：
    - AI处理结果的生命周期管理
    - 状态流转（pending → processing → completed/failed）
    - 按任务和类型查询（支持即时和智能搜索）
    - 用户操作管理（留存、删除、评分、备注）
    - 统计分析和失败重试
    """

    # ==================== 创建和初始化 ====================

    @abstractmethod
    async def create_pending_result(
        self,
        raw_result_id: str,
        task_id: str,
        search_type: str = "instant"
    ) -> InstantProcessedResult:
        """创建待处理的结果记录

        Args:
            raw_result_id: 原始结果ID（来自instant_search_results）
            task_id: 任务ID
            search_type: 搜索类型（instant | smart）v2.1.0

        Returns:
            创建的InstantProcessedResult实体

        注意：
        - 初始状态为PENDING
        - 自动生成ID和时间戳
        """
        pass

    @abstractmethod
    async def bulk_create_pending_results(
        self,
        raw_result_ids: List[str],
        task_id: str,
        search_type: str = "instant"
    ) -> List[InstantProcessedResult]:
        """批量创建待处理结果

        Args:
            raw_result_ids: 原始结果ID列表
            task_id: 任务ID
            search_type: 搜索类型（instant | smart）v2.1.0

        Returns:
            创建的InstantProcessedResult列表

        业务逻辑：
        - 使用insert_many批量插入
        - 提高大批量数据的创建性能
        """
        pass

    # ==================== 状态管理 ====================

    @abstractmethod
    async def update_processing_status(
        self,
        result_id: str,
        status: InstantProcessedStatus,
        **kwargs
    ) -> bool:
        """更新处理状态

        Args:
            result_id: 结果ID
            status: 新状态
            **kwargs: 其他更新字段（如 processing_error, ai_model 等）

        Returns:
            是否更新成功

        业务逻辑：
        - 自动更新updated_at字段
        - COMPLETED状态自动设置processed_at
        """
        pass

    @abstractmethod
    async def save_ai_result(
        self,
        result_id: str,
        translated_title: Optional[str] = None,
        translated_content: Optional[str] = None,
        summary: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        sentiment: Optional[str] = None,
        categories: Optional[List[str]] = None,
        ai_model: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        ai_confidence_score: Optional[float] = None
    ) -> bool:
        """保存AI处理结果

        Args:
            result_id: 结果ID
            translated_title: 翻译后的标题
            translated_content: 翻译后的内容
            summary: AI摘要
            key_points: 关键点列表
            sentiment: 情感分析
            categories: 分类标签
            ai_model: AI模型名称
            processing_time_ms: 处理耗时
            ai_confidence_score: 置信度分数

        Returns:
            是否保存成功

        业务逻辑：
        - 只更新非None的字段
        - 自动设置状态为COMPLETED
        - 自动设置processed_at和updated_at
        """
        pass

    # ==================== 查询方法 ====================

    @abstractmethod
    async def get_by_id(self, result_id: str) -> Optional[InstantProcessedResult]:
        """根据ID获取处理结果

        Args:
            result_id: 结果ID

        Returns:
            InstantProcessedResult实体或None
        """
        pass

    @abstractmethod
    async def get_by_raw_result_id(self, raw_result_id: str) -> Optional[InstantProcessedResult]:
        """根据原始结果ID获取处理结果

        Args:
            raw_result_id: 原始结果ID

        Returns:
            InstantProcessedResult实体或None

        业务逻辑：
        - 用于检查是否已处理过某个原始结果
        """
        pass

    @abstractmethod
    async def get_by_task(
        self,
        task_id: str,
        status: Optional[InstantProcessedStatus] = None,
        search_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InstantProcessedResult], int]:
        """获取任务的处理结果（支持状态筛选和分页）

        Args:
            task_id: 任务ID
            status: 状态筛选（可选）
            search_type: 搜索类型筛选（instant | smart，可选）v2.1.0
            page: 页码
            page_size: 每页数量

        Returns:
            (结果列表, 总数)

        排序：
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def get_by_task_and_type(
        self,
        task_id: str,
        search_type: str,
        status: Optional[InstantProcessedStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InstantProcessedResult], int]:
        """根据任务ID和搜索类型获取处理结果（v2.1.0 统一架构专用）

        Args:
            task_id: 任务ID
            search_type: 搜索类型（instant | smart）
            status: 状态筛选（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            (结果列表, 总数)
        """
        pass

    # ==================== 用户操作 ====================

    @abstractmethod
    async def update_user_action(
        self,
        result_id: str,
        status: Optional[InstantProcessedStatus] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """更新用户操作（留存、删除、评分、备注）

        Args:
            result_id: 结果ID
            status: 新状态（ARCHIVED或DELETED）
            user_rating: 用户评分（1-5）
            user_notes: 用户备注

        Returns:
            是否更新成功

        验证：
        - user_rating必须在1-5之间

        注意：
        - 自动更新updated_at字段
        """
        pass

    # ==================== 统计和分析 ====================

    @abstractmethod
    async def get_status_statistics(
        self,
        task_id: str,
        search_type: Optional[str] = None
    ) -> Dict[str, int]:
        """获取任务的状态统计

        Args:
            task_id: 任务ID
            search_type: 搜索类型筛选（instant | smart，可选）v2.1.0

        Returns:
            状态计数字典 {"pending": 10, "completed": 5, ...}

        业务逻辑：
        - 使用MongoDB聚合管道按状态分组
        - 返回所有可能状态的计数（未出现的为0）
        """
        pass

    @abstractmethod
    async def get_failed_results(self, max_retry: int = 3) -> List[InstantProcessedResult]:
        """获取失败的结果（用于重试）

        Args:
            max_retry: 最大重试次数

        Returns:
            失败的结果列表（retry_count < max_retry）

        排序：
        - 按更新时间升序（优先重试旧的）

        业务逻辑：
        - 用于AI处理失败重试机制
        """
        pass

    # ==================== 批量操作 ====================

    @abstractmethod
    async def delete_by_task(self, task_id: str) -> int:
        """删除任务的所有处理结果

        Args:
            task_id: 任务ID

        Returns:
            删除的记录数

        业务逻辑：
        - 级联删除，通常在删除任务时调用
        """
        pass
