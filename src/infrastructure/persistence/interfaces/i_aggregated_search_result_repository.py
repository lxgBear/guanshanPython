"""聚合搜索结果仓储接口

Version: v3.0.0 (模块化架构)

v1.5.2 职责分离实现：
- 专用于 smart_search_results 集合
- 存储智能搜索的去重聚合结果
- 包含综合评分、多源信息等聚合字段

聚合搜索结果仓储提供智能搜索聚合结果的持久化操作，包括：
- 批量保存聚合结果
- 多维度查询（按任务、状态、评分、来源数）
- 统计分析（综合评分、多源比例）
- 状态管理（单个和批量更新）
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.aggregated_search_result import AggregatedSearchResult
from src.core.domain.entities.search_result import ResultStatus
from .i_repository import IBasicRepository


class IAggregatedSearchResultRepository(IBasicRepository[AggregatedSearchResult]):
    """聚合搜索结果仓储接口

    职责：
    - 存储去重聚合后的搜索结果
    - 包含综合评分、多源信息、聚合统计
    - 与 instant_search_results 分离
    - 支持多维度查询和排序
    - 提供丰富的统计分析功能
    """

    @abstractmethod
    async def save_results(
        self,
        results: List[AggregatedSearchResult]
    ) -> int:
        """批量保存聚合搜索结果

        Args:
            results: 聚合搜索结果列表

        Returns:
            插入的记录数

        注意：
        - 使用insert_many批量插入
        - 文档_id使用实体id
        """
        pass

    @abstractmethod
    async def get_results_by_task(
        self,
        smart_task_id: str,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "composite_score"
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """获取任务的聚合搜索结果

        Args:
            smart_task_id: 智能搜索任务ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            sort_by: 排序字段（composite_score, avg_relevance_score, source_count, created_at）

        Returns:
            (结果列表, 总数)

        排序规则：
        - composite_score: 综合评分倒序 + 来源数倒序 + 平均相关性倒序
        - source_count: 来源数倒序 + 综合评分倒序
        - avg_relevance_score: 平均相关性倒序 + 综合评分倒序
        - created_at: 创建时间倒序
        """
        pass

    @abstractmethod
    async def get_top_results(
        self,
        smart_task_id: str,
        limit: int = 10,
        min_composite_score: float = 0.0
    ) -> List[AggregatedSearchResult]:
        """获取任务的top结果（按综合评分）

        Args:
            smart_task_id: 智能搜索任务ID
            limit: 返回的最大记录数
            min_composite_score: 最小综合评分阈值

        Returns:
            结果列表

        排序：
        - 综合评分倒序 + 来源数倒序 + 平均相关性倒序
        """
        pass

    @abstractmethod
    async def get_multi_source_results(
        self,
        smart_task_id: str,
        min_source_count: int = 2,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """获取多源结果（出现在多个查询中）

        Args:
            smart_task_id: 智能搜索任务ID
            min_source_count: 最小来源数量
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)

        排序：
        - 来源数倒序 + 综合评分倒序
        """
        pass

    @abstractmethod
    async def count_results_by_task(self, smart_task_id: str) -> int:
        """统计任务的结果数量

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            结果数量
        """
        pass

    @abstractmethod
    async def get_statistics_by_task(self, smart_task_id: str) -> Dict[str, Any]:
        """获取任务的统计信息

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            统计信息字典，包含：
            - total_results: 总结果数
            - avg_composite_score: 平均综合评分
            - avg_source_count: 平均来源数
            - max_composite_score: 最高综合评分
            - min_composite_score: 最低综合评分
            - multi_source_results: 多源结果数
            - single_source_results: 单源结果数
            - multi_source_ratio: 多源结果比例

        业务逻辑：
        - 使用MongoDB聚合管道统计
        - 计算多源和单源结果分布
        """
        pass

    @abstractmethod
    async def delete_results_by_task(self, smart_task_id: str) -> int:
        """删除任务的所有结果

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            删除的记录数
        """
        pass

    @abstractmethod
    async def update_result(self, result: AggregatedSearchResult) -> bool:
        """更新单个结果

        Args:
            result: 聚合搜索结果

        Returns:
            是否更新成功

        注意：
        - 自动更新updated_at字段
        """
        pass

    @abstractmethod
    async def get_by_url(
        self,
        smart_task_id: str,
        url: str
    ) -> Optional[AggregatedSearchResult]:
        """根据URL查找结果（去重时使用）

        Args:
            smart_task_id: 智能搜索任务ID
            url: 结果URL

        Returns:
            聚合搜索结果（如果存在）

        业务逻辑：
        - 用于去重检查
        - 同一URL在同一任务中只保存一次
        """
        pass

    # ==================== 状态管理方法 ====================

    @abstractmethod
    async def get_results_by_status(
        self,
        smart_task_id: str,
        status: ResultStatus,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """按状态筛选结果

        Args:
            smart_task_id: 智能搜索任务ID
            status: 结果状态
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)

        排序：
        - 综合评分倒序 + 创建时间倒序
        """
        pass

    @abstractmethod
    async def count_by_status(self, smart_task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            状态计数字典 {status_value: count}

        业务逻辑：
        - 使用MongoDB聚合管道按状态分组
        - 返回所有可能状态的计数（未出现的为0）
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

        注意：
        - 自动更新updated_at字段
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

        业务逻辑：
        - 使用update_many批量更新
        - 自动更新updated_at字段
        """
        pass
