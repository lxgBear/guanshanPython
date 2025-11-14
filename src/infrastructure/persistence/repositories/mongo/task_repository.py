"""
MongoDB 搜索任务 Repository 实现

基于 MongoDB 的搜索任务数据访问实现，实现 ITaskRepository 接口。

Version: v3.0.0 (模块化架构)
"""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from src.core.domain.entities.search_task import SearchTask, TaskStatus, ScheduleInterval
from src.infrastructure.persistence.interfaces import ITaskRepository
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoTaskRepository(ITaskRepository):
    """
    MongoDB 搜索任务 Repository 实现

    使用 MongoDB 作为数据存储，实现 ITaskRepository 接口。
    """

    def __init__(self):
        self.collection_name = "search_tasks"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _task_to_dict(self, task: SearchTask) -> Dict[str, Any]:
        """将任务实体转换为 MongoDB 文档"""
        return {
            "_id": str(task.id),
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type,
            "query": task.query,
            "crawl_url": task.crawl_url,
            "target_website": task.target_website,
            "search_config": task.search_config,
            "crawl_config": task.crawl_config,
            "schedule_interval": task.schedule_interval,
            "is_active": task.is_active,
            "status": task.status.value,
            "created_by": task.created_by,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "last_executed_at": task.last_executed_at,
            "next_run_time": task.next_run_time,
            "execution_count": task.execution_count,
            "success_count": task.success_count,
            "failure_count": task.failure_count,
            "total_results": task.total_results,
            "total_credits_used": task.total_credits_used,
            "last_error": task.last_error,
            "last_error_time": task.last_error_time
        }

    def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
        """将 MongoDB 文档转换为任务实体"""
        # 防御性编程：确保配置字段是字典类型
        search_config = data.get("search_config", {})
        if not isinstance(search_config, dict):
            search_config = {}

        crawl_config = data.get("crawl_config", {})
        if not isinstance(crawl_config, dict):
            crawl_config = {}

        task = SearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description"),
            task_type=data.get("task_type", "search_keyword"),
            query=data["query"],
            crawl_url=data.get("crawl_url"),
            target_website=data.get("target_website"),
            search_config=search_config,
            crawl_config=crawl_config,
            schedule_interval=data["schedule_interval"],
            is_active=data["is_active"],
            status=TaskStatus(data["status"]),
            created_by=data["created_by"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            last_executed_at=data.get("last_executed_at"),
            next_run_time=data.get("next_run_time"),
            execution_count=data.get("execution_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            total_results=data.get("total_results", 0),
            total_credits_used=data.get("total_credits_used", 0),
            last_error=data.get("last_error"),
            last_error_time=data.get("last_error_time")
        )

        # 自动同步 target_website
        task.sync_target_website()
        return task

    # ==================== IBasicRepository 实现 ====================

    async def create(self, entity: SearchTask) -> str:
        """创建搜索任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(entity)

            await collection.insert_one(task_dict)
            logger.info(f"✅ 创建任务: {entity.name} (ID: {entity.id})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建任务失败: {e}")
            raise RepositoryException(f"创建任务失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[SearchTask]:
        """根据ID获取任务"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_task(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取任务失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取任务失败: {e}", e)

    async def update(self, entity: SearchTask) -> bool:
        """更新任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(entity)
            task_dict.pop("_id")  # 移除 ID 字段

            result = await collection.update_one(
                {"_id": str(entity.id)},
                {"$set": task_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"任务不存在: {entity.id}")

            logger.info(f"✅ 更新任务: {entity.name} (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新任务失败: {e}")
            raise RepositoryException(f"更新任务失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除任务"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除任务: {id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 删除任务失败: {e}")
            raise RepositoryException(f"删除任务失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查任务是否存在"""
        try:
            collection = await self._get_collection()
            count = await collection.count_documents({"_id": id}, limit=1)
            return count > 0

        except Exception as e:
            logger.error(f"❌ 检查任务存在性失败: {e}")
            raise RepositoryException(f"检查任务存在性失败: {e}", e)

    # ==================== IQueryableRepository 实现 ====================

    async def find_all(self, limit: Optional[int] = None) -> List[SearchTask]:
        """获取所有任务"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({}).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks

        except Exception as e:
            logger.error(f"❌ 获取所有任务失败: {e}")
            raise RepositoryException(f"获取所有任务失败: {e}", e)

    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[SearchTask]:
        """根据条件查询任务"""
        try:
            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks

        except Exception as e:
            logger.error(f"❌ 条件查询任务失败: {e}")
            raise RepositoryException(f"条件查询任务失败: {e}", e)

    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """统计任务数量"""
        try:
            collection = await self._get_collection()
            query = criteria if criteria else {}
            return await collection.count_documents(query)

        except Exception as e:
            logger.error(f"❌ 统计任务数量失败: {e}")
            raise RepositoryException(f"统计任务数量失败: {e}", e)

    # ==================== IPaginatableRepository 实现 ====================

    async def find_with_pagination(
        self,
        page: int,
        page_size: int,
        criteria: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> Tuple[List[SearchTask], int]:
        """分页查询任务"""
        if page < 1:
            raise ValueError("页码必须大于等于1")
        if page_size < 1:
            raise ValueError("页大小必须大于等于1")

        try:
            collection = await self._get_collection()
            query = criteria if criteria else {}

            # 统计总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            sort_field = sort_by if sort_by else "created_at"
            sort_direction = -1 if sort_order == "desc" else 1

            cursor = collection.find(query).sort(sort_field, sort_direction).skip(skip).limit(page_size)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks, total

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ 分页查询任务失败: {e}")
            raise RepositoryException(f"分页查询任务失败: {e}", e)

    # ==================== ITaskRepository 特定方法 ====================

    async def find_active_tasks(self) -> List[SearchTask]:
        """获取所有活跃任务"""
        try:
            criteria = {
                "is_active": True,
                "status": TaskStatus.ACTIVE.value
            }
            return await self.find_by_criteria(criteria)

        except Exception as e:
            logger.error(f"❌ 获取活跃任务失败: {e}")
            raise RepositoryException(f"获取活跃任务失败: {e}", e)

    async def find_by_schedule(self, schedule_interval: str) -> List[SearchTask]:
        """根据调度间隔查询任务"""
        try:
            # 验证调度间隔值
            try:
                ScheduleInterval.from_value(schedule_interval)
            except ValueError as e:
                raise ValueError(f"无效的调度间隔: {schedule_interval}")

            criteria = {"schedule_interval": schedule_interval}
            return await self.find_by_criteria(criteria)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ 按调度间隔查询任务失败: {e}")
            raise RepositoryException(f"按调度间隔查询任务失败: {e}", e)

    async def find_by_status(self, status: TaskStatus) -> List[SearchTask]:
        """根据状态查询任务"""
        try:
            criteria = {"status": status.value}
            return await self.find_by_criteria(criteria)

        except Exception as e:
            logger.error(f"❌ 按状态查询任务失败: {e}")
            raise RepositoryException(f"按状态查询任务失败: {e}", e)

    async def find_by_creator(self, created_by: str) -> List[SearchTask]:
        """根据创建者查询任务"""
        try:
            criteria = {"created_by": created_by}
            return await self.find_by_criteria(criteria)

        except Exception as e:
            logger.error(f"❌ 按创建者查询任务失败: {e}")
            raise RepositoryException(f"按创建者查询任务失败: {e}", e)

    async def find_tasks_due_for_execution(
        self,
        current_time: datetime
    ) -> List[SearchTask]:
        """查询到期需要执行的任务"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({
                "is_active": True,
                "status": TaskStatus.ACTIVE.value,
                "$or": [
                    {"next_run_time": None},  # 从未执行
                    {"next_run_time": {"$lte": current_time}}  # 已到期
                ]
            })

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks

        except Exception as e:
            logger.error(f"❌ 查询到期任务失败: {e}")
            raise RepositoryException(f"查询到期任务失败: {e}", e)

    async def update_execution_stats(
        self,
        task_id: str,
        success: bool,
        result_count: int,
        credits_used: int,
        next_run_time: Optional[datetime] = None
    ) -> bool:
        """更新任务执行统计"""
        try:
            collection = await self._get_collection()

            # 构建更新数据
            update_data = {
                "execution_count": {"$inc": 1},  # 使用 $inc 原子操作
                "total_results": {"$inc": result_count},
                "total_credits_used": {"$inc": credits_used},
                "last_executed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            if success:
                update_data["success_count"] = {"$inc": 1}
            else:
                update_data["failure_count"] = {"$inc": 1}

            if next_run_time:
                update_data["next_run_time"] = next_run_time

            # 使用 $inc 操作符进行原子更新
            result = await collection.update_one(
                {"_id": task_id},
                {
                    "$inc": {
                        "execution_count": 1,
                        "success_count": 1 if success else 0,
                        "failure_count": 0 if success else 1,
                        "total_results": result_count,
                        "total_credits_used": credits_used
                    },
                    "$set": {
                        "last_executed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        **({"next_run_time": next_run_time} if next_run_time else {})
                    }
                }
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"任务不存在: {task_id}")

            logger.info(f"✅ 更新执行统计: {task_id} (成功={success}, 结果数={result_count})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新执行统计失败: {e}")
            raise RepositoryException(f"更新执行统计失败: {e}", e)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None
    ) -> Tuple[List[SearchTask], int]:
        """分页查询任务列表（带过滤）"""
        try:
            # 构建查询条件
            criteria = {}

            if status:
                criteria["status"] = status

            if is_active is not None:
                criteria["is_active"] = is_active

            if query:
                # 模糊查询：名称、描述、查询词
                criteria["$or"] = [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"query": {"$regex": query, "$options": "i"}}
                ]

            return await self.find_with_pagination(
                page=page,
                page_size=page_size,
                criteria=criteria,
                sort_by="created_at",
                sort_order="desc"
            )

        except Exception as e:
            logger.error(f"❌ 列表查询任务失败: {e}")
            raise RepositoryException(f"列表查询任务失败: {e}", e)
