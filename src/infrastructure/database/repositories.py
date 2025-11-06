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
            "task_type": task.task_type,  # v2.0.0: 任务类型
            "query": task.query,
            "crawl_url": task.crawl_url,
            "target_website": task.target_website,
            "search_config": task.search_config,
            "crawl_config": task.crawl_config,  # v2.0.0: 爬取配置
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
            # v2.0.1: 错误信息
            "last_error": task.last_error,
            "last_error_time": task.last_error_time
        }
    
    def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
        """将字典转换为任务实体"""
        # 防御性编程：确保 search_config 和 crawl_config 是字典类型
        search_config_raw = data.get("search_config", {})
        search_config = search_config_raw if isinstance(search_config_raw, dict) else {}

        crawl_config_raw = data.get("crawl_config", {})
        crawl_config = crawl_config_raw if isinstance(crawl_config_raw, dict) else {}

        task = SearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description"),
            task_type=data.get("task_type", "search_keyword"),  # v2.0.0: 向后兼容，默认为关键词搜索
            query=data["query"],
            crawl_url=data.get("crawl_url"),  # 向后兼容：旧数据可能没有此字段
            target_website=data.get("target_website"),  # 向后兼容：旧数据可能没有此字段
            search_config=search_config,
            crawl_config=crawl_config,  # v2.0.0: 向后兼容，默认为空字典
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
            # v2.0.1: 错误信息（向后兼容，旧数据可能没有此字段）
            last_error=data.get("last_error"),
            last_error_time=data.get("last_error_time")
        )

        # 如果 target_website 为空，自动从 search_config 提取
        task.sync_target_website()

        return task
    
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
        """将结果实体转换为字典 - 优化后的模型（v2.1.0: 移除metadata存储）"""
        return {
            "_id": str(result.id),
            "task_id": str(result.task_id),
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            # 优化后的字段
            "markdown_content": result.markdown_content,  # Markdown格式内容
            "html_content": result.html_content,  # HTML格式内容
            "article_tag": result.article_tag,
            "article_published_time": result.article_published_time,
            "source_url": result.source_url,
            "http_status_code": result.http_status_code,
            "search_position": result.search_position,
            # v2.1.0: 不再存储 metadata 字段以减少数据量（2-5KB/记录）
            # 所有有用字段已提取为独立字段：author, language, article_tag, http_status_code等
            # "metadata": result.metadata,  # 已废弃 - 不再存储
            # 已移除字段: raw_data, content (使用markdown_content替代)
            "relevance_score": result.relevance_score,
            "quality_score": result.quality_score,
            "status": result.status.value,
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "is_test_data": result.is_test_data
        }
    
    def _dict_to_result(self, data: Dict[str, Any]) -> SearchResult:
        """将字典转换为结果实体

        v1.5.0: 修复ID类型 - 使用id字段（雪花ID）而非_id字段（MongoDB主键）
        """
        # v1.5.0: 优先使用id字段（迁移后的雪花ID），fallback到_id（向后兼容）
        result_id = str(data.get("id") or data.get("_id", ""))
        task_id = str(data.get("task_id", ""))

        # 处理article_tag：数据库中可能存储为列表
        article_tag_raw = data.get("article_tag")
        if isinstance(article_tag_raw, list):
            # 如果是列表，用逗号连接成字符串
            article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        else:
            article_tag = article_tag_raw

        # v1.5.2: 处理旧状态值的向后兼容
        status_value = data.get("status", "pending")
        try:
            status = ResultStatus(status_value)
        except ValueError:
            # 处理旧状态值: processing/completed → pending (回归到待处理)
            logger.warning(f"⚠️  检测到已废弃的状态值 '{status_value}'，将转换为 'pending' (ID: {result_id})")
            status = ResultStatus.PENDING

        return SearchResult(
            id=result_id,
            task_id=task_id,
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            # 优化后的字段
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            article_tag=article_tag,
            article_published_time=data.get("article_published_time"),
            source_url=data.get("source_url"),
            http_status_code=data.get("http_status_code"),
            search_position=data.get("search_position"),
            metadata=data.get("metadata", {}),
            # 已移除字段: raw_data, content (不再从数据库读取)
            relevance_score=data.get("relevance_score", 0.0),
            quality_score=data.get("quality_score", 0.0),
            status=status,
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

    # ==================== 状态管理方法 (v2.1.0新增) ====================

    async def get_results_by_status(
        self,
        task_id: str,
        status: ResultStatus,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[SearchResult], int]:
        """按状态筛选搜索结果

        Args:
            task_id: 任务ID
            status: 结果状态
            page: 页码
            page_size: 每页数量

        Returns:
            (结果列表, 总数)
        """
        try:
            collection = await self._get_collection()

            query = {
                "task_id": task_id,
                "status": status.value
            }

            # 总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results, total

        except Exception as e:
            logger.error(f"按状态获取结果失败: {e}")
            raise

    async def count_by_status(self, task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            task_id: 任务ID

        Returns:
            状态计数字典 {"pending": 10, "archived": 5, ...}
        """
        try:
            collection = await self._get_collection()

            pipeline = [
                {"$match": {"task_id": task_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]

            status_counts = {status.value: 0 for status in ResultStatus}

            async for doc in collection.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]

            return status_counts

        except Exception as e:
            logger.error(f"统计状态失败: {e}")
            raise

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
        try:
            collection = await self._get_collection()

            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"更新结果状态: {result_id} -> {new_status.value}")
                return True

            return False

        except Exception as e:
            logger.error(f"更新结果状态失败: {e}")
            raise

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
        try:
            collection = await self._get_collection()

            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await collection.update_many(
                {"_id": {"$in": result_ids}},
                {"$set": update_data}
            )

            logger.info(f"批量更新状态: {result.modified_count}条 -> {new_status.value}")
            return result.modified_count

        except Exception as e:
            logger.error(f"批量更新状态失败: {e}")
            raise

    async def get_status_distribution(self, task_id: str) -> Dict[str, Any]:
        """获取状态分布统计

        Args:
            task_id: 任务ID

        Returns:
            状态分布统计信息
        """
        try:
            # 获取各状态计数
            status_counts = await self.count_by_status(task_id)
            total = sum(status_counts.values())

            # 计算百分比
            distribution = {}
            for status, count in status_counts.items():
                percentage = (count / total * 100) if total > 0 else 0
                distribution[status] = {
                    "count": count,
                    "percentage": round(percentage, 2)
                }

            return {
                "total": total,
                "distribution": distribution
            }

        except Exception as e:
            logger.error(f"获取状态分布失败: {e}")
            raise