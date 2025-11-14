"""即时搜索仓储接口层

Version: v3.0.0 (模块化架构)

定义即时搜索相关的仓储接口：
- IInstantSearchTaskRepository: 即时搜索任务管理
- IInstantSearchResultRepository: 即时搜索结果管理（支持content_hash去重）
- IInstantSearchResultMappingRepository: 搜索-结果映射关系管理（核心）

设计原则：
1. Interface Segregation Principle (ISP): 接口职责单一明确
2. Dependency Inversion Principle (DIP): 依赖抽象而非实现
3. 去重核心：content_hash机制，避免重复存储相同内容
4. 关系追踪：映射表记录搜索发现结果的完整历史
"""

from abc import abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from src.core.domain.entities.instant_search_task import InstantSearchTask
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.instant_search_result_mapping import InstantSearchResultMapping

from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IPaginatableRepository
)


class IInstantSearchTaskRepository(
    IBasicRepository[InstantSearchTask],
    IPaginatableRepository[InstantSearchTask]
):
    """即时搜索任务仓储接口

    职责：
    - 管理即时搜索任务的生命周期（创建、查询、更新）
    - 支持按状态、创建者筛选的分页查询
    - 提供任务列表和详情查询功能

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
    ) -> Tuple[List[InstantSearchTask], int]:
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


class IInstantSearchResultRepository(
    IBasicRepository[InstantSearchResult]
):
    """即时搜索结果仓储接口

    职责：
    - 管理即时搜索结果的存储和查询
    - 实现基于content_hash的去重机制（v1.3.0核心）
    - 维护结果发现统计信息
    - 支持按任务ID和搜索类型查询

    去重机制 (v1.3.0)：
    1. 每个结果生成content_hash（基于标题+URL+内容）
    2. 新结果入库前先查询content_hash是否存在
    3. 存在则调用update_discovery_stats()更新统计
    4. 不存在则调用create()创建新结果

    统计字段：
    - first_found_at: 首次发现时间
    - last_found_at: 最近发现时间
    - found_count: 总发现次数
    - unique_searches: 发现该结果的唯一搜索数

    注意：
    - create() 返回 result_id (str)，而非实体
    - update() 返回更新成功标志 (bool)
    """

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> Optional[InstantSearchResult]:
        """根据content_hash查找结果（去重核心方法）

        Args:
            content_hash: 内容哈希值

        Returns:
            InstantSearchResult | None: 已存在的结果，或None

        用途：
        - 去重检测：新结果入库前必须调用此方法
        - 统计更新：命中时调用update_discovery_stats()
        - 映射创建：无论命中与否都创建映射记录
        """
        pass

    @abstractmethod
    async def create(
        self,
        result: InstantSearchResult,
        search_type: str = "instant"
    ) -> str:
        """创建新结果

        Args:
            result: 结果实体
            search_type: 搜索类型 ("instant" | "smart") v2.1.0统一架构

        Returns:
            result_id: 创建的结果ID

        注意：
        - 调用前应先检查content_hash是否存在
        - search_type用于统一架构支持（即时搜索和智能搜索共用结果表）
        """
        pass

    @abstractmethod
    async def update_discovery_stats(self, result: InstantSearchResult) -> bool:
        """更新发现统计信息（去重命中时调用）

        Args:
            result: 已存在的结果实体（包含ID）

        Returns:
            是否更新成功

        原子更新操作：
        - last_found_at = now
        - found_count += 1
        - unique_searches += 1
        - updated_at = now

        使用场景：
        - 当find_by_content_hash()命中时调用
        - 表示该结果被再次发现
        """
        pass

    @abstractmethod
    async def get_results_by_task_and_type(
        self,
        task_id: str,
        search_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[InstantSearchResult], int]:
        """根据任务ID和搜索类型查询结果（v2.1.0统一架构查询）

        Args:
            task_id: 任务ID
            search_type: 搜索类型筛选 ("instant" | "smart")，None表示不筛选
            skip: 跳过记录数（用于分页）
            limit: 返回最大记录数

        Returns:
            (results, total): 结果列表和总数

        排序规则：
        1. relevance_score DESC（相关性优先）
        2. created_at DESC（时间次之）
        """
        pass


class IInstantSearchResultMappingRepository(
    IBasicRepository[InstantSearchResultMapping]
):
    """即时搜索结果映射仓储接口

    职责：
    - 管理搜索执行与结果的多对多关系（v1.3.0核心）
    - 记录每次搜索发现结果的完整历史
    - 支持正向查询（某次搜索发现了哪些结果）
    - 支持反向查询（某个结果被哪些搜索发现）

    映射表设计：
    - search_execution_id: 搜索执行ID（每次搜索生成唯一ID）
    - result_id: 结果ID（指向instant_search_results）
    - task_id: 任务ID（冗余字段，方便查询）
    - search_position: 搜索结果排名位置
    - relevance_score: 相关性评分
    - is_first_discovery: 是否首次发现该结果
    - found_at: 发现时间

    去重机制关系：
    - 同一个result_id可以有多条映射记录（不同搜索发现）
    - 通过映射表可以追踪结果的完整发现历史
    - 映射表支持批量创建（一次搜索发现多个结果）

    唯一索引：
    - (search_execution_id, result_id) 联合唯一
    - 保证同一次搜索中同一个结果只记录一次

    注意：
    - create() 返回 mapping_id (str)，而非实体
    - batch_create() 支持重复键容错（v2.1.2）
    """

    @abstractmethod
    async def batch_create(self, mappings: List[InstantSearchResultMapping]) -> None:
        """批量创建映射记录（v2.1.2重复键容错）

        Args:
            mappings: 映射记录列表

        容错策略 (v2.1.2)：
        - 使用 ordered=False 允许部分插入成功
        - 捕获重复键异常，只记录警告而不抛出错误
        - 返回void，通过日志记录成功/跳过数量

        使用场景：
        - 一次搜索发现多个结果时批量创建映射
        - 性能优化：减少数据库往返次数
        """
        pass

    @abstractmethod
    async def get_results_by_search_execution(
        self,
        search_execution_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取某次搜索执行的所有结果（JOIN查询）

        Args:
            search_execution_id: 搜索执行ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            (results_with_mapping, total)
            每个元素包含：
            {
                "mapping": InstantSearchResultMapping,  # 映射元数据
                "result": InstantSearchResult            # 完整结果
            }

        查询逻辑：
        1. 筛选该次搜索的映射记录
        2. JOIN instant_search_results表获取完整结果
        3. 按search_position排序（保持搜索排名）
        4. 分页返回

        使用场景：
        - 前端展示某次搜索的结果列表
        - 追踪搜索结果的原始排名
        """
        pass

    @abstractmethod
    async def get_mappings_by_result(self, result_id: str) -> List[InstantSearchResultMapping]:
        """查询哪些搜索发现了该结果（反向查询）

        Args:
            result_id: 结果ID

        Returns:
            映射记录列表（按found_at倒序）

        使用场景：
        - 追溯结果的发现历史
        - 分析结果的复现频率
        - 验证去重机制的有效性
        """
        pass
