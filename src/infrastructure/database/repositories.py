"""数据库仓储层实现"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.search_task import SearchTask, TaskStatus
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SearchTaskRepository:
    """搜索任务仓储"""
    
    def __init__(self):
        self.collection_name = "search_tasks"
    
    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]
    
    def _task_to_dict(self, task: SearchTask) -> Dict[str, Any]:
        """将任务实体转换为字典"""
        return {
            "_id": str(task.id),
            "name": task.name,
            "description": task.description,
            "query": task.query,
            "search_config": task.search_config,
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
            "total_credits_used": task.total_credits_used
        }
    
    def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
        """将字典转换为任务实体"""
        return SearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description"),
            query=data["query"],
            search_config=data.get("search_config", {}),
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
            total_credits_used=data.get("total_credits_used", 0)
        )
    
    async def create(self, task: SearchTask) -> SearchTask:
        """创建任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)
            
            await collection.insert_one(task_dict)
            logger.info(f"创建任务成功: {task.name} (ID: {task.id})")
            
            return task
            
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            raise
    
    async def get_by_id(self, task_id: str) -> Optional[SearchTask]:
        """根据ID获取任务"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": task_id})
            
            if data:
                return self._dict_to_task(data)
            return None
            
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            raise
    
    async def update(self, task: SearchTask) -> SearchTask:
        """更新任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)
            task_dict.pop("_id")  # 移除ID字段
            
            result = await collection.update_one(
                {"_id": str(task.id)},
                {"$set": task_dict}
            )
            
            if result.matched_count == 0:
                raise ValueError(f"任务不存在: {task.id}")
            
            logger.info(f"更新任务成功: {task.name} (ID: {task.id})")
            return task
            
        except Exception as e:
            logger.error(f"更新任务失败: {e}")
            raise
    
    async def delete(self, task_id: str) -> bool:
        """删除任务"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": task_id})
            
            if result.deleted_count > 0:
                logger.info(f"删除任务成功: {task_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            raise
    
    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> tuple[List[SearchTask], int]:
        """获取任务列表"""
        try:
            collection = await self._get_collection()
            
            # 构建查询条件
            filter_dict = {}
            
            if status:
                filter_dict["status"] = status
            
            if is_active is not None:
                filter_dict["is_active"] = is_active
            
            if created_by:
                filter_dict["created_by"] = created_by
            
            if query:
                # 模糊查询名称、描述和查询词
                filter_dict["$or"] = [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"query": {"$regex": query, "$options": "i"}}
                ]
            
            # 计算总数
            total = await collection.count_documents(filter_dict)
            
            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(page_size)
            
            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))
            
            return tasks, total
            
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            raise
    
    async def get_active_tasks(self) -> List[SearchTask]:
        """获取所有活跃任务（用于调度）"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({
                "is_active": True,
                "status": TaskStatus.ACTIVE.value
            })
            
            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取活跃任务失败: {e}")
            raise
    
    async def get_tasks_to_execute(self, current_time: datetime) -> List[SearchTask]:
        """获取需要执行的任务"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({
                "is_active": True,
                "status": TaskStatus.ACTIVE.value,
                "$or": [
                    {"next_run_time": None},  # 从未执行过的任务
                    {"next_run_time": {"$lte": current_time}}  # 到期的任务
                ]
            })
            
            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取待执行任务失败: {e}")
            raise


class SearchResultRepository:
    """搜索结果仓储"""
    
    def __init__(self):
        self.collection_name = "search_results"
    
    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]
    
    def _result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        """将结果实体转换为字典"""
        return {
            "_id": str(result.id),
            "task_id": str(result.task_id),
            "title": result.title,
            "url": result.url,
            "content": result.content,
            "snippet": result.snippet,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            "raw_data": result.raw_data,
            "markdown_content": result.markdown_content,
            "html_content": result.html_content,
            "article_tag": result.article_tag,
            "article_published_time": result.article_published_time,
            "metadata": result.metadata,
            "relevance_score": result.relevance_score,
            "quality_score": result.quality_score,
            "status": result.status.value,
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "is_test_data": result.is_test_data
        }
    
    def _dict_to_result(self, data: Dict[str, Any]) -> SearchResult:
        """将字典转换为结果实体"""
        # 处理ID转换 - task_id可能是字符串格式的数字ID（雪花算法）
        # 需要转换为UUID格式，如果不是有效的UUID，使用uuid5生成
        try:
            result_id = UUID(data["_id"])
        except (ValueError, AttributeError):
            # 如果不是有效的UUID，使用字符串作为命名空间生成UUID
            import uuid
            result_id = uuid.uuid5(uuid.NAMESPACE_OID, str(data["_id"]))

        try:
            task_id = UUID(data["task_id"])
        except (ValueError, AttributeError):
            # 使用雪花ID字符串生成UUID
            import uuid
            task_id = uuid.uuid5(uuid.NAMESPACE_OID, str(data["task_id"]))

        # 处理article_tag：数据库中可能存储为列表
        article_tag_raw = data.get("article_tag")
        if isinstance(article_tag_raw, list):
            # 如果是列表，用逗号连接成字符串
            article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        else:
            article_tag = article_tag_raw

        return SearchResult(
            id=result_id,
            task_id=task_id,
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            snippet=data.get("snippet"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            raw_data=data.get("raw_data", {}),
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            article_tag=article_tag,
            article_published_time=data.get("article_published_time"),
            metadata=data.get("metadata", {}),
            relevance_score=data.get("relevance_score", 0.0),
            quality_score=data.get("quality_score", 0.0),
            status=ResultStatus(data.get("status", "pending")),
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            is_test_data=data.get("is_test_data", False)
        )
    
    async def save_results(self, results: List[SearchResult]) -> None:
        """批量保存搜索结果"""
        if not results:
            return
        
        try:
            collection = await self._get_collection()
            result_dicts = [self._result_to_dict(result) for result in results]
            
            await collection.insert_many(result_dicts)
            logger.info(f"保存搜索结果成功: {len(results)}条")
            
        except Exception as e:
            logger.error(f"保存搜索结果失败: {e}")
            raise
    
    async def get_results_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20,
        execution_time: Optional[datetime] = None
    ) -> tuple[List[SearchResult], int]:
        """获取任务的搜索结果"""
        try:
            collection = await self._get_collection()
            
            # 构建查询条件
            filter_dict = {"task_id": task_id}
            if execution_time:
                filter_dict["execution_time"] = execution_time
            
            # 计算总数
            total = await collection.count_documents(filter_dict)
            
            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(page_size)
            
            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))
            
            return results, total
            
        except Exception as e:
            logger.error(f"获取任务结果失败: {e}")
            raise
    
    async def get_latest_results(
        self,
        task_id: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """获取任务的最新结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({"task_id": task_id}).sort("created_at", -1).limit(limit)
            
            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))
            
            return results
            
        except Exception as e:
            logger.error(f"获取最新结果失败: {e}")
            raise
    
    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})
            
            logger.info(f"删除任务结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"删除任务结果失败: {e}")
            raise