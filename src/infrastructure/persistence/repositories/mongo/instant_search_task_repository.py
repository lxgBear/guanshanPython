"""即时搜索任务仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 IInstantSearchTaskRepository 接口，提供：
- 即时搜索任务的 CRUD 操作
- 按状态、创建者筛选的分页查询
- 任务列表查询功能

职责：
- 数据库操作：MongoDB 集合 instant_search_tasks
- 实体转换：InstantSearchTask <-> Dict
- 异常处理：统一的错误日志和异常抛出
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_instant_search_repository import (
    IInstantSearchTaskRepository
)
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoInstantSearchTaskRepository(IInstantSearchTaskRepository):
    """即时搜索任务仓储 MongoDB 实现

    集合: instant_search_tasks

    索引建议:
    - _id (默认)
    - status (筛选)
    - created_by (筛选)
    - created_at (排序)
    - search_execution_id (唯一查询)
    """

    def __init__(self):
        self.collection_name = "instant_search_tasks"

    async def _get_collection(self):
        """获取MongoDB集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _task_to_dict(self, task: InstantSearchTask) -> Dict[str, Any]:
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
            "query": task.query,
            "crawl_url": task.crawl_url,
            "target_website": task.target_website,
            "search_config": task.search_config,
            "search_execution_id": task.search_execution_id,
            "status": task.status.value,
            "created_by": task.created_by,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "total_results": task.total_results,
            "new_results": task.new_results,
            "shared_results": task.shared_results,
            "credits_used": task.credits_used,
            "execution_time_ms": task.execution_time_ms,
            "error_message": task.error_message
        }

    def _dict_to_task(self, data: Dict[str, Any]) -> InstantSearchTask:
        """将MongoDB文档转换为任务实体

        Args:
            data: MongoDB文档字典

        Returns:
            任务实体
        """
        task = InstantSearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description"),
            query=data.get("query"),
            crawl_url=data.get("crawl_url"),
            target_website=data.get("target_website"),
            search_config=data.get("search_config", {}),
            search_execution_id=data["search_execution_id"],
            status=InstantSearchStatus(data["status"]),
            created_by=data.get("created_by", "system"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            total_results=data.get("total_results", 0),
            new_results=data.get("new_results", 0),
            shared_results=data.get("shared_results", 0),
            credits_used=data.get("credits_used", 0),
            execution_time_ms=data.get("execution_time_ms", 0),
            error_message=data.get("error_message")
        )

        # 如果 target_website 为空，自动提取
        task.sync_target_website()

        return task

    async def create(self, entity: InstantSearchTask) -> str:
        """创建即时搜索任务

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
            logger.info(f"✅ 创建即时搜索任务: {entity.name} (ID: {entity.id})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建即时搜索任务失败: {e}")
            raise RepositoryException(f"创建即时搜索任务失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[InstantSearchTask]:
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
            logger.error(f"❌ 获取即时搜索任务失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取即时搜索任务失败: {e}", e)

    async def update(self, entity: InstantSearchTask) -> bool:
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
                raise EntityNotFoundException(f"即时搜索任务不存在: {entity.id}")

            logger.info(f"✅ 更新即时搜索任务: {entity.name} (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新即时搜索任务失败: {e}")
            raise RepositoryException(f"更新即时搜索任务失败: {e}", e)

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
                logger.info(f"✅ 删除即时搜索任务: ID={id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 删除即时搜索任务失败 (ID: {id}): {e}")
            raise RepositoryException(f"删除即时搜索任务失败: {e}", e)

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
            logger.error(f"❌ 检查即时搜索任务是否存在失败 (ID: {id}): {e}")
            raise RepositoryException(f"检查任务是否存在失败: {e}", e)

    async def find_with_pagination(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: int = -1
    ) -> Tuple[List[InstantSearchTask], int]:
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
            logger.error(f"❌ 分页查询即时搜索任务失败: {e}")
            raise RepositoryException(f"分页查询任务失败: {e}", e)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[InstantSearchTask], int]:
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
                f"📋 查询即时搜索任务列表: page={page}, size={page_size}, "
                f"status={status}, created_by={created_by}, total={total}"
            )

            return tasks, total

        except Exception as e:
            logger.error(f"❌ 获取即时搜索任务列表失败: {e}")
            raise RepositoryException(f"获取任务列表失败: {e}", e)
