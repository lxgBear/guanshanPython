"""智能搜索仓储接口层

Version: v3.0.0 (模块化架构)

定义智能搜索相关的仓储接口：
- ISmartSearchTaskRepository: 智能搜索任务管理
- ISmartSearchResultRepository: 智能搜索结果管理
- IQueryDecompositionCacheRepository: LLM查询分解缓存管理

设计原则：
1. Interface Segregation Principle (ISP): 接口职责单一明确
2. Dependency Inversion Principle (DIP): 依赖抽象而非实现
3. 缓存优化：LLM查询分解缓存降低API成本
4. 聚合查询：智能搜索结果支持多维度聚合分析
"""

from abc import abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from src.core.domain.entities.smart_search_task import SmartSearchTask
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.core.domain.entities.query_decomposition import QueryDecomposition

from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IPaginatableRepository
)


class ISmartSearchTaskRepository(
    IBasicRepository[SmartSearchTask],
    IPaginatableRepository[SmartSearchTask]
):
    """智能搜索任务仓储接口

    职责：
    - 管理智能搜索任务的生命周期（创建、查询、更新、删除）
    - 支持按状态、创建者筛选的分页查询
    - 维护任务的分解、确认、执行全流程

    智能搜索工作流：
    1. **分解阶段**: LLM分解原始查询为多个子查询
    2. **确认阶段**: 用户确认/修改子查询
    3. **执行阶段**: 并发执行子查询，收集结果
    4. **聚合阶段**: 聚合分析子查询结果

    注意：
    - create() 返回 task_id (str)，而非实体
    - update() 返回更新成功标志 (bool)
    """

    @abstractmethod
    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[SmartSearchTask], int]:
        """获取任务列表（分页 + 筛选）

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            status: 状态筛选（可选）
            created_by: 创建者筛选（可选）

        Returns:
            (tasks, total): 任务列表和总数

        业务逻辑：
        - 按创建时间倒序排序
        - 支持多条件组合筛选
        """
        pass


class ISmartSearchResultRepository:
    """智能搜索结果仓储接口

    职责：
    - 管理智能搜索结果的存储和查询（使用独立集合 smart_search_results）
    - 支持按子查询索引分组查询
    - 提供聚合优先级管理
    - 支持结果状态管理（v2.1.0）
    - 提供多维度统计分析

    智能搜索特定字段：
    - original_query: 原始查询
    - decomposed_query: 分解后的子查询
    - decomposition_reasoning: 分解理由
    - query_focus: 查询焦点
    - sub_query_index: 子查询索引
    - aggregation_priority: 聚合优先级
    - relevance_to_original: 对原始查询的相关性

    注意：
    - 与普通搜索结果分开存储（smart_search_results vs search_results）
    - 支持跨任务的原始查询检索
    """

    @abstractmethod
    async def save_results(
        self,
        results: List[SearchResult],
        task: SmartSearchTask,
        sub_query_index: int = 0
    ) -> None:
        """批量保存搜索结果（添加智能搜索特定字段）

        Args:
            results: 搜索结果列表
            task: 智能搜索任务
            sub_query_index: 子查询索引

        业务逻辑：
        - 自动填充智能搜索特定字段
        - 基于相关性分数计算聚合优先级
        """
        pass

    @abstractmethod
    async def get_results_by_task(
        self,
        task_id: str,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "aggregation_priority"
    ) -> Tuple[List[SearchResult], int]:
        """获取任务的所有搜索结果

        Args:
            task_id: 任务ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            sort_by: 排序字段 (aggregation_priority, relevance_score, created_at)

        Returns:
            (结果列表, 总数)

        排序规则：
        - aggregation_priority: 聚合优先级 DESC → 相关性 DESC → 创建时间 DESC
        - relevance_score: 相关性 DESC → 创建时间 DESC
        - created_at: 创建时间 DESC
        """
        pass

    @abstractmethod
    async def get_results_by_sub_query(
        self,
        task_id: str,
        sub_query_index: int,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """获取特定子查询的结果

        Args:
            task_id: 任务ID
            sub_query_index: 子查询索引
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)

        用途：
        - 查看单个子查询的搜索结果
        - 分析子查询质量
        """
        pass

    @abstractmethod
    async def get_top_results(
        self,
        task_id: str,
        limit: int = 10,
        min_relevance_score: float = 0.0
    ) -> List[SearchResult]:
        """获取任务的top结果（按聚合优先级和相关性）

        Args:
            task_id: 任务ID
            limit: 返回的最大记录数
            min_relevance_score: 最小相关性分数阈值

        Returns:
            结果列表

        排序规则：
        1. aggregation_priority DESC
        2. relevance_score DESC
        3. quality_score DESC

        用途：
        - 前端展示最佳结果
        - 聚合报告生成
        """
        pass

    @abstractmethod
    async def get_results_by_original_query(
        self,
        original_query: str,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """根据原始查询获取结果（跨任务查询）

        Args:
            original_query: 原始查询
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)

        用途：
        - 查找相同原始查询的历史结果
        - 跨任务结果分析
        """
        pass

    @abstractmethod
    async def update_aggregation_priority(
        self,
        result_id: str,
        priority: int
    ) -> bool:
        """更新结果的聚合优先级

        Args:
            result_id: 结果ID
            priority: 新的优先级

        Returns:
            是否更新成功

        用途：
        - 用户手动调整结果排序
        - 基于反馈优化聚合算法
        """
        pass

    @abstractmethod
    async def update_relevance_to_original(
        self,
        result_id: str,
        relevance: float
    ) -> bool:
        """更新结果对原始查询的相关性

        Args:
            result_id: 结果ID
            relevance: 相关性分数 (0.0-1.0)

        Returns:
            是否更新成功

        用途：
        - LLM重新评估相关性
        - 基于用户反馈调整
        """
        pass

    @abstractmethod
    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果

        Args:
            task_id: 任务ID

        Returns:
            删除的记录数
        """
        pass

    @abstractmethod
    async def count_results_by_task(self, task_id: str) -> int:
        """统计任务的结果数量

        Args:
            task_id: 任务ID

        Returns:
            结果数量
        """
        pass

    @abstractmethod
    async def get_statistics_by_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务的结果统计信息

        Args:
            task_id: 任务ID

        Returns:
            统计信息字典
            {
                "total_count": 100,
                "sub_query_statistics": [
                    {
                        "sub_query_index": 0,
                        "count": 30,
                        "avg_relevance_score": 0.85,
                        "avg_quality_score": 0.78,
                        "max_relevance_score": 0.95,
                        "min_relevance_score": 0.60
                    },
                    ...
                ]
            }

        用途：
        - 分析子查询质量
        - 生成聚合报告
        """
        pass

    # ==================== 状态管理方法 (v2.1.0新增) ====================

    @abstractmethod
    async def get_results_by_status(
        self,
        task_id: str,
        status: ResultStatus,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """按状态筛选搜索结果

        Args:
            task_id: 任务ID
            status: 结果状态
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        pass

    @abstractmethod
    async def count_by_status(self, task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            task_id: 任务ID

        Returns:
            状态计数字典 {"pending": 10, "archived": 5, ...}
        """
        pass

    @abstractmethod
    async def update_result_status(
        self,
        result_id: str,
        new_status: ResultStatus
    ) -> bool:
        """更新单个结果状态

        Args:
            result_id: 结果ID
            new_status: 新状态

        Returns:
            是否更新成功
        """
        pass

    @abstractmethod
    async def bulk_update_status(
        self,
        result_ids: List[str],
        new_status: ResultStatus
    ) -> int:
        """批量更新结果状态

        Args:
            result_ids: 结果ID列表
            new_status: 新状态

        Returns:
            更新的记录数
        """
        pass

    @abstractmethod
    async def get_status_distribution(self, task_id: str) -> Dict[str, Any]:
        """获取状态分布统计

        Args:
            task_id: 任务ID

        Returns:
            状态分布统计信息
            {
                "total": 100,
                "distribution": {
                    "pending": {"count": 50, "percentage": 50.0},
                    "archived": {"count": 30, "percentage": 30.0},
                    ...
                }
            }
        """
        pass


class IQueryDecompositionCacheRepository:
    """查询分解缓存仓储接口

    职责：
    - 缓存LLM分解结果，降低API调用成本
    - 管理缓存TTL（默认24小时）
    - 提供缓存统计和清理功能

    缓存策略：
    - 缓存键：MD5(query + search_context)
    - TTL：24小时自动过期
    - 命中统计：记录缓存使用次数和最后使用时间
    - Upsert操作：存在则更新，不存在则插入

    注意：
    - 缓存失败不应阻塞主流程
    - 所有方法应捕获异常并返回默认值
    """

    @abstractmethod
    async def get_cached_decomposition(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Optional[QueryDecomposition]:
        """获取缓存的分解结果

        Args:
            query: 原始查询
            context: 搜索上下文

        Returns:
            QueryDecomposition或None

        业务逻辑：
        - 计算缓存键：MD5(query + context)
        - 检查是否过期（expires_at > now）
        - 命中则更新hit_count和last_used_at
        - 未命中返回None
        """
        pass

    @abstractmethod
    async def save_decomposition(
        self,
        query: str,
        context: Dict[str, Any],
        decomposition: QueryDecomposition,
        ttl_hours: int = 24
    ) -> bool:
        """保存分解结果到缓存

        Args:
            query: 原始查询
            context: 搜索上下文
            decomposition: 分解结果
            ttl_hours: 过期时间（小时）

        Returns:
            是否成功

        业务逻辑：
        - 计算缓存键和过期时间
        - Upsert操作（存在则更新，不存在则插入）
        - 失败不抛出异常，返回False
        """
        pass

    @abstractmethod
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            统计信息字典
            {
                "total_cached": 100,
                "valid_cached": 80,
                "expired_cached": 20,
                "total_hits": 500,
                "avg_hits_per_cache": 5.0,
                "estimated_tokens_saved": 50000,
                "cache_hit_rate": 0.8
            }

        用途：
        - 监控缓存效果
        - 成本节约分析
        """
        pass

    @abstractmethod
    async def clear_expired_cache(self) -> int:
        """清理过期缓存

        Returns:
            删除的缓存数量

        用途：
        - 定期清理（如每日凌晨）
        - 释放存储空间
        """
        pass
