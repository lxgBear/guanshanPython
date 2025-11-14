"""Firecrawl原始响应仓储接口

Version: v3.0.0 (模块化架构)

⚠️ 临时仓储接口
用途：存储和查询 Firecrawl API 原始响应数据
用完后会删除

Firecrawl原始响应仓储提供API响应的持久化操作，包括：
- 创建和批量创建原始响应记录
- 按任务ID、URL查询
- 统计和删除操作
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any

from src.core.domain.entities.firecrawl_raw_response import FirecrawlRawResponse
from .i_repository import IBasicRepository


class IFirecrawlRawResponseRepository(IBasicRepository[FirecrawlRawResponse]):
    """Firecrawl原始响应仓储接口

    职责：
    - 原始响应的创建和批量创建
    - 按任务ID、URL查询响应
    - 统计响应数量和任务分布
    - 按任务删除和全量清理
    - 临时数据管理

    注意：
    - 这是临时仓储，主要用于调试和数据分析
    - 不需要复杂的事务支持
    - 提供批量操作以提高性能
    """

    @abstractmethod
    async def create(self, entity: FirecrawlRawResponse) -> str:
        """创建原始响应记录

        Args:
            entity: FirecrawlRawResponse实体

        Returns:
            创建的记录ID
        """
        pass

    @abstractmethod
    async def batch_create(self, entities: List[FirecrawlRawResponse]) -> int:
        """批量创建原始响应记录

        Args:
            entities: FirecrawlRawResponse实体列表

        Returns:
            创建的记录数量

        业务逻辑：
        - 使用insert_many批量插入
        - 提高大批量数据的插入性能
        """
        pass

    @abstractmethod
    async def get_by_id(self, response_id: str) -> Optional[FirecrawlRawResponse]:
        """根据ID获取原始响应

        Args:
            response_id: 响应ID

        Returns:
            FirecrawlRawResponse实体或None
        """
        pass

    @abstractmethod
    async def get_by_task_id(
        self,
        task_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[FirecrawlRawResponse]:
        """根据任务ID获取原始响应列表

        Args:
            task_id: 任务ID
            limit: 限制数量
            skip: 跳过数量

        Returns:
            FirecrawlRawResponse实体列表

        排序：
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def get_by_url(self, url: str) -> List[FirecrawlRawResponse]:
        """根据URL获取原始响应（可能有多次爬取）

        Args:
            url: 结果URL

        Returns:
            FirecrawlRawResponse实体列表

        业务逻辑：
        - 返回同一URL的所有爬取记录
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def count_by_task_id(self, task_id: str) -> int:
        """统计任务的原始响应数量

        Args:
            task_id: 任务ID

        Returns:
            数量
        """
        pass

    @abstractmethod
    async def delete_by_task_id(self, task_id: str) -> int:
        """删除任务的所有原始响应

        Args:
            task_id: 任务ID

        Returns:
            删除的数量
        """
        pass

    @abstractmethod
    async def delete_all(self) -> int:
        """删除所有原始响应（清理临时数据）

        Returns:
            删除的数量

        注意：
        - 这是危险操作，仅用于清理临时数据
        - 通常在调试完成后调用
        """
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计数据字典，包含：
            - total_responses: 总响应数
            - top_tasks: 响应数最多的前10个任务

        业务逻辑：
        - 使用MongoDB聚合管道统计
        - 按任务分组并排序
        """
        pass
