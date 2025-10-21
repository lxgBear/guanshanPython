"""即时搜索数据仓储层实现

v1.3.0 架构说明：
- InstantSearchTaskRepository: 管理即时搜索任务
- InstantSearchResultRepository: 管理搜索结果（支持content_hash去重）
- InstantSearchResultMappingRepository: 管理搜索-结果映射关系（核心）

数据库：MongoDB (使用Motor异步驱动)
集合命名：
- instant_search_tasks
- instant_search_results
- instant_search_result_mappings
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.instant_search_result_mapping import InstantSearchResultMapping
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InstantSearchTaskRepository:
    """即时搜索任务仓储"""

    def __init__(self):
        self.collection_name = "instant_search_tasks"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _task_to_dict(self, task: InstantSearchTask) -> Dict[str, Any]:
        """将任务实体转换为字典"""
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
        """将字典转换为任务实体"""
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

    async def create(self, task: InstantSearchTask) -> InstantSearchTask:
        """创建任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)

            await collection.insert_one(task_dict)
            logger.info(f"创建即时搜索任务成功: {task.name} (ID: {task.id})")

            return task

        except Exception as e:
            logger.error(f"创建即时搜索任务失败: {e}")
            raise

    async def get_by_id(self, task_id: str) -> Optional[InstantSearchTask]:
        """根据ID获取任务"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": task_id})

            if data:
                return self._dict_to_task(data)
            return None

        except Exception as e:
            logger.error(f"获取即时搜索任务失败: {e}")
            raise

    async def update(self, task: InstantSearchTask) -> InstantSearchTask:
        """更新任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)
            task_dict.pop("_id")  # 移除ID字段

            result = await collection.update_one(
                {"_id": task.id},
                {"$set": task_dict}
            )

            if result.matched_count == 0:
                raise ValueError(f"即时搜索任务不存在: {task.id}")

            logger.info(f"更新即时搜索任务成功: {task.name} (ID: {task.id})")
            return task

        except Exception as e:
            logger.error(f"更新即时搜索任务失败: {e}")
            raise

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[InstantSearchTask], int]:
        """获取任务列表"""
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

            return tasks, total

        except Exception as e:
            logger.error(f"获取即时搜索任务列表失败: {e}")
            raise


class InstantSearchResultRepository:
    """即时搜索结果仓储"""

    def __init__(self):
        self.collection_name = "instant_search_results"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: InstantSearchResult) -> Dict[str, Any]:
        """将结果实体转换为字典"""
        return {
            "_id": result.id,
            "task_id": result.task_id,
            "title": result.title,
            "url": result.url,
            "content": result.content,
            "snippet": result.snippet,
            "content_hash": result.content_hash,  # v1.3.0 去重键
            "url_normalized": result.url_normalized,  # v1.3.0 规范化URL
            "markdown_content": result.markdown_content,
            "html_content": result.html_content,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            "metadata": result.metadata,
            "relevance_score": result.relevance_score,
            "quality_score": result.quality_score,
            # v1.3.0 发现统计字段
            "first_found_at": result.first_found_at,
            "last_found_at": result.last_found_at,
            "found_count": result.found_count,
            "unique_searches": result.unique_searches,
            "created_at": result.created_at,
            "updated_at": result.updated_at
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> InstantSearchResult:
        """将字典转换为结果实体"""
        return InstantSearchResult(
            id=data["_id"],
            task_id=data["task_id"],
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            snippet=data.get("snippet"),
            content_hash=data.get("content_hash", ""),
            url_normalized=data.get("url_normalized", ""),
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            metadata=data.get("metadata", {}),
            relevance_score=data.get("relevance_score", 0.0),
            quality_score=data.get("quality_score", 0.0),
            first_found_at=data.get("first_found_at", datetime.utcnow()),
            last_found_at=data.get("last_found_at", datetime.utcnow()),
            found_count=data.get("found_count", 1),
            unique_searches=data.get("unique_searches", 1),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow())
        )

    async def find_by_content_hash(self, content_hash: str) -> Optional[InstantSearchResult]:
        """
        根据content_hash查找结果（去重的核心方法）

        v1.3.0 核心功能：
        - 如果content_hash存在，返回已有结果（去重命中）
        - 如果不存在，返回None（需要创建新结果）
        """
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"content_hash": content_hash})

            if data:
                logger.debug(f"去重命中: content_hash={content_hash}")
                return self._dict_to_result(data)

            return None

        except Exception as e:
            logger.error(f"查找content_hash失败: {e}")
            raise

    async def create(self, result: InstantSearchResult) -> InstantSearchResult:
        """创建结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(result)

            await collection.insert_one(result_dict)
            logger.info(f"创建即时搜索结果成功: {result.title[:50]}... (ID: {result.id})")

            return result

        except Exception as e:
            logger.error(f"创建即时搜索结果失败: {e}")
            raise

    async def update_discovery_stats(self, result: InstantSearchResult) -> InstantSearchResult:
        """
        更新发现统计信息（去重命中时调用）

        v1.3.0 核心功能：
        - 更新last_found_at为当前时间
        - found_count + 1
        - unique_searches + 1
        """
        try:
            collection = await self._get_collection()

            update_result = await collection.update_one(
                {"_id": result.id},
                {
                    "$set": {
                        "last_found_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$inc": {
                        "found_count": 1,
                        "unique_searches": 1
                    }
                }
            )

            if update_result.matched_count == 0:
                raise ValueError(f"结果不存在: {result.id}")

            # 更新实体对象的统计信息
            result.last_found_at = datetime.utcnow()
            result.updated_at = datetime.utcnow()
            result.found_count += 1
            result.unique_searches += 1

            logger.debug(f"更新发现统计成功: {result.id}")
            return result

        except Exception as e:
            logger.error(f"更新发现统计失败: {e}")
            raise

    async def get_by_id(self, result_id: str) -> Optional[InstantSearchResult]:
        """根据ID获取结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"获取即时搜索结果失败: {e}")
            raise


class InstantSearchResultMappingRepository:
    """即时搜索结果映射仓储（v1.3.0核心）"""

    def __init__(self):
        self.collection_name = "instant_search_result_mappings"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _mapping_to_dict(self, mapping: InstantSearchResultMapping) -> Dict[str, Any]:
        """将映射实体转换为字典"""
        return {
            "_id": mapping.id,
            "search_execution_id": mapping.search_execution_id,
            "result_id": mapping.result_id,
            "task_id": mapping.task_id,
            "found_at": mapping.found_at,
            "search_position": mapping.search_position,
            "relevance_score": mapping.relevance_score,
            "is_first_discovery": mapping.is_first_discovery,
            "created_at": mapping.created_at
        }

    def _dict_to_mapping(self, data: Dict[str, Any]) -> InstantSearchResultMapping:
        """将字典转换为映射实体"""
        return InstantSearchResultMapping(
            id=data["_id"],
            search_execution_id=data["search_execution_id"],
            result_id=data["result_id"],
            task_id=data["task_id"],
            found_at=data.get("found_at", datetime.utcnow()),
            search_position=data.get("search_position", 0),
            relevance_score=data.get("relevance_score", 0.0),
            is_first_discovery=data.get("is_first_discovery", False),
            created_at=data.get("created_at", datetime.utcnow())
        )

    async def create(self, mapping: InstantSearchResultMapping) -> InstantSearchResultMapping:
        """创建映射记录"""
        try:
            collection = await self._get_collection()
            mapping_dict = self._mapping_to_dict(mapping)

            await collection.insert_one(mapping_dict)
            logger.debug(f"创建结果映射成功: search={mapping.search_execution_id}, result={mapping.result_id}")

            return mapping

        except Exception as e:
            logger.error(f"创建结果映射失败: {e}")
            raise

    async def batch_create(self, mappings: List[InstantSearchResultMapping]) -> None:
        """批量创建映射记录"""
        if not mappings:
            return

        try:
            collection = await self._get_collection()
            mapping_dicts = [self._mapping_to_dict(m) for m in mappings]

            await collection.insert_many(mapping_dicts)
            logger.info(f"批量创建结果映射成功: {len(mappings)}条")

        except Exception as e:
            logger.error(f"批量创建结果映射失败: {e}")
            raise

    async def get_results_by_search_execution(
        self,
        search_execution_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取某次搜索执行的所有结果（通过JOIN映射表和结果表）

        v1.3.0 核心查询：
        - 通过search_execution_id查询映射表
        - JOIN instant_search_results表获取完整结果
        - 按search_position排序

        Returns:
            (results_with_mapping, total_count)
            每个结果包含：result字段（结果数据）+ mapping字段（映射元数据）
        """
        try:
            collection = await self._get_collection()

            # 使用MongoDB聚合管道实现JOIN查询
            skip = (page - 1) * page_size

            pipeline = [
                # 1. 筛选该次搜索执行的映射
                {"$match": {"search_execution_id": search_execution_id}},

                # 2. JOIN结果表
                {
                    "$lookup": {
                        "from": "instant_search_results",
                        "localField": "result_id",
                        "foreignField": "_id",
                        "as": "result"
                    }
                },

                # 3. 展开结果数组
                {"$unwind": "$result"},

                # 4. 按搜索排名排序
                {"$sort": {"search_position": 1}},

                # 5. 分页
                {"$skip": skip},
                {"$limit": page_size}
            ]

            # 执行查询
            cursor = collection.aggregate(pipeline)
            results_with_mapping = []

            async for doc in cursor:
                results_with_mapping.append({
                    "mapping": self._dict_to_mapping(doc),
                    "result": InstantSearchResultRepository()._dict_to_result(doc["result"])
                })

            # 计算总数
            total = await collection.count_documents({"search_execution_id": search_execution_id})

            logger.debug(f"查询搜索结果成功: search_execution_id={search_execution_id}, total={total}")
            return results_with_mapping, total

        except Exception as e:
            logger.error(f"查询搜索结果失败: {e}")
            raise

    async def get_mappings_by_result(self, result_id: str) -> List[InstantSearchResultMapping]:
        """
        查询哪些搜索发现了该结果（反向查询）

        用于追溯结果的发现历史
        """
        try:
            collection = await self._get_collection()
            cursor = collection.find({"result_id": result_id}).sort("found_at", -1)

            mappings = []
            async for data in cursor:
                mappings.append(self._dict_to_mapping(data))

            return mappings

        except Exception as e:
            logger.error(f"查询结果映射失败: {e}")
            raise
