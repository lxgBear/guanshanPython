"""智能搜索任务仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 ISmartSearchTaskRepository 接口，提供：
- 智能搜索任务的 CRUD 操作
- 按状态、创建者筛选的分页查询
- 任务生命周期管理（分解→确认→执行→聚合）

职责：
- 数据库操作：MongoDB 集合 smart_search_tasks
- 实体转换：SmartSearchTask <-> Dict（包含复杂嵌套结构）
- 异常处理：统一的错误日志和异常抛出

智能搜索工作流：
1. **分解阶段**: LLM分解原始查询为多个子查询
2. **确认阶段**: 用户确认/修改子查询
3. **执行阶段**: 并发执行子查询，收集结果
4. **聚合阶段**: 聚合分析子查询结果
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.smart_search_task import (
    SmartSearchTask,
    SmartSearchStatus,
    SubSearchResult
)
from src.core.domain.entities.query_decomposition import DecomposedQuery
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_smart_search_repository import (
    ISmartSearchTaskRepository
)
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoSmartSearchTaskRepository(ISmartSearchTaskRepository):
    """智能搜索任务仓储 MongoDB 实现

    集合: smart_search_tasks

    索引建议:
    - _id (默认)
    - status (筛选)
    - created_by (筛选)
    - created_at (排序)
    - original_query (查询优化)

    复杂字段：
    - decomposed_queries: List[DecomposedQuery]
    - sub_search_results: Dict[task_id, SubSearchResult]
    - user_confirmed_queries: List[str]
    - aggregated_stats: Dict[str, Any]
    """

    def __init__(self):
        self.collection_name = "smart_search_tasks"

    async def _get_collection(self):
        """获取MongoDB集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _task_to_dict(self, task: SmartSearchTask) -> Dict[str, Any]:
        """将任务实体转换为MongoDB文档

        Args:
            task: 任务实体

        Returns:
            MongoDB文档字典
        """
        return {
            "_id": task.id,
            "name": task.name,
            "description": task.description,
            "original_query": task.original_query,
            "search_config": task.search_config,

            # 分解阶段
            "decomposed_queries": [
                {
                    "query": q.query,
                    "reasoning": q.reasoning,
                    "focus": q.focus
                }
                for q in task.decomposed_queries
            ],
            "llm_model": task.llm_model,
            "llm_reasoning": task.llm_reasoning,
            "decomposition_tokens_used": task.decomposition_tokens_used,

            # 确认阶段
            "user_confirmed_queries": task.user_confirmed_queries,
            "user_modifications": task.user_modifications,

            # 执行阶段
            "sub_search_task_ids": task.sub_search_task_ids,
            "sub_search_results": {
                task_id: {
                    "query": r.query,
                    "task_id": r.task_id,
                    "status": r.status,
                    "result_count": r.result_count,
                    "credits_used": r.credits_used,
                    "execution_time_ms": r.execution_time_ms,
                    "error": r.error,
                    "retryable": r.retryable
                }
                for task_id, r in task.sub_search_results.items()
            },

            # 聚合统计
            "aggregated_stats": task.aggregated_stats,

            # 状态管理
            "status": task.status.value,
            "created_by": task.created_by,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "confirmed_at": task.confirmed_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,

            # 元数据
            "execution_time_ms": task.execution_time_ms or task.calculate_execution_time(),
            "error_message": task.error_message
        }

    def _dict_to_task(self, data: Dict[str, Any]) -> SmartSearchTask:
        """将MongoDB文档转换为任务实体

        Args:
            data: MongoDB文档字典

        Returns:
            任务实体
        """
        # 转换DecomposedQuery列表
        decomposed_queries = [
            DecomposedQuery(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in data.get("decomposed_queries", [])
        ]

        # 转换SubSearchResult字典
        sub_search_results = {
            task_id: SubSearchResult(
                query=r["query"],
                task_id=r["task_id"],
                status=r["status"],
                result_count=r.get("result_count", 0),
                credits_used=r.get("credits_used", 0),
                execution_time_ms=r.get("execution_time_ms", 0),
                error=r.get("error"),
                retryable=r.get("retryable", False)
            )
            for task_id, r in data.get("sub_search_results", {}).items()
        }

        return SmartSearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description", "智能搜索任务"),
            original_query=data["original_query"],
            search_config=data.get("search_config", {}),

            decomposed_queries=decomposed_queries,
            llm_model=data.get("llm_model", "gpt-4"),
            llm_reasoning=data.get("llm_reasoning", ""),
            decomposition_tokens_used=data.get("decomposition_tokens_used", 0),

            user_confirmed_queries=data.get("user_confirmed_queries", []),
            user_modifications=data.get("user_modifications", {}),

            sub_search_task_ids=data.get("sub_search_task_ids", []),
            sub_search_results=sub_search_results,

            aggregated_stats=data.get("aggregated_stats", {}),

            status=SmartSearchStatus(data.get("status", "awaiting_confirmation")),
            created_by=data.get("created_by", "system"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            confirmed_at=data.get("confirmed_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),

            execution_time_ms=data.get("execution_time_ms", 0),
            error_message=data.get("error_message")
        )

    async def create(self, entity: SmartSearchTask) -> str:
        """创建智能搜索任务

        Args:
            entity: 任务实体

        Returns:
            task_id: 创建的任务ID

        Raises:
            RepositoryException: 创建失败时抛出
        """
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(entity)

            await collection.insert_one(task_dict)
            logger.info(f"✅ 创建智能搜索任务: {entity.name} (ID: {entity.id})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建智能搜索任务失败: {e}")
            raise RepositoryException(f"创建智能搜索任务失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[SmartSearchTask]:
        """根据ID获取任务

        Args:
            id: 任务ID

        Returns:
            任务实体或None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_task(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取智能搜索任务失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取智能搜索任务失败: {e}", e)

    async def update(self, entity: SmartSearchTask) -> bool:
        """更新任务

        Args:
            entity: 任务实体

        Returns:
            是否更新成功

        Raises:
            EntityNotFoundException: 任务不存在
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(entity)
            task_dict.pop("_id")  # 移除ID字段

            result = await collection.update_one(
                {"_id": entity.id},
                {"$set": task_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"智能搜索任务不存在: {entity.id}")

            logger.info(f"✅ 更新智能搜索任务: {entity.name} (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新智能搜索任务失败: {e}")
            raise RepositoryException(f"更新智能搜索任务失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除任务

        Args:
            id: 任务ID

        Returns:
            是否删除成功

        Raises:
            RepositoryException: 删除失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除智能搜索任务: ID={id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 删除智能搜索任务失败 (ID: {id}): {e}")
            raise RepositoryException(f"删除智能搜索任务失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查任务是否存在

        Args:
            id: 任务ID

        Returns:
            是否存在

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            count = await collection.count_documents({"_id": id}, limit=1)
            return count > 0

        except Exception as e:
            logger.error(f"❌ 检查智能搜索任务是否存在失败 (ID: {id}): {e}")
            raise RepositoryException(f"检查任务是否存在失败: {e}", e)

    async def find_with_pagination(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: int = -1
    ) -> Tuple[List[SmartSearchTask], int]:
        """分页查询任务（通用方法）

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            filters: 查询条件字典
            sort_by: 排序字段
            sort_order: 排序方向（1升序，-1降序）

        Returns:
            (tasks, total): 任务列表和总数

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()

            # 构建查询条件
            filter_dict = filters or {}

            # 计算总数
            total = await collection.count_documents(filter_dict)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort(sort_by, sort_order).skip(skip).limit(page_size)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks, total

        except Exception as e:
            logger.error(f"❌ 分页查询智能搜索任务失败: {e}")
            raise RepositoryException(f"分页查询任务失败: {e}", e)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[SmartSearchTask], int]:
        """获取任务列表（业务方法）

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

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()

            # 构建查询条件
            filter_dict = {}

            if status:
                filter_dict["status"] = status

            if created_by:
                filter_dict["created_by"] = created_by

            # 计算总数
            total = await collection.count_documents(filter_dict)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(page_size)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            logger.debug(
                f"📋 查询智能搜索任务列表: page={page}, size={page_size}, "
                f"status={status}, created_by={created_by}, total={total}"
            )

            return tasks, total

        except Exception as e:
            logger.error(f"❌ 获取智能搜索任务列表失败: {e}")
            raise RepositoryException(f"获取任务列表失败: {e}", e)
